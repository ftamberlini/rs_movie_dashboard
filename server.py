"""FastAPI backend — CineMap dashboard (DuckDB + Parquet, no Oracle at runtime)."""
import os
import re
import threading
from pathlib import Path
from contextlib import asynccontextmanager

import duckdb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))

_PARQUET_TABLES = [
    "country", "ml_imdb", "director", "writer",
    "movie_imdb", "movie_country", "movie_ml_genre", "movie_imdb_genre",
    "movie_director", "movie_writer", "movie_rating",
    "subtitle_geo", "subtitle_theme",
]


def _new_db() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB in-memory connection with views over the Parquet files."""
    con = duckdb.connect(":memory:")
    for t in _PARQUET_TABLES:
        p = DATA_DIR / f"{t}.parquet"
        if p.exists():
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}')")
    return con


# ── Value parsers ─────────────────────────────────────────────────────────────

def _float(s):
    try:
        return round(float(s), 1)
    except (TypeError, ValueError):
        return None


def _int(s):
    if not s or s == "N/A":
        return 0
    cleaned = re.sub(r"[^0-9]", "", str(s))
    return int(cleaned) if cleaned else 0


def _box(s):
    """'$14,648,076' → 14.65  (USD millions)."""
    if not s or s in ("N/A", "$0", ""):
        return 0.0
    digits = re.sub(r"[^0-9]", "", str(s))
    return round(int(digits) / 1_000_000, 2) if digits else 0.0


def _gender(g):
    if not g:
        return "Unknown"
    u = g.upper()
    if u == "MALE":
        return "Male"
    if u == "FEMALE":
        return "Female"
    return "Unknown"


def _race(r):
    if not r:
        return "UNKNOWN"
    return "UNKNOWN" if r.upper() == "UNDEFINED" else r.upper()


# ── Main films query (DuckDB / Parquet) ───────────────────────────────────────

_FILMS_QUERY = """\
WITH
  m AS (
    SELECT IMDBID, MOVIEID, TITLE, YEAR, IMDBRATING, IMDBVOTES, BOXOFFICE,
           OSCAR_WINNING, OSCAR_NOMINATION,
           AWARD_WINNING, AWARD_NOMINATION,
           BAFTA_WINNING, BAFTA_NOMINATION,
           EMMY_WINNING,  EMMY_NOMINATION,
           GENRE    AS IMDB_GENRE_RAW,
           COUNTRY  AS IMDB_COUNTRY_RAW
    FROM movie_imdb
    WHERE TYPE     = 'movie'
      AND IMDBRATING IS NOT NULL
      AND IMDBRATING != 'N/A'
      AND RESPONSE  = 'true'
  ),
  fc AS (
    SELECT mc.IMDBID, mc.COUNTRY,
           COALESCE(ci.CONTINENT, cn.CONTINENT) AS CONTINENT,
           COALESCE(ci.REGION,    cn.REGION)    AS REGION,
           ROW_NUMBER() OVER (PARTITION BY mc.IMDBID) AS rn
    FROM movie_country mc
    LEFT JOIN country ci ON ci.ISO     = mc.ISO
    LEFT JOIN country cn ON cn.COUNTRY = mc.COUNTRY AND ci.ISO IS NULL
    JOIN m ON m.IMDBID = mc.IMDBID
  ),
  fg AS (
    SELECT mg.MOVIEID, mg.GENRE,
           ROW_NUMBER() OVER (PARTITION BY mg.MOVIEID) AS rn
    FROM movie_ml_genre mg
    JOIN m ON m.MOVIEID = mg.MOVIEID
  ),
  fi AS (
    SELECT ig.IMDBID, ig.GENRE,
           ROW_NUMBER() OVER (PARTITION BY ig.IMDBID) AS rn
    FROM movie_imdb_genre ig
    JOIN m ON m.IMDBID = ig.IMDBID
  ),
  fd AS (
    SELECT md.IMDBID, md.DIRECTORID,
           d.NAME, d.GENDER, d.GENDER_LLM, d.RACE, d.BIRTHYEAR, d.NATIONALITY,
           ROW_NUMBER() OVER (PARTITION BY md.IMDBID) AS rn
    FROM movie_director md
    JOIN director d ON d.DIRECTORID = md.DIRECTORID
    JOIN m          ON m.IMDBID     = md.IMDBID
  ),
  fw AS (
    SELECT mw.IMDBID, mw.WRITERID,
           w.NAME, w.GENDER, w.RACE, w.BIRTHYEAR, w.NATIONALITY,
           ROW_NUMBER() OVER (PARTITION BY mw.IMDBID) AS rn
    FROM movie_writer mw
    JOIN writer w ON w.WRITERID = mw.WRITERID
    JOIN m        ON m.IMDBID   = mw.IMDBID
  ),
  fv AS (
    SELECT m.MOVIEID, SUM(mr.COUNT_RATING) AS VOTES_ML
    FROM movie_rating mr
    JOIN m ON m.MOVIEID = mr.MOVIEID
    GROUP BY m.MOVIEID
  ),
  fd_all AS (
    SELECT md.IMDBID,
           STRING_AGG(d.NAME, ', ') AS ALL_DIRS
    FROM movie_director md
    JOIN director d ON d.DIRECTORID = md.DIRECTORID
    JOIN m          ON m.IMDBID     = md.IMDBID
    GROUP BY md.IMDBID
  ),
  fc_all AS (
    SELECT mc.IMDBID,
           STRING_AGG(COALESCE(ci.COUNTRY, cn.COUNTRY, mc.COUNTRY), ', ') AS ALL_COUNTRIES
    FROM movie_country mc
    LEFT JOIN country ci ON ci.ISO     = mc.ISO
    LEFT JOIN country cn ON cn.COUNTRY = mc.COUNTRY AND ci.ISO IS NULL
    JOIN m ON m.IMDBID = mc.IMDBID
    GROUP BY mc.IMDBID
  ),
  fg_all AS (
    SELECT mg.MOVIEID,
           STRING_AGG(mg.GENRE, ', ') AS ALL_ML_GENRES
    FROM movie_ml_genre mg
    JOIN m ON m.MOVIEID = mg.MOVIEID
    GROUP BY mg.MOVIEID
  ),
  fi_all AS (
    SELECT ig.IMDBID,
           STRING_AGG(ig.GENRE, ', ') AS ALL_IMDB_GENRES
    FROM movie_imdb_genre ig
    JOIN m ON m.IMDBID = ig.IMDBID
    GROUP BY ig.IMDBID
  )
