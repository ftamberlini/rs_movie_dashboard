"""FastAPI backend — CineMap dashboard serving Oracle film data."""
import os
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv
import oracledb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

WALLET_DIR = os.path.abspath(os.getenv("ORACLE_WALLET_DIR", "./oracle"))


def _conn():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN"),
        config_dir=WALLET_DIR,
        wallet_location=WALLET_DIR,
        wallet_password=os.getenv("ORACLE_WALLET_PASSWORD"),
    )


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


# ── Main query ────────────────────────────────────────────────────────────────
# One CTE query: LEFT JOINs country (via ISO code, fallback to name),
# genres, director, writer — one row per movie (ROW_NUMBER rn=1).

_QUERY = """\
WITH
  m AS (
    SELECT IMDBID, TITLE, YEAR, IMDBRATING, IMDBVOTES, BOXOFFICE,
           OSCAR_WINNING, OSCAR_NOMINATION,
           AWARD_WINNING, AWARD_NOMINATION,
           BAFTA_WINNING, BAFTA_NOMINATION,
           EMMY_WINNING,  EMMY_NOMINATION,
           GENRE AS IMDB_GENRE_RAW,
           COUNTRY AS IMDB_COUNTRY_RAW,
           MOVIEID
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
           ROW_NUMBER() OVER (PARTITION BY mc.IMDBID ORDER BY mc.ROWID) rn
    FROM movie_country mc
    LEFT JOIN country ci ON ci.ISO     = mc.ISO
    LEFT JOIN country cn ON cn.COUNTRY = mc.COUNTRY AND ci.ISO IS NULL
    JOIN m ON m.IMDBID = mc.IMDBID
  ),
  fg AS (
    SELECT mg.MOVIEID, mg.GENRE,
           ROW_NUMBER() OVER (PARTITION BY mg.MOVIEID ORDER BY mg.ROWID) rn
    FROM movie_ml_genre mg
    JOIN m ON m.MOVIEID = mg.MOVIEID
  ),
  fi AS (
    SELECT ig.IMDBID, ig.GENRE,
           ROW_NUMBER() OVER (PARTITION BY ig.IMDBID ORDER BY ig.ROWID) rn
    FROM movie_imdb_genre ig
    JOIN m ON m.IMDBID = ig.IMDBID
  ),
  fd AS (
    SELECT md.IMDBID,
           d.NAME, d.GENDER, d.GENDER_LLM, d.RACE, d.BIRTHYEAR, d.NATIONALITY,
           ROW_NUMBER() OVER (PARTITION BY md.IMDBID ORDER BY md.ROWID) rn
    FROM movie_director md
    JOIN director d ON d.DIRECTORID = md.DIRECTORID
    JOIN m          ON m.IMDBID     = md.IMDBID
  ),
  fw AS (
    SELECT mw.IMDBID,
           w.NAME, w.GENDER, w.RACE, w.BIRTHYEAR, w.NATIONALITY,
           ROW_NUMBER() OVER (PARTITION BY mw.IMDBID ORDER BY mw.ROWID) rn
    FROM movie_writer mw
    JOIN writer w ON w.WRITERID = mw.WRITERID
    JOIN m        ON m.IMDBID   = mw.IMDBID
  )
SELECT
  m.IMDBID, m.TITLE, m.YEAR,
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
  fd.NAME        AS DIR_NAME,
  fd.RACE        AS DIR_RACE,
  fd.BIRTHYEAR   AS DIR_BY,
  fd.NATIONALITY AS DIR_NAT,
  fw.NAME        AS WRI_NAME,
  fw.GENDER      AS WRI_GENDER,
  fw.RACE        AS WRI_RACE,
  fw.BIRTHYEAR   AS WRI_BY,
  fw.NATIONALITY AS WRI_NAT
FROM m
LEFT JOIN fc ON fc.IMDBID  = m.IMDBID  AND fc.rn = 1
LEFT JOIN fg ON fg.MOVIEID = m.MOVIEID AND fg.rn = 1
LEFT JOIN fi ON fi.IMDBID  = m.IMDBID  AND fi.rn = 1
LEFT JOIN fd ON fd.IMDBID  = m.IMDBID  AND fd.rn = 1
LEFT JOIN fw ON fw.IMDBID  = m.IMDBID  AND fw.rn = 1
ORDER BY m.TITLE
"""


# ── Cache ─────────────────────────────────────────────────────────────────────
_FILMS: list[dict] = []


def _load_films() -> list[dict]:
    conn = _conn()

    # ISO-3 code → (country_name, continent, region)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ISO, COUNTRY, CONTINENT, REGION FROM country WHERE ISO IS NOT NULL"
        )
        nat: dict[str, tuple] = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}

    films: list[dict] = []
    with conn.cursor() as cur:
        cur.execute(_QUERY)
        cols = [d[0] for d in cur.description]
        for raw in cur:
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

            # Awards
            osc_w = r["OSCAR_WINNING"]    or 0
            osc_n = r["OSCAR_NOMINATION"] or 0
            aw_w  = r["AWARD_WINNING"]    or 0
            aw_n  = r["AWARD_NOMINATION"] or 0
            ba_w  = r["BAFTA_WINNING"]    or 0
            ba_n  = r["BAFTA_NOMINATION"] or 0
            em_w  = r["EMMY_WINNING"]     or 0
            em_n  = r["EMMY_NOMINATION"]  or 0
            other_awards = max(0, aw_w - osc_w) + max(0, aw_n - osc_n) + ba_w + ba_n + em_w + em_n

            # Director nationality → country/region lookup
            dn      = nat.get(r["DIR_NAT"] or "", (None, None, None))
            dir_age = (r["YEAR"] - r["DIR_BY"]) if r["YEAR"] and r["DIR_BY"] else None

            # Writer nationality → country/region lookup
            wn      = nat.get(r["WRI_NAT"] or "", (None, None, None))
            wri_age = (r["YEAR"] - r["WRI_BY"]) if r["YEAR"] and r["WRI_BY"] else None

            films.append({
                "imdbid":      r["IMDBID"],
                "title":       r["TITLE"],
                "director":    r["DIR_NAME"] or "",
                "year":        r["YEAR"],
                "country":     country,
                "genre":       genre,
                "mlGenre":     ml_g or genre,
                "imdbGenre":   imdb_g or genre,
                "rating":      rating,
                "box":         _box(r["BOXOFFICE"]),
                "continent":   continent,
                "region":      region,
                "ratingImdb":  rating,
                "ratingMl":    round(rating / 2.0, 1),
                "votesImdb":   _int(r["IMDBVOTES"]),
                "votesMl":     0,
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
                    "gender":  _gender(r["WRI_GENDER"]),
                    "race":    _race(r["WRI_RACE"]),
                    "country": wn[0] or country,
                    "region":  wn[2] or region,
                    "age":     wri_age,
                },
            })

    conn.close()
    print(f"[CineMap] {len(films)} films loaded from Oracle")
    return films


# ── FastAPI app ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _FILMS
    print("[CineMap] Loading films from Oracle…")
    _FILMS = _load_films()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/films")
def api_films():
    return _FILMS


@app.get("/api/reload")
def api_reload():
    global _FILMS
    _FILMS = _load_films()
    return {"loaded": len(_FILMS)}


# Static files served last so API routes take priority
app.mount("/", StaticFiles(directory=".", html=True), name="static")