SELECT
  m.IMDBID, m.MOVIEID, m.TITLE, m.YEAR,
  m.IMDBRATING, m.IMDBVOTES, m.BOXOFFICE,
  m.OSCAR_WINNING,   m.OSCAR_NOMINATION,
  m.AWARD_WINNING,   m.AWARD_NOMINATION,
  m.BAFTA_WINNING,   m.BAFTA_NOMINATION,
  m.EMMY_WINNING,    m.EMMY_NOMINATION,
  m.IMDB_GENRE_RAW,  m.IMDB_COUNTRY_RAW,
  fc.COUNTRY,    fc.CONTINENT,  fc.REGION,
  fg.GENRE       AS ML_GENRE,
  fi.GENRE       AS IMDB_GENRE,
  COALESCE(fd.GENDER, fd.GENDER_LLM) AS DIR_GENDER,
  fd.DIRECTORID  AS DIR_ID,
  fd.NAME        AS DIR_NAME,
  fd.RACE        AS DIR_RACE,
  fd.BIRTHYEAR   AS DIR_BY,
  fd.NATIONALITY AS DIR_NAT,
  fw.WRITERID    AS WRI_ID,
  fw.NAME        AS WRI_NAME,
  fw.GENDER      AS WRI_GENDER,
  fw.RACE        AS WRI_RACE,
  fw.BIRTHYEAR   AS WRI_BY,
  fw.NATIONALITY AS WRI_NAT,
  fv.VOTES_ML,
  fd_all.ALL_DIRS,
  fc_all.ALL_COUNTRIES,
  COALESCE(fg_all.ALL_ML_GENRES, fi_all.ALL_IMDB_GENRES) AS ALL_GENRES
FROM m
LEFT JOIN fc     ON fc.IMDBID    = m.IMDBID  AND fc.rn = 1
LEFT JOIN fg     ON fg.MOVIEID   = m.MOVIEID AND fg.rn = 1
LEFT JOIN fi     ON fi.IMDBID    = m.IMDBID  AND fi.rn = 1
LEFT JOIN fd     ON fd.IMDBID    = m.IMDBID  AND fd.rn = 1
LEFT JOIN fw     ON fw.IMDBID    = m.IMDBID  AND fw.rn = 1
LEFT JOIN fv     ON fv.MOVIEID   = m.MOVIEID
LEFT JOIN fd_all ON fd_all.IMDBID  = m.IMDBID
LEFT JOIN fc_all ON fc_all.IMDBID  = m.IMDBID
LEFT JOIN fg_all ON fg_all.MOVIEID = m.MOVIEID
LEFT JOIN fi_all ON fi_all.IMDBID  = m.IMDBID
ORDER BY m.TITLE
"""


# ── Cache ─────────────────────────────────────────────────────────────────────
_FILMS:        list[dict] = []
_RATINGS_DIST: list[dict] = []
_LOCATIONS:    list[dict] = []
_READY:        bool       = False


def _load_ratings_dist() -> list[dict]:
    con = _new_db()
    rows = con.execute(
        "SELECT RATING, SUM(COUNT_RATING) AS VOTES"
        " FROM movie_rating GROUP BY RATING ORDER BY RATING"
    ).fetchall()
    con.close()
    return [{"rating": float(r[0]), "votes": int(r[1])} for r in rows]


# ── Location classifier ────────────────────────────────────────────────────────

# Lookup: normalized (stripped, lowercase) → type
# Types: Country, City, State, Region, Other
_LOC_TYPES: dict[str, str] = {
    # ── Countries (sovereign / historical) ────────────────────────────────────
    **{k: "Country" for k in [
        "france","england","germany","china","italy","japan","india","mexico",
        "russia","spain","canada","australia","brazil","vietnam","egypt","poland",
        "turkey","greece","korea","south korea","north korea","sweden","israel",
        "scotland","ireland","cuba","belgium","thailand","austria","norway","denmark",
        "singapore","south africa","argentina","morocco","pakistan","iran",
        "philippines","portugal","hungary","ukraine","peru","romania","taiwan",
        "chile","jamaica","wales","iceland","netherlands","holland","venezuela",
        "colombia","lebanon","kenya","indonesia","malaysia","congo",
        "democratic republic of the congo","republic of the congo",
        "algeria","yugoslavia","czechoslovakia","chad","bulgaria","bosnia",
        "sudan","bangladesh","bolivia","nepal","cambodia","burma","myanmar",
        "libya","haiti","guatemala","nigeria","ethiopia","saudi arabia","guinea",
        "switzerland","hong kong","afghanistan","iraq","jordan","panama",
        "new zealand","finland","syria","bahamas","ussr","the soviet union",
        "soviet union","great britain","united kingdom","united states",
        "the united states","the united states of america","usa","u.s.","u.s.a.",
        "uk","britain","america","united arab emirates","uae",
        "north africa","georgia (country)","congo","croatia","serbia","slovakia",
        "czechia","czech republic","luxembourg","iceland","malta","moldova",
        "albania","armenia","azerbaijan","georgia","kazakhstan","uzbekistan",
        "tajikistan","kyrgyzstan","turkmenistan","belarus","latvia","lithuania",
        "estonia","macedonia","montenegro","kosovo","andorra","liechtenstein",
        "san marino","monaco","cyprus","iraq","qatar","bahrain","kuwait",
        "oman","yemen","sri lanka","myanmar","laos","mongolia","bhutan",
        "maldives","east timor","timor-leste","brunei","papua new guinea",
        "fiji","samoa","tonga","vanuatu","palau","kiribati","nauru",
        "eritrea","djibouti","somalia","tanzania","uganda","rwanda","burundi",
        "malawi","zambia","zimbabwe","mozambique","madagascar","mauritius",
        "seychelles","comoros","angola","namibia","botswana","lesotho",
        "swaziland","eswatini","sierra leone","liberia","ghana","senegal",
        "mali","niger","burkina faso","benin","togo","gambia","guinea-bissau",
        "cape verde","cameroon","gabon","equatorial guinea",
        "central african republic","south sudan","malawi",
        "dominican republic","trinidad and tobago","barbados","grenada",
        "saint lucia","saint vincent","belize","honduras","nicaragua",
        "el salvador","costa rica","ecuador","paraguay","uruguay","guyana",
        "suriname","french guiana","puerto rico","caribbean",
        "palestine","israel","iran","iraq",
        # common alternate spellings / historical names
        "persia","siam","ceylon","rhodesia","zaire","abyssinia",
        "bohemia","prussia","ottoman","austro-hungarian",
    ]},
    # ── Cities ────────────────────────────────────────────────────────────────
    **{k: "City" for k in [
        # USA cities
        "new york","new york city","los angeles","chicago","houston","phoenix",
        "philadelphia","san antonio","san diego","dallas","san francisco",
        "san jose","austin","jacksonville","fort worth","columbus","charlotte",
        "indianapolis","san francisco","seattle","denver","washington","boston",
        "detroit","nashville","memphis","portland","las vegas","baltimore",
        "milwaukee","albuquerque","tucson","fresno","sacramento","mesa",
        "kansas city","atlanta","omaha","colorado springs","raleigh","virginia beach",
        "long beach","minneapolis","tampa","new orleans","wichita","arlington",
        "bakersfield","anaheim","aurora","santa ana","corpus christi","riverside",
        "st. louis","lexington","pittsburgh","stockton","anchorage","cincinnati",
        "st. paul","greensboro","toledo","newark","plano","henderson","lincoln",
        "buffalo","fort wayne","jersey city","chula vista","orlando","st. petersburg",
        "norfolk","chandler","laredo","madison","durham","lubbock","winston-salem",
        "garland","glendale","hialeah","reno","baton rouge","irvine","chesapeake",
        "scottsdale","north las vegas","fremont","gilbert","birmingham","rochester",
        "richmond","san bernardino","spokane","des moines","montgomery","modesto",
        "fayetteville","tacoma","shreveport","akron","aurora","yonkers","mobile",
        "little rock","glendale","amarillo","huntington beach","grand rapids",
        "salt lake city","tallahassee","huntsville","worcester","knoxville",
        "brownsville","santa clarita","providence","garden grove","oceanside",
        "chattanooga","fort lauderdale","rancho cucamonga","santa rosa","oceanside",
        "tempe","cape coral","springfield","eugene","peoria","elk grove",
        "cary","hayward","coral springs","sterling heights","hollywood",
        "torrance","paterson","east los angeles","sunnyvale","bridgeport",
        "clarksville","pomona","rockford","alexandria","escondido","macon",
        "columbia","lakewood","sunnyvale","savannah","pomona","pasadena",
        "kansas city","fort collins","salinas","hampton","palmdale","sunnyvale",
        "corona","springfield","jackson","hartford","berkeley","cedar rapids",
        "flint","athens","columbus","richmond","boise","cambridge","el paso",
        "miami","honolulu","brooklyn","manhattan","bronx","queens",
        "the bronx","beverly hills","malibu","santa monica","burbank",
        "pasadena","long island","staten island","harlem","soho",
        "chinatown","greenwich","times square","wall street",
        # International cities
        "paris","london","rome","berlin","tokyo","moscow","madrid","vienna",
        "amsterdam","milan","barcelona","munich","brussels","stockholm",
        "oslo","copenhagen","helsinki","athens","lisbon","prague","warsaw",
        "budapest","bucharest","sofia","zagreb","belgrade","sarajevo","kiev",
        "kyiv","minsk","vilnius","riga","tallinn","reykjavik","dublin",
        "edinburgh","glasgow","manchester","liverpool","birmingham","leeds",
        "bristol","oxford","cambridge","brighton","dover","chester",
        "beijing","shanghai","guangzhou","shenzhen","chengdu","wuhan",
        "xi'an","nanjing","hangzhou","chongqing","tianjin","hong kong","macau",
        "tokyo","osaka","kyoto","hiroshima","nagasaki","yokohama","sapporo",
        "kobe","nagoya","fukuoka","sendai","okinawa",
        "seoul","busan","incheon","daegu",
        "delhi","new delhi","mumbai","bombay","calcutta","kolkata","chennai",
        "madras","bangalore","bengaluru","hyderabad","pune","ahmedabad",
        "jaipur","surat","lucknow","kanpur","nagpur","indore",
        "karachi","lahore","islamabad","rawalpindi","faisalabad",
        "dhaka","chittagong",
        "sydney","melbourne","brisbane","perth","adelaide","canberra",
        "auckland","wellington","christchurch",
        "toronto","montreal","vancouver","calgary","edmonton","ottawa","quebec",
        "mexico city","guadalajara","monterrey","tijuana","acapulco","cancun",
        "buenos aires","rio de janeiro","rio","sao paulo","brasilia","salvador",
        "bogota","medellin","cali","lima","santiago","caracas","quito",
        "la paz","asuncion","montevideo","panama city","san jose","managua",
        "tegucigalpa","guatemala city","havana","santo domingo","san juan",
        "port-au-prince",
        "cairo","alexandria","casablanca","tunis","algiers","tripoli",
        "lagos","accra","nairobi","dar es salaam","addis ababa","khartoum",
        "cape town","johannesburg","durban","pretoria",
        "tehran","baghdad","riyadh","dubai","abu dhabi","beirut","amman",
        "jerusalem","tel aviv","damascus","ankara","istanbul","kabul",
        "bangkok","singapore","kuala lumpur","jakarta","manila","hanoi",
        "ho chi minh city","saigon","phnom penh","vientiane","rangoon","yangon",
        "colombo","kathmandu","dhaka","ulaanbaatar",
        "zurich","geneva","bern","basel","vienna","salzburg","innsbruck",
        "amsterdam","rotterdam","the hague","utrecht","bruges","ghent","antwerp",
        "luxembourg city","strasbourg","marseille","marseilles","bordeaux",
        "lyon","toulouse","nice","cannes","versailles","montpellier",
        "hamburg","frankfurt","cologne","dusseldorf","stuttgart","bremen",
        "leipzig","dresden","nuremberg","heidelberg","bonn",
        "warsaw","krakow","lodz","wroclaw","poznan","gdansk",
        "budapest","debrecen","miskolc","pecs","gyor",
        "bucharest","cluj-napoca","timisoara","iasi","constanta",
        "prague","brno","ostrava","plzen",
        "bratislava","kosice","zilina",
        "zagreb","split","rijeka","osijek",
        "belgrade","novi sad","nis","kragujevac",
        "sarajevo","banja luka","mostar",
        "sofia","plovdiv","varna","burgas",
        "athens","thessaloniki","piraeus","patras","heraklion",
        "lisbon","porto","braga","coimbra","setubal",
        "madrid","barcelona","valencia","seville","bilbao","malaga","zaragoza",
        "rome","milan","naples","turin","palermo","genoa","bologna","florence",
        "venice","verona","catania","bari","messina","padua","trieste",
        "stockholm","gothenburg","malmo","uppsala",
        "oslo","bergen","stavanger","trondheim",
        "copenhagen","aarhus","odense","aalborg",
        "helsinki","tampere","turku","oulu","espoo",
        "reykjavik","akureyri",
        "dublin","cork","limerick","galway","waterford",
        "edinburgh","glasgow","aberdeen","dundee","inverness",
        "cardiff","swansea","newport",
        "london","paris","berlin","rome","madrid","moscow","istanbul",
        # Historical city names
        "leningrad","peking","bombay","calcutta","saigon","rangoon","rhodesia",
        "constantinople","byzantium","carthage","babylon","troy","pompeii",
        "auschwitz","hiroshima","nagasaki","stalingrad","dunkirk","normandy beach",
        # US neighborhoods / boroughs treated as cities
        "beverly hills","hollywood","manhattan","brooklyn","bronx","queens",
        "staten island","harlem","chinatown","little italy","soho","tribeca",
        "greenwich village","the village","midtown","downtown","uptown",
        "long island city","astoria","flushing","coney island","brighton beach",
        # Commonly missed US cities
        "cleveland","charlotte","kansas city","oklahoma city","atlantic city",
        "jersey city","salt lake city","virginia beach","colorado springs",
        "fort worth","fort lauderdale","st. louis","saint louis","st louis",
        "st. paul","saint paul","st paul","st. petersburg","saint petersburg",
        "la jolla","palm springs","palm beach","west palm beach","boca raton",
        "fort myers","fort collins","fort wayne","fort smith","fort lee",
        "newport","newport beach","newport news","new haven","new brunswick",
        "new rochelle","new bedford","new britain","new london","new albany",
        "santa fe","santa barbara","santa clara","santa cruz","san marcos",
        "san bernardino","san leandro","san mateo","san rafael","san ramon",
        "san luis obispo","santa ana","santa rosa","santa clarita","pomona",
        "rancho cucamonga","moreno valley","ontario","corona","roseville",
        "lancaster","palmdale","sunnyvale","hayward","fremont","concord",
        "elk grove","vallejo","peoria","springfield","champaign","decatur",
        "rockford","joliet","naperville","aurora","waukegan","evanston",
        "gary","south bend","fort wayne","evansville","terre haute",
        "dayton","akron","youngstown","canton","lorain","parma","toledo",
        "lansing","ann arbor","flint","kalamazoo","grand rapids","saginaw",
        "madison","green bay","kenosha","racine","appleton","waukesha",
        "des moines","cedar rapids","davenport","sioux city","waterloo",
        "omaha","lincoln","bellevue","hastings",
        "topeka","wichita","overland park","olathe",
        "tulsa","norman","lawton","broken arrow",
        "jackson","hattiesburg","meridian","biloxi","gulfport",
        "shreveport","baton rouge","lafayette","lake charles","monroe",
        "knoxville","chattanooga","clarksville","murfreesboro","franklin",
        "columbia","greenville","mount pleasant","rock hill","sumter",
        "durham","raleigh","greensboro","winston-salem","fayetteville",
        "richmond","norfolk","chesapeake","virginia beach","portsmouth",
        "charleston","huntington","morgantown","parkersburg",
        "portland","eugene","salem","corvallis","bend","medford",
        "spokane","tacoma","bellevue","everett","kent","renton","kirkland",
        "anchorage","fairbanks","juneau",
        "honolulu","hilo","kailua","kaneohe",
        "albuquerque","las cruces","rio rancho","santa fe",
        "boise","nampa","meridian","idaho falls","pocatello",
        "billings","missoula","great falls","bozeman","helena",
        "cheyenne","casper","laramie","gillette",
        "sioux falls","rapid city","aberdeen","watertown",
        "fargo","bismarck","grand forks","minot",
        "pierre","rapid city","huron","yankton",
        "augusta","portland","bangor","lewiston","auburn",
        "concord","manchester","nashua","dover","portsmouth",
        "burlington","montpelier","rutland","barre",
        "providence","warwick","cranston","pawtucket","woonsocket",
        "dover","wilmington","newark","milford",
        "annapolis","frederick","gaithersburg","rockville","hagerstown",
        "hartford","new haven","bridgeport","stamford","waterbury","norwalk",
        # More international
        "nice","cannes","monte carlo","monaco","san remo","menton",
        "lausanne","lucerne","interlaken","davos","st. moritz","zermatt",
        "innsbruck","graz","linz","salzburg","klagenfurt",
        "bologna","florence","verona","padua","trieste","bari","catania",
        "messina","reggio","brescia","modena","parma","pisa","livorno",
        "porto","braga","coimbra","faro","setubal","funchal",
        "seville","bilbao","valencia","malaga","murcia","palma","las palmas",
        "cologne","dusseldorf","essen","dortmund","stuttgart","nuremberg",
        "heidelberg","freiburg","hannover","bielefeld","bonn","mannheim",
        "wiesbaden","karlsruhe","augsburg","wuppertal","aachen",
        "lodz","wroclaw","poznan","gdansk","szczecin","bydgoszcz","lublin",
        "brno","ostrava","plzen","olomouc","liberec",
        "kosice","zilina","banska bystrica","presov",
        "pecs","miskolc","debrecen","gyor","szekesfehervar","kecskemet",
        "constanta","timisoara","cluj-napoca","iasi","craiova","brasov",
        "varna","plovdiv","burgas","stara zagora","ruse",
        "thessaloniki","piraeus","patras","heraklion","larissa",
        "rotterdam","the hague","utrecht","eindhoven","tilburg","groningen",
        "bruges","ghent","antwerp","liege","charleroi","namur",
        "aarhus","odense","aalborg","esbjerg","horsens","vejle",
        "gothenburg","malmo","uppsala","linkoping","orebro","vasteras",
        "tampere","turku","oulu","espoo","vantaa","lahti","jyvaskyla",
        "bergen","stavanger","trondheim","kristiansand","bodo","tromso",
        "cork","limerick","galway","waterford","dundalk","drogheda",
        "aberdeen","dundee","inverness","stirling","perth","paisley",
        "cardiff","swansea","newport","wrexham",
        "belfast","derry","londonderry","armagh","newry",
        "liverpool","leeds","sheffield","bristol","manchester","birmingham",
        "glasgow","edinburgh","leicester","coventry","bradford","kingston",
        "nottingham","hull","stoke","wolverhampton","derby","southampton",
        "portsmouth","reading","york","sunderland","plymouth","exeter",
        "brighton","hove","oxford","cambridge","bath","wells","salisbury",
        "durham","newcastle","middlesbrough","sunderland","chester","dover",
        "canterbury","rochester","maidstone","guildford","woking",
        "zurich","bern","lausanne","geneva","basel","winterthur","st. gallen",
        "toronto","montreal","vancouver","calgary","edmonton","ottawa",
        "winnipeg","hamilton","kitchener","london ontario","st. catharines",
        "halifax","moncton","saint john","fredericton","charlottetown",
        "sydney nova scotia","cape breton",
        "melbourne","brisbane","perth","adelaide","canberra","hobart","darwin",
        "christchurch","auckland","wellington","dunedin","hamilton nz",
        "guadalajara","monterrey","puebla","leon","juarez","culiacan",
        "merida","aguascalientes","queretaro","tabasco",
        "bogota","medellin","cali","barranquilla","cartagena","bucaramanga",
        "lima","arequipa","trujillo","chiclayo","piura","iquitos",
        "santiago","valparaiso","concepcion","antofagasta","vina del mar",
        "caracas","maracaibo","valencia venezuela","barquisimeto",
        "quito","guayaquil","cuenca","manta","ambato",
        "la paz","santa cruz","cochabamba","sucre",
        "asuncion","ciudad del este","encarnacion",
        "montevideo","salto","paysandu",
        "buenos aires","cordoba","rosario","mendoza","tucuman","salta",
        "sao paulo","rio de janeiro","belo horizonte","salvador","fortaleza",
        "curitiba","manaus","porto alegre","belem","recife","natal",
        "nairobi","mombasa","kisumu","nakuru","eldoret",
        "accra","kumasi","tamale","sekondi","cape coast",
        "lagos","abuja","ibadan","kano","kaduna","benin city","port harcourt",
        "addis ababa","dire dawa","mekelle","gondar","hawassa",
        "cairo","giza","alexandria","luxor","aswan","port said","ismailia",
        "casablanca","rabat","marrakech","fes","meknes","tangier","agadir",
        "algiers","oran","constantine","annaba","blida","batna",
        "tunis","sfax","sousse","kairouan","bizerte",
        "tripoli","benghazi","misrata","sirte","tobruk",
        "khartoum","omdurman","port sudan","kassala",
        "dar es salaam","dodoma","mwanza","arusha","zanzibar",
        "kampala","gulu","jinja","mbarara","entebbe",
        "kigali","butare","gisenyi","ruhengeri",
        "harare","bulawayo","mutare","gweru","kwekwe",
        "lusaka","ndola","kitwe","kabwe","livingstone",
        "windhoek","walvis bay","swakopmund",
        "gaborone","francistown","maun","selebi-phikwe",
        "johannesburg","cape town","durban","pretoria","port elizabeth",
        "east london","bloemfontein","pietermaritzburg","soweto",
        "tehran","mashhad","isfahan","tabriz","shiraz","karaj","qom",
        "riyadh","jeddah","mecca","medina","dammam","khobar","dhahran",
        "dubai","abu dhabi","sharjah","ajman","ras al-khaimah",
        "doha","al rayyan","al wakrah","al khor",
        "kuwait city","ahmadi","hawalli","salmiya",
        "manama","riffa","muharraq","isa town",
        "muscat","salalah","nizwa","sohar",
        "sanaa","aden","taiz","hodeidah","ibb",
        "amman","zarqa","irbid","aqaba","zarqa",
        "beirut","tripoli lebanon","sidon","tyre","zahle",
        "damascus","aleppo","homs","latakia","hama","deir ez-zor",
        "ankara","istanbul","izmir","bursa","adana","gaziantep","konya",
        "kabul","kandahar","herat","mazar-i-sharif","jalalabad",
        "islamabad","karachi","lahore","faisalabad","rawalpindi","gujranwala",
        "dhaka","chittagong","khulna","rajshahi","sylhet","comilla",
        "colombo","kandy","galle","jaffna","negombo",
        "kathmandu","pokhara","lalitpur","biratnagar",
        "yangon","mandalay","naypyidaw","bago","mawlamyine",
        "phnom penh","siem reap","battambang","sihanoukville",
        "vientiane","luang prabang","savannakhet",
        "hanoi","ho chi minh city","da nang","hai phong","hue","can tho",
        "bangkok","chiang mai","pattaya","phuket","hat yai","khon kaen",
        "singapore","jurong","woodlands","tampines","changi",
        "kuala lumpur","george town","ipoh","johor bahru","shah alam",
        "jakarta","surabaya","bandung","medan","semarang","palembang","makassar",
        "manila","quezon city","cebu","davao","zamboanga","cagayan de oro",
        "beijing","shanghai","guangzhou","shenzhen","chengdu","wuhan",
        "tianjin","chongqing","nanjing","xi'an","hangzhou","shenyang",
        "harbin","changchun","dalian","qingdao","jinan","zhengzhou",
        "kunming","lanzhou","taiyuan","hefei","fuzhou","nanchang","guiyang",
        "taipei","taichung","tainan","kaohsiung","hsinchu","taoyuan",
        "tokyo","osaka","kyoto","nagoya","sapporo","kobe","yokohama",
        "fukuoka","kawasaki","sendai","saitama","hiroshima","chiba",
        "seoul","busan","incheon","daegu","daejeon","gwangju","suwon",
        "ulaanbaatar","darkhan","erdenet",
        "moscow","saint petersburg","novosibirsk","yekaterinburg","nizhny novgorod",
        "kazan","chelyabinsk","omsk","samara","rostov-on-don","ufa","krasnoyarsk",
        "perm","voronezh","volgograd","saratov","krasnodar","tolyatti",
        "kiev","kharkiv","odessa","dnipro","donetsk","zaporizhzhia","lviv",
        "minsk","gomel","vitebsk","mogilev","grodno","brest",
        "vilnius","kaunas","klaipeda","siauliai","panevezys",
        "riga","daugavpils","liepaja","jurmala","jelgava",
        "tallinn","tartu","narva","parnu","kohtla-jarve",
        "yerevan","gyumri","vanadzor","vagharshapat",
        "tbilisi","kutaisi","batumi","rustavi","zugdidi",
        "baku","ganja","sumqayit","mingachevir",
        "tashkent","samarkand","namangan","andijan","fergana","bukhara",
        "dushanbe","khujand","kulob","qurghonteppa",
        "bishkek","osh","jalal-abad","karakol",
        "astana","almaty","shymkent","karaganda","aktobe","taraz","pavlodar",
        "ashgabat","turkmenbashi","mary","dashoguz",
        "prague","brno","ostrava","plzen","olomouc","liberec","ceske budejovice",
        "bratislava","kosice","zilina","banska bystrica","nitra","trnava",
        "warsaw","krakow","lodz","wroclaw","poznan","gdansk","szczecin",
        "lublin","bydgoszcz","katowice","bialystok","gdynia","czestochowa",
        "budapest","debrecen","miskolc","pecs","gyor","nyiregyhaza","kecskemet",
        "bucharest","cluj-napoca","timisoara","iasi","constanta","craiova",
        "brasov","galati","ploiesti","braila","oradea",
        "sofia","plovdiv","varna","burgas","ruse","stara zagora",
        "zagreb","split","rijeka","osijek","zadar","slavonski brod",
        "belgrade","novi sad","nis","kragujevac","subotice","subotica",
        "sarajevo","banja luka","tuzla","zenica","mostar",
        "podgorica","niksic","pljevlja","bijelo polje",
        "pristina","prizren","peja","gjilan","mitrovica",
        "skopje","bitola","tetovo","kumanovo","ohrid",
        "tirana","durres","shkoder","vlore","elbasan","korce",
        "chisinau","tiraspol","balti","bender",
        "yerevan","gyumri","vanadzor",
        "bern","zurich","geneva","lausanne","basel","winterthur",
        "vienna","graz","linz","salzburg","innsbruck","klagenfurt","wels",
        "amsterdam","rotterdam","the hague","utrecht","eindhoven","tilburg",
        "groningen","breda","nijmegen","apeldoorn","arnhem","enschede",
        "brussels","antwerp","ghent","bruges","liege","namur","charleroi",
        "luxembourg city","esch-sur-alzette","differdange",
        "paris","marseille","lyon","toulouse","nice","nantes","strasbourg",
        "montpellier","bordeaux","lille","rennes","reims","le havre","toulon",
        "dijon","angers","nimes","clermont-ferrand","saint-etienne","le mans",
        "aix-en-provence","brest france","limoges","amiens","metz","nancy",
        "perpignan","caen","mulhouse","rouen","tours","grenoble","besancon",
        "rome","milan","naples","turin","palermo","genoa","bologna","florence",
        "catania","bari","venice","verona","messina","padua","trieste","taranto",
        "brescia","prato","reggio calabria","modena","reggio emilia",
        "parma","pisa","livorno","cagliari","foggia","perugia","salerno",
        "berlin","hamburg","munich","cologne","frankfurt","essen","dortmund",
        "dusseldorf","stuttgart","bremen","hannover","nuremberg","duisburg",
        "bochum","wuppertal","bielefeld","bonn","munster","karlsruhe",
        "mannheim","augsburg","wiesbaden","gelsenkirchen","monchengladbach",
        "aachen","braunschweig","chemnitz","kiel","halle","magdeburg","freiburg",
        "krefeld","lubeck","oberhausen","erfurt","mainz","rostock","kassel",
        "hagen","saarbrucken","hamm","mulheim","solingen","leverkusen",
        "madrid","barcelona","valencia","seville","bilbao","malaga","murcia",
        "palma","alicante","cordoba","valladolid","vitoria","gijon","la coruna",
        "granada","las palmas","santa cruz","zaragoza","pamplona","san sebastian",
        "lisbon","porto","braga","amadora","setubal","coimbra","funchal",
        "oslo","bergen","stavanger","trondheim","baerum","drammen","fredrikstad",
        "kristiansand","tromso","sandnes","sarpsborg","bodo",
        "stockholm","gothenburg","malmo","uppsala","vasteras","orebro",
        "linkoping","helsingborg","jonkoping","norrkoping","lund",
        "copenhagen","aarhus","odense","aalborg","frederiksberg","esbjerg",
        "helsinki","espoo","tampere","vantaa","oulu","turku","jyvaskyla",
        "reykjavik","kopavogur","hafnarfjordur","akureyri",
        "dublin","cork","limerick","galway","waterford","drogheda","dundalk",
        "belfast","derry","armagh","newry","lisburn","bangor northern ireland",
        "edinburgh","glasgow","aberdeen","dundee","inverness","stirling","perth",
        "cardiff","swansea","newport wales","wrexham","newport gwent",
        "london","manchester","birmingham","leeds","sheffield","bristol",
        "liverpool","leicester","coventry","bradford","nottingham","hull",
        "newcastle","sunderland","middlesbrough","wolverhampton","derby",
        "southampton","portsmouth","plymouth","exeter","brighton","oxford",
        "cambridge","bath","york","reading","stoke-on-trent",
        "athens","thessaloniki","piraeus","heraklion","larissa","patras","volos",
    ]},
    # ── US States (+ DC + territories) ───────────────────────────────────────
    **{k: "State" for k in [
        "alabama","alaska","arizona","arkansas","california","colorado",
        "connecticut","delaware","florida","georgia","hawaii","idaho",
        "illinois","indiana","iowa","kansas","kentucky","louisiana",
        "maine","maryland","massachusetts","michigan","minnesota","mississippi",
        "missouri","montana","nebraska","nevada","new hampshire","new jersey",
        "new mexico","new york state","north carolina","north dakota","ohio",
        "oklahoma","oregon","pennsylvania","rhode island","south carolina",
        "south dakota","tennessee","texas","utah","vermont","virginia",
        "washington state","west virginia","wisconsin","wyoming",
        "washington d.c.","district of columbia",
        # Abbreviations
        "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id",
        "il","in","ia","ks","ky","la","me","md","ma","mi","mn","ms",
        "mo","mt","ne","nv","nh","nj","nm","ny","nc","nd","oh","ok",
        "or","pa","ri","sc","sd","tn","tx","ut","vt","va","wa","wv",
        "wi","wy","dc",
        # Common dot-abbrevations
        "miss.","pa.","mass.","mich.","conn.","tenn.","ill.","ala.",
        "ark.","colo.","del.","fla.","ga.","ind.","kan.","ky.","la.",
        "me.","md.","minn.","mo.","mont.","neb.","nev.","n.h.","n.j.",
        "n.m.","n.y.","n.c.","n.d.","o.h.","okla.","ore.","r.i.","s.c.",
        "s.d.","tex.","vt.","va.","w.va.","wis.","wyo.",
        # Canadian provinces
        "ontario","quebec","british columbia","alberta","nova scotia",
        "new brunswick","manitoba","saskatchewan","prince edward island",
        "newfoundland","northwest territories","nunavut","yukon",
        # Australian states
        "new south wales","victoria","queensland","western australia",
        "south australia","tasmania","northern territory",
        # Other states/provinces
        "bali","sicily","normandy","tibet","andalusia","catalonia","bavaria",
        "tuscany","lombardy","veneto","sardinia","corsica","brittany","alsace",
        "lorraine","provence","champagne","burgundy","flanders","wallonia",
        "transylvania","crimea","donetsk","chechnya","dagestan","siberia",
        "kashmir","punjab","sindh","balochistan","kerala","maharashtra",
        "rajasthan","uttar pradesh","bihar","west bengal","tamil nadu",
        "karnataka","andhra pradesh","gujarat","madhya pradesh",
        "okinawa","hokkaido","kyushu","honshu","shikoku",
        "guangdong","yunnan","sichuan","xinjiang","tibet","inner mongolia",
        "catalonia","basque country","galicia","aragon","castile",
        "new england",  # US region / historical
    ]},
    # ── Regions (geographic / historical / sub-city) ──────────────────────────
    **{k: "Region" for k in [
        "americas","latin america","south america","central america",
        "north america","middle east","near east","far east","east asia",
        "southeast asia","south asia","central asia","sub-saharan africa",
        "north africa","east africa","west africa","southern africa",
        "the balkans","balkans","scandinavia","the mediterranean","mediterranean",
        "the caribbean","caribbean","the pacific","pacific","polynesia",
        "the atlantic","atlantic","europe","asia","africa","oceania",
        "the arctic","arctic","antarctic","antarctica",
        "the alps","alps","the andes","andes","the himalayas","himalayas",
        "the amazon","amazon","the sahara","sahara",
        "the nile","thames","mississippi river","amazon river",
        "long island","staten island","cape cod","the hamptons","hamptons",
        "bay area","silicon valley","the valley","san fernando valley",
        "wall street","fifth avenue","main street","broadway","the strip",
        "yorkshire","cornwall","the midlands","the north","the south",
        "new england","the midwest","the west","the east coast","the south",
        "the deep south","appalachia","the rust belt","the bible belt",
        "the pacific northwest","the southwest","the northeast",
        "the riviera","french riviera","amalfi coast","dalmatian coast",
        "the black sea","the caspian sea","persian gulf","red sea",
        "the aegean","aegean sea","the adriatic","adriatic sea",
        "great barrier reef","the outback","outback",
        "holy land","promised land","fertile crescent",
        "the west bank","west bank","the gaza strip","gaza",
        "soviet union","eastern europe","western europe","central europe",
        "the third world","the developing world",
        # Islands / archipelagos / territories
        "tahiti","bali","sicily","corsica","sardinia","mallorca","ibiza",
        "canary islands","azores","madeira","cape verde islands",
        "hawaii islands","caribbean islands","west indies","antilles",
        "normandy","brittany","alsace","lorraine","champagne","burgundy",
        "tibet","kashmir","crimea","siberia","manchuria","mesopotamia",
        "transylvania","the caucasus","caucasus","the levant","levant",
        "sub-saharan","horn of africa","great plains","great lakes",
        "rocky mountains","sierra nevada","appalachian","ozarks",
        "the bronx","queens","harlem","brooklyn",  # NYC boroughs
    ]},
}

# Variants / abbreviations that resolve to the same type
_LOC_ALIASES: dict[str, str] = {
    # US (country variants)
    "us": "Country", "u.s.": "Country", "u.s.a.": "Country", "usa": "Country",
    "united states": "Country", "the united states": "Country",
    "the united states of america": "Country", "states": "Country",
    "uk": "Country", "u.k.": "Country", "britain": "Country",
    "great britain": "Country", "the soviet union": "Country",
    "soviet union": "Country", "ussr": "Country",
    "nam": "Country",        # Vietnam (slang)
    "arabia": "Country",     # Saudi Arabia shorthand
    "holland": "Country",    # Netherlands
    # City aliases / abbreviations
    "la": "City", "l.a.": "City", "la.": "City",
    "nyc": "City", "n.y.c.": "City", "new york's": "City",
    "dc": "City", "d.c.": "City",
    "philly": "City", "frisco": "City", "chi": "City", "chi-town": "City",
    "rio": "City", "bombay": "City", "calcutta": "City", "saigon": "City",
    "leningrad": "City", "petrograd": "City", "stalingrad": "City",
    "peking": "City", "canton": "City", "nanking": "City",
    "rangoon": "City", "edo": "City", "byzantium": "City",
    "new york": "City", "new york city": "City",
    "hong kong": "City", "macau": "City",
    "beverly": "City",       # Beverly Hills shorthand
    "vegas": "City",         # Las Vegas shorthand
    "roma": "City",          # Rome in Italian/Spanish
    "oakland": "City",
    "niagara falls": "City",
    "albany": "City",
    "bethlehem": "City",
    "woodstock": "City",
    "chico": "City",
    "marietta": "City",
    "newton": "City",
    "springfield": "City",
    "marion": "City",
    "laurel": "City",
    "jersey city": "City",
    "jersey": "State",       # usually New Jersey in US context
    "carolina": "State",     # North or South Carolina
    # State abbreviations (single-letter ambiguous ones already in _LOC_TYPES)
    "miss.": "State", "pa.": "State", "mass.": "State", "md": "State",
    "mo": "State", "pa": "State",
    # Historical country names
    "persia": "Country", "siam": "Country", "ceylon": "Country",
    "rhodesia": "Country", "zaire": "Country", "abyssinia": "Country",
    "burma": "Country",
    # Noise / non-geographic — explicit overrides
    "america": "Country",  # usually means USA in movie context
    # Missing countries
    "tunisia": "Country", "greenland": "Country", "east germany": "Country",
    "east pakistan": "Country", "the united kingdom": "Country",
    "west germany": "Country", "north vietnam": "Country",
    "south vietnam": "Country", "the republic of ireland": "Country",
    # Missing cities
    "louisville": "City", "aspen": "City", "princeton": "City",
    "chernobyl": "City", "jericho": "City", "fort knox": "City",
    "san quentin": "City", "eureka": "City", "washington dc": "City",
    "washington, d.c.": "City", "washington, dc": "City",
    "goa": "State",     # Indian state
    "b.c.": "State",    # British Columbia
    "bc": "State",
    "bengal": "Region", "gibraltar": "Region",
    "east berlin": "City", "west berlin": "City",
    "st. tropez": "City", "monte carlo": "City",
}


def _classify_location(loc: str) -> str:
    """Classify a location string into Country/City/State/Region/Other."""
    key = loc.strip().lower()
    # Direct alias lookup first
    if key in _LOC_ALIASES:
        return _LOC_ALIASES[key]
    # Main lookup
    if key in _LOC_TYPES:
        return _LOC_TYPES[key]
    # Heuristic: all-caps usually a noisy duplicate → check lowered
    lower = key.lower()
    if lower in _LOC_TYPES:
        return _LOC_TYPES[lower]
    # Partial patterns: "New York's" → strip possessive
    stripped = key.rstrip("'s").rstrip("s'").strip()
    if stripped in _LOC_TYPES:
        return _LOC_TYPES[stripped]
    return "Other"


def _load_locations() -> list[dict]:
    """One row per (location, movie): location name, mention count, imdbid, title, country."""
    try:
        con = _new_db()
        rows = con.execute("""
            SELECT la.LOCATION, la.MENTIONS, mi.IMDBID, mi.TITLE, fc.COUNTRY
            FROM (
                SELECT sg.IMDB, sg.LOCATION, SUM(sg.COUNT) AS MENTIONS
                FROM subtitle_geo sg
                GROUP BY sg.IMDB, sg.LOCATION
                HAVING SUM(sg.COUNT) >= 2
            ) la
            JOIN ml_imdb    mli ON mli.IMDBID = la.IMDB
            JOIN movie_imdb mi  ON mi.MOVIEID = mli.MOVIEID
                               AND mi.TYPE     = 'movie'
                               AND mi.RESPONSE = 'true'
            LEFT JOIN (
                SELECT IMDBID, COUNTRY,
                       ROW_NUMBER() OVER (PARTITION BY IMDBID) AS rn
                FROM movie_country
            ) fc ON fc.IMDBID = mi.IMDBID AND fc.rn = 1
            ORDER BY la.MENTIONS DESC
            LIMIT 200000
        """).fetchall()
        con.close()
        result = [
            {
                "location": r[0],
                "locType":  _classify_location(r[0]),
                "mentions": int(r[1]),
                "imdbid":   r[2],
                "title":    r[3],
                "country":  r[4] or "Unknown",
            }
            for r in rows
        ]
        print(f"[CineMap] {len(result)} location entries loaded")
        return result
    except Exception as e:
        print(f"[CineMap] WARNING: could not load locations: {e}")
        return []


def _load_films() -> list[dict]:
    con = _new_db()

    # ISO-3 code → (country_name, continent, region)
    nat: dict[str, tuple] = {
        r[0]: (r[1], r[2], r[3])
        for r in con.execute(
            "SELECT ISO, COUNTRY, CONTINENT, REGION FROM country WHERE ISO IS NOT NULL"
        ).fetchall()
    }

    films: list[dict] = []
    cur = con.execute(_FILMS_QUERY)
    cols = [d[0] for d in cur.description]
    for raw in cur.fetchall():
            r = dict(zip(cols, raw))

            rating = _float(r["IMDBRATING"])
            if rating is None:
                continue

            # Country / continent / region
            country   = r["COUNTRY"] or (r["IMDB_COUNTRY_RAW"] or "").split(",")[0].strip() or "Unknown"
            continent = r["CONTINENT"] or "Other"
            region    = r["REGION"] or ""

            # Genre
            ml_g   = r["ML_GENRE"]
            imdb_g = r["IMDB_GENRE"] or (r["IMDB_GENRE_RAW"] or "").split(",")[0].strip() or None
            genre  = ml_g or imdb_g or "Other"

            # Awards (Parquet stores as DOUBLE — convert to int)
            osc_w = int(r["OSCAR_WINNING"]    or 0)
            osc_n = int(r["OSCAR_NOMINATION"] or 0)
            aw_w  = int(r["AWARD_WINNING"]    or 0)
            aw_n  = int(r["AWARD_NOMINATION"] or 0)
            ba_w  = int(r["BAFTA_WINNING"]    or 0)
            ba_n  = int(r["BAFTA_NOMINATION"] or 0)
            em_w  = int(r["EMMY_WINNING"]     or 0)
            em_n  = int(r["EMMY_NOMINATION"]  or 0)
            other_awards = max(0, aw_w - osc_w) + max(0, aw_n - osc_n) + ba_w + ba_n + em_w + em_n

            year = int(r["YEAR"]) if r["YEAR"] else None

            # Director nationality → country/region lookup
            dn      = nat.get(r["DIR_NAT"] or "", (None, None, None))
            dir_age = (year - int(r["DIR_BY"])) if year and r["DIR_BY"] else None

            # Writer nationality → country/region lookup
            wn      = nat.get(r["WRI_NAT"] or "", (None, None, None))
            wri_age = (year - int(r["WRI_BY"])) if year and r["WRI_BY"] else None

            genres_all = r["ALL_GENRES"] or (r["IMDB_GENRE_RAW"] or "").replace(",", ", ") or genre

            films.append({
                "imdbid":        r["IMDBID"],
                "movieid":       r["MOVIEID"],
                "title":         r["TITLE"],
                "director":      r["DIR_NAME"] or "",
                "directorid":    r["DIR_ID"],
                "directorsAll":  r["ALL_DIRS"] or r["DIR_NAME"] or "",
                "year":          year,
                "country":       country,
                "countriesAll":  r["ALL_COUNTRIES"] or country,
                "genre":         genre,
                "genresAll":     genres_all.strip() if genres_all else genre,
                "mlGenre":     ml_g or genre,
                "imdbGenre":   imdb_g or genre,
                "rating":      rating,
                "box":         _box(r["BOXOFFICE"]),
                "continent":   continent,
                "region":      region,
                "ratingImdb":  rating,
                "ratingMl":    round(rating / 2.0, 1),
                "votesImdb":   _int(r["IMDBVOTES"]),
                "votesMl":     int(r["VOTES_ML"]) if r["VOTES_ML"] else 0,
                "oscars":      osc_w,
                "otherAwards": other_awards,
                "dir": {
                    "gender":  _gender(r["DIR_GENDER"]),
                    "race":    _race(r["DIR_RACE"]),
                    "country": dn[0] or country,
                    "region":  dn[2] or region,
                    "age":     dir_age,
                },
                "wri": {
                    "name":    r["WRI_NAME"] or "",
                    "id":      r["WRI_ID"],
                    "gender":  _gender(r["WRI_GENDER"]),
                    "race":    _race(r["WRI_RACE"]),
                    "country": wn[0] or country,
                    "region":  wn[2] or region,
                    "age":     wri_age,
                },
            })

    con.close()
    print(f"[CineMap] {len(films)} films loaded from Parquet")
    return films


# ── FastAPI app ───────────────────────────────────────────────────────────────

def _load_all_data() -> None:
    global _FILMS, _RATINGS_DIST, _LOCATIONS, _READY
    print("[CineMap] Loading films from Parquet…")
    _FILMS = _load_films()
    _RATINGS_DIST = _load_ratings_dist()
    print("[CineMap] Loading location data…")
    _LOCATIONS = _load_locations()
    _READY = True
    print("[CineMap] All data loaded — ready to serve.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start data loading in background so the server binds to the port immediately.
    # Cloud Run health checks will see /health return 503 until _READY = True.
    threading.Thread(target=_load_all_data, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    from fastapi.responses import JSONResponse
    if not _READY:
        return JSONResponse(status_code=503, content={"status": "loading"})
    return {"status": "ok"}


@app.get("/api/films")
def api_films():
    return _FILMS


@app.get("/api/ratings-dist")
def api_ratings_dist():
    return _RATINGS_DIST


@app.get("/api/locations")
def api_locations():
    return _LOCATIONS


@app.get("/api/themes/options")
def api_themes_options():
    """Idioms, themes per idiom, words per idiom+theme — for sidebar selects."""
    con = _new_db()
    rows = con.execute("""
        SELECT DISTINCT st.IDIOM, st.THEME, st.WORD
        FROM subtitle_theme st
        JOIN ml_imdb    mli ON mli.IMDBID = st.IMDB
        JOIN movie_imdb mi  ON mi.MOVIEID = mli.MOVIEID
                           AND mi.TYPE = 'movie' AND mi.RESPONSE = 'true'
        WHERE st.IDIOM IS NOT NULL
        GROUP BY st.IDIOM, st.THEME, st.WORD
        HAVING SUM(st.COUNT) >= 3
        ORDER BY st.IDIOM, st.THEME, st.WORD
    """).fetchall()
    con.close()

    idioms: set[str] = set()
    themes_by_idiom: dict[str, set] = {}
    words_by_theme: dict[str, dict] = {}
    for idiom, theme, word in rows:
        idioms.add(idiom)
        themes_by_idiom.setdefault(idiom, set()).add(theme)
        words_by_theme.setdefault(idiom, {}).setdefault(theme, set()).add(word)

    return {
        "idioms": sorted(idioms),
        "themes_by_idiom": {k: sorted(v) for k, v in themes_by_idiom.items()},
        "words_by_theme": {
            k: {t: sorted(w) for t, w in v.items()}
            for k, v in words_by_theme.items()
        },
    }


@app.get("/api/themes/filter")
def api_themes_filter(
    idiom: str = "",
    theme: str = "",
    word: str = "",
    sort: str = "mentions",
    dir: str = "desc",
    page: int = 0,
    size: int = 50,
):
    """Server-side filtered theme rows queried on demand from Parquet via DuckDB."""
    where_parts = ["SUM(st.COUNT) >= 3"]
    params: list = []
    if idiom:
        where_parts.append("st.IDIOM = ?")
        params.append(idiom)
    if theme:
        where_parts.append("st.THEME = ?")
        params.append(theme)
    if word:
        where_parts.append("st.WORD = ?")
        params.append(word)
    having = " AND ".join(where_parts)

    base_sql = f"""
        SELECT st.IDIOM AS idiom, st.THEME AS theme, st.WORD AS word,
               SUM(st.COUNT) AS mentions,
               mi.IMDBID AS imdbid, mi.TITLE AS title,
               COALESCE(fc.COUNTRY, 'Unknown') AS country
        FROM subtitle_theme st
        JOIN ml_imdb    mli ON mli.IMDBID = st.IMDB
        JOIN movie_imdb mi  ON mi.MOVIEID = mli.MOVIEID
                           AND mi.TYPE = 'movie' AND mi.RESPONSE = 'true'
        LEFT JOIN (
            SELECT IMDBID, COUNTRY, ROW_NUMBER() OVER (PARTITION BY IMDBID) AS rn
            FROM movie_country
        ) fc ON fc.IMDBID = mi.IMDBID AND fc.rn = 1
        GROUP BY st.IDIOM, st.THEME, st.WORD, mi.IMDBID, mi.TITLE, fc.COUNTRY
        HAVING {having}
    """

    valid_sort = {"mentions", "title", "idiom", "theme", "word"}
    sk = sort if sort in valid_sort else "mentions"
    order = f"{sk} {'ASC' if dir == 'asc' else 'DESC'}"

    con = _new_db()

    # Paginated rows
    page_rows_raw = con.execute(
        f"SELECT * FROM ({base_sql}) ORDER BY {order} LIMIT ? OFFSET ?",
        params + [size, page * size],
    ).fetchall()
    cols = ["idiom", "theme", "word", "mentions", "imdbid", "title", "country"]
    page_rows = [dict(zip(cols, r)) for r in page_rows_raw]

    total = con.execute(
        f"SELECT COUNT(*) FROM ({base_sql})", params
    ).fetchone()[0]

    film_ids = [r[0] for r in con.execute(
        f"SELECT DISTINCT imdbid FROM ({base_sql})", params
    ).fetchall()]

    country_rows = con.execute(
        f"SELECT country, SUM(mentions) FROM ({base_sql}) GROUP BY country ORDER BY 2 DESC",
        params,
    ).fetchall()
    country_m = {r[0]: int(r[1]) for r in country_rows}

    theme_rows = con.execute(
        f"SELECT theme, COUNT(DISTINCT imdbid) AS n FROM ({base_sql}) GROUP BY theme ORDER BY n DESC LIMIT 15",
        params,
    ).fetchall()
    theme_stats = [{"theme": r[0], "n": int(r[1])} for r in theme_rows]

    con.close()

    return {
        "total":           total,
        "film_ids":        film_ids,
        "rows":            page_rows,
        "country_mentions": country_m,
        "theme_stats":     theme_stats,
    }


# Static files served last so API routes take priority
app.mount("/", StaticFiles(directory=".", html=True), name="static")
