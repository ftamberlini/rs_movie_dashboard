/* CineMap Dashboard — app.js (vanilla JS, no framework)
   Loads d3 + topojson (CDN) and country-data.js (window.CINEMAP_COUNTRY_ROWS). */
(function () {
  'use strict';

  /* ---------------- Data ---------------- */
  var GENRE_COLORS = {
    'Drama':'#efa838','Romance':'#5b9bf0','Thriller':'#a06bf0','Horror':'#3fbf9a',
    'Comedy':'#ef6b8b','Action':'#ef5b5b','Sci-Fi':'#3fc7df','Fantasy':'#b6d94c',
    'Animation':'#df5bc7','Documentary':'#9aa6b8'
  };
  var ML_GENRES = ['Action','Adventure','Animation','Children','Comedy','Crime','Documentary','Drama','Fantasy','Film-Noir','Horror','IMAX','Musical','Mystery','Romance','Sci-Fi','Thriller','War','Western','(no genres listed)'];
  var IMDB_GENRES = ['Action','Adult','Adventure','Animation','Biography','Children','Comedy','Crime','Documentary','Drama','Family','Fantasy','Film-Noir','Game-Show','History','Horror','Music','Musical','Mystery','News','Reality-TV','Romance','Sci-Fi','Short','Sport','Talk-Show','Thriller','War','Western'];
  var YEARS = []; // populated from Oracle data after load
  var RATINGS_DIST = []; // [{rating, votes}] from /api/ratings-dist
  var GENDERS = ['Male','Female','Unknown'];
  var RACES = ['WHITE','ASIAN','BLACK','INDIGENOUS','MIXED-RACE','UNKNOWN'];
  var RACE_COLORS = {WHITE:'#cdbba0',ASIAN:'#e0b54a',BLACK:'#7a5a48',INDIGENOUS:'#cf6a3c','MIXED-RACE':'#b98a5e',UNKNOWN:'#8b97a8'};
  var MALE_C = '#34a9e0', FEMALE_C = '#ef5b7b';

  var COORDS = {
    // North America
    'United States':{lng:-98.6,lat:39.8},'Canada':{lng:-106,lat:56},'Mexico':{lng:-102,lat:23.5},
    // Europe
    'United Kingdom':{lng:-2,lat:53},'France':{lng:2.4,lat:46.6},'Germany':{lng:10.4,lat:51},
    'Italy':{lng:12.6,lat:42.8},'Spain':{lng:-3.7,lat:40.2},'Netherlands':{lng:5.3,lat:52.1},
    'Belgium':{lng:4.5,lat:50.8},'Sweden':{lng:18.1,lat:59.3},'Denmark':{lng:10.0,lat:56.0},
    'Norway':{lng:10.7,lat:59.9},'Finland':{lng:25.7,lat:61.9},'Poland':{lng:19.1,lat:52.1},
    'Russia':{lng:37.6,lat:55.8},'Austria':{lng:14.5,lat:47.5},'Switzerland':{lng:8.3,lat:46.9},
    'Czechia':{lng:15.5,lat:49.8},'Hungary':{lng:19.0,lat:47.5},'Romania':{lng:24.9,lat:45.9},
    'Portugal':{lng:-8.2,lat:39.4},'Greece':{lng:21.8,lat:39.1},'Ireland':{lng:-8.2,lat:53.1},
    'Ukraine':{lng:30.5,lat:50.5},'Turkey':{lng:35.2,lat:38.9},'Israel':{lng:34.9,lat:31.5},
    'Serbia':{lng:21.0,lat:44.0},'Croatia':{lng:15.9,lat:45.1},'Bulgaria':{lng:25.5,lat:42.7},
    'Slovakia':{lng:19.3,lat:48.7},'Slovenia':{lng:14.8,lat:46.1},'Lithuania':{lng:23.9,lat:55.2},
    'Latvia':{lng:24.1,lat:56.9},'Estonia':{lng:24.7,lat:58.6},'Iceland':{lng:-18.2,lat:64.9},
    'Luxembourg':{lng:6.1,lat:49.8},'Moldova':{lng:28.4,lat:47.0},'Albania':{lng:20.2,lat:41.3},
    // Asia
    'Japan':{lng:138.3,lat:36.2},'South Korea':{lng:127.8,lat:36.5},'India':{lng:79,lat:22},
    'China':{lng:104.2,lat:35.9},'Hong Kong':{lng:114.2,lat:22.3},'Taiwan':{lng:120.9,lat:23.7},
    'Thailand':{lng:100.5,lat:13.8},'Vietnam':{lng:108.3,lat:14.1},'Indonesia':{lng:113.9,lat:-0.8},
    'Philippines':{lng:122.6,lat:12.9},'Malaysia':{lng:109.7,lat:4.2},'Singapore':{lng:103.8,lat:1.4},
    'Iran':{lng:53.7,lat:32.4},'Kazakhstan':{lng:66.9,lat:48.0},'Pakistan':{lng:69.3,lat:30.4},
    'Bangladesh':{lng:90.4,lat:23.7},'Sri Lanka':{lng:80.7,lat:7.9},'Cambodia':{lng:104.9,lat:12.6},
    'Mongolia':{lng:106.9,lat:47.9},'Nepal':{lng:84.1,lat:28.4},'Lebanon':{lng:35.5,lat:33.9},
    'Jordan':{lng:36.2,lat:31.0},'Saudi Arabia':{lng:45.1,lat:23.9},'United Arab Emirates':{lng:53.8,lat:23.4},
    'Georgia':{lng:43.4,lat:42.3},'Armenia':{lng:44.5,lat:40.2},'Azerbaijan':{lng:47.6,lat:40.1},
    'Uzbekistan':{lng:63.1,lat:41.4},'Tajikistan':{lng:71.3,lat:38.9},'Kyrgyzstan':{lng:74.6,lat:41.2},
    'Myanmar':{lng:96.1,lat:17.1},'Afghanistan':{lng:67.7,lat:33.9},
    // Latin America
    'Brazil':{lng:-51,lat:-12},'Argentina':{lng:-63,lat:-36},'Colombia':{lng:-74.1,lat:4.7},
    'Chile':{lng:-70.7,lat:-33.5},'Peru':{lng:-77.0,lat:-12.0},'Venezuela':{lng:-66.9,lat:10.5},
    'Bolivia':{lng:-64.7,lat:-17.1},'Ecuador':{lng:-78.1,lat:-1.8},'Paraguay':{lng:-58.4,lat:-23.4},
    'Uruguay':{lng:-56.2,lat:-32.5},'Cuba':{lng:-79.5,lat:21.5},'Puerto Rico':{lng:-66.5,lat:18.2},
    'Costa Rica':{lng:-84.1,lat:9.8},'Guatemala':{lng:-90.3,lat:15.8},'Dominican Republic':{lng:-70.2,lat:19.0},
    // Africa
    'South Africa':{lng:25.1,lat:-29.0},'Nigeria':{lng:8.7,lat:9.1},'Egypt':{lng:30.8,lat:26.8},
    'Kenya':{lng:37.9,lat:0.0},'Morocco':{lng:-7.1,lat:31.8},'Ethiopia':{lng:40.5,lat:9.1},
    'Ghana':{lng:-1.0,lat:7.9},'Tanzania':{lng:34.9,lat:-6.4},'Senegal':{lng:-14.5,lat:14.5},
    'Cameroon':{lng:12.4,lat:5.7},'Tunisia':{lng:9.6,lat:33.9},'Algeria':{lng:2.6,lat:28.0},
    "Côte d'Ivoire":{lng:-5.6,lat:7.5},'Democratic Republic of the Congo':{lng:23.7,lat:-4.0},
    // Oceania
    'Australia':{lng:133,lat:-25},'New Zealand':{lng:172.5,lat:-41.3}
  };

  // ISO 3166-1 numeric → country name (matches Oracle country names)
  var ISO_NUM = {
    4:'Afghanistan',8:'Albania',12:'Algeria',24:'Angola',32:'Argentina',36:'Australia',
    40:'Austria',50:'Bangladesh',56:'Belgium',64:'Bhutan',68:'Bolivia',76:'Brazil',
    100:'Bulgaria',104:'Myanmar',116:'Cambodia',120:'Cameroon',124:'Canada',152:'Chile',
    156:'China',170:'Colombia',178:'Republic of the Congo',
    180:'Democratic Republic of the Congo',188:'Costa Rica',191:'Croatia',192:'Cuba',
    196:'Cyprus',203:'Czechia',208:'Denmark',214:'Dominican Republic',218:'Ecuador',
    818:'Egypt',231:'Ethiopia',246:'Finland',250:'France',268:'Georgia',276:'Germany',
    288:'Ghana',300:'Greece',320:'Guatemala',332:'Haiti',344:'Hong Kong',348:'Hungary',
    356:'India',360:'Indonesia',364:'Iran',368:'Iraq',372:'Ireland',376:'Israel',
    380:'Italy',388:'Jamaica',392:'Japan',400:'Jordan',398:'Kazakhstan',404:'Kenya',
    408:'North Korea',410:'South Korea',417:'Kyrgyzstan',418:'Laos',422:'Lebanon',
    428:'Latvia',440:'Lithuania',442:'Luxembourg',450:'Madagascar',458:'Malaysia',
    484:'Mexico',496:'Mongolia',504:'Morocco',516:'Namibia',524:'Nepal',528:'Netherlands',
    554:'New Zealand',566:'Nigeria',578:'Norway',586:'Pakistan',591:'Panama',
    600:'Paraguay',604:'Peru',608:'Philippines',616:'Poland',620:'Portugal',634:'Qatar',
    642:'Romania',643:'Russia',646:'Rwanda',682:'Saudi Arabia',686:'Senegal',
    694:'Sierra Leone',702:'Singapore',703:'Slovakia',705:'Slovenia',706:'Somalia',
    710:'South Africa',724:'Spain',144:'Sri Lanka',752:'Sweden',756:'Switzerland',
    158:'Taiwan',762:'Tajikistan',764:'Thailand',788:'Tunisia',792:'Turkey',800:'Uganda',
    804:'Ukraine',784:'United Arab Emirates',826:'United Kingdom',840:'United States',
    858:'Uruguay',860:'Uzbekistan',704:'Vietnam',887:'Yemen',716:'Zimbabwe',
    384:"Côte d'Ivoire",233:'Estonia',862:'Venezuela',630:'Puerto Rico',
    312:'Guadeloupe',474:'Martinique',470:'Malta',492:'Monaco',480:'Mauritius'
  };

  var FILMS = []; // populated from /api/films on load

  /* Option data from country-data.js (fallback to film-derived) */
  function optionData() {
    var rows = window.CINEMAP_COUNTRY_ROWS;
    if (rows && rows.length) {
      return {
        conts: uniqSort(rows.map(function (r) { return r[1]; })),
        regs: uniqSort(rows.map(function (r) { return r[2]; })),
        countries: rows.map(function (r) { return r[0]; }).sort(function (a, b) { return a.localeCompare(b); })
      };
    }
    return {
      conts: uniqSort(FILMS.map(function (f) { return f.continent; })),
      regs: uniqSort(FILMS.map(function (f) { return f.region; })),
      countries: uniqSort(FILMS.map(function (f) { return f.country; }))
    };
  }
  function uniqSort(a) { return Array.from(new Set(a)).sort(); }

  /* ---------------- State ---------------- */
  var PAGE_SIZE = 50;
  var state = {
    tab: 'map', search: '',
    mlGenres: [], imdbGenres: [], years: [], continents: [], regions: [], countries: [],
    dirGenders: [], dirRaces: [], dirRegions: [], dirCountries: [],
    wriGenders: [], wriRaces: [], wriRegions: [], wriCountries: [],
    open: { film: true, director: false, writer: false },
    sortKey: 'title', sortDir: 'asc',
    tablePage: 0
  };
  var OD = optionData();

  /* ---------------- Helpers ---------------- */
  function el(tag, props, children) {
    var e = document.createElement(tag);
    if (props) for (var k in props) {
      if (k === 'class') e.className = props[k];
      else if (k === 'html') e.innerHTML = props[k];
      else if (k === 'text') e.textContent = props[k];
      else if (k === 'style') e.style.cssText = props[k];
      else if (k.indexOf('on') === 0 && typeof props[k] === 'function') e.addEventListener(k.slice(2).toLowerCase(), props[k]);
      else if (props[k] != null) e.setAttribute(k, props[k]);
    }
    if (children != null) (Array.isArray(children) ? children : [children]).forEach(function (c) {
      if (c == null) return;
      e.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return e;
  }
  function fmtMoney(m) { return m >= 1000 ? '$' + (m / 1000).toFixed(2) + 'B' : '$' + Math.round(m) + 'M'; }
  function fmtVotes(n) { if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'; if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'; return String(n); }
  function colorOf(g) { return GENRE_COLORS[g] || '#9aa6b8'; }
  function $(id) { return document.getElementById(id); }

  /* ---------------- Filtering ---------------- */
  function filterFilms() {
    var s = state, q = (s.search || '').trim().toLowerCase();
    return FILMS.filter(function (f) {
      if (q && f.title.toLowerCase().indexOf(q) < 0 && f.director.toLowerCase().indexOf(q) < 0) return false;
      if (s.mlGenres.length && s.mlGenres.indexOf(f.mlGenre) < 0) return false;
      if (s.imdbGenres.length && s.imdbGenres.indexOf(f.imdbGenre) < 0) return false;
      if (s.years.length && s.years.indexOf(f.year) < 0) return false;
      if (s.continents.length && s.continents.indexOf(f.continent) < 0) return false;
      if (s.regions.length && s.regions.indexOf(f.region) < 0) return false;
      if (s.countries.length && s.countries.indexOf(f.country) < 0) return false;
      if (s.dirGenders.length && s.dirGenders.indexOf(f.dir.gender) < 0) return false;
      if (s.dirRaces.length && s.dirRaces.indexOf(f.dir.race) < 0) return false;
      if (s.dirRegions.length && s.dirRegions.indexOf(f.dir.region) < 0) return false;
      if (s.dirCountries.length && s.dirCountries.indexOf(f.dir.country) < 0) return false;
      if (s.wriGenders.length && s.wriGenders.indexOf(f.wri.gender) < 0) return false;
      if (s.wriRaces.length && s.wriRaces.indexOf(f.wri.race) < 0) return false;
      if (s.wriRegions.length && s.wriRegions.indexOf(f.wri.region) < 0) return false;
      if (s.wriCountries.length && s.wriCountries.indexOf(f.wri.country) < 0) return false;
      return true;
    });
  }

  /* ---------------- Sidebar build ---------------- */
  var filterUpdaters = [];
  var groupRefs = {};

  function buildSidebar() {
    var root = $('sidebar');
    root.innerHTML = '';
    root.appendChild(el('div', { class: 'filters-title', html: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M1.5 3h13l-5 6v5l-3-1.6V9z"/></svg>FILTERS' }));

    // FILM group
    var filmBody = el('div', { class: 'group-body' });
    root.appendChild(groupHeader('film', 'FILM'));
    root.appendChild(filmBody);
    filmBody.appendChild(el('input', {
      class: 'search', placeholder: 'Search film or director...',
      oninput: function (e) { state.search = e.target.value; render(); }
    }));
    addFilter(filmBody, 'years', 'RELEASE YEAR', function () { return YEARS; }, true);
    addFilter(filmBody, 'mlGenres', 'GENRE \u00B7 MOVIELENS', function () { return ML_GENRES; });
    addFilter(filmBody, 'imdbGenres', 'GENRE \u00B7 IMDB', function () { return IMDB_GENRES; });
    addFilter(filmBody, 'continents', 'CONTINENT', function () { return OD.conts; });
    addFilter(filmBody, 'regions', 'REGION', function () { return OD.regs; });
    addFilter(filmBody, 'countries', 'COUNTRY', function () { return OD.countries; });

    // DIRECTOR group
    var dirBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('director', 'DIRECTOR'));
    root.appendChild(dirBody);
    addFilter(dirBody, 'dirGenders', 'Gender', function () { return GENDERS; });
    addFilter(dirBody, 'dirRaces', 'Race', function () { return RACES; });
    addFilter(dirBody, 'dirRegions', 'Region', function () { return OD.regs; });
    addFilter(dirBody, 'dirCountries', 'Country', function () { return OD.countries; });

    // WRITER group
    var wriBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('writer', 'WRITER'));
    root.appendChild(wriBody);
    addFilter(wriBody, 'wriGenders', 'Gender', function () { return GENDERS; });
    addFilter(wriBody, 'wriRaces', 'Race', function () { return RACES; });
    addFilter(wriBody, 'wriRegions', 'Region', function () { return OD.regs; });
    addFilter(wriBody, 'wriCountries', 'Country', function () { return OD.countries; });

    groupRefs.film.body = filmBody;
    groupRefs.director.body = dirBody;
    groupRefs.writer.body = wriBody;
  }

  function groupHeader(key, label) {
    var badge = el('span', { class: 'group-badge', style: 'display:none' }, '0');
    var chev = el('span', { class: 'chev' }, state.open[key] ? '\u25BE' : '\u25B8');
    var head = el('div', { class: 'group-header', onclick: function () {
      state.open[key] = !state.open[key];
      groupRefs[key].body.classList.toggle('collapsed', !state.open[key]);
      chev.textContent = state.open[key] ? '\u25BE' : '\u25B8';
    } }, [
      el('div', { class: 'group-left' }, [el('span', { class: 'group-name' }, label), badge]),
      chev
    ]);
    groupRefs[key] = { badge: badge, chev: chev };
    return head;
  }

  function addFilter(parent, key, label, allFn, numeric) {
    var field = el('div', { class: 'field' });
    field.appendChild(el('div', { class: 'field-label' }, label));
    var select = el('select');
    var sw = el('div', { class: 'select-wrap' }, [select, el('span', { class: 'chev-down', html: '&#9662;' })]);
    field.appendChild(sw);
    var chips = el('div', { class: 'chips' });
    field.appendChild(chips);
    parent.appendChild(field);

    select.addEventListener('change', function () {
      var v = select.value;
      if (v === '') return;
      var val = numeric ? parseInt(v, 10) : v;
      if (state[key].indexOf(val) < 0) { state[key] = state[key].concat([val]); render(); }
      select.value = '';
    });

    function update() {
      var sel = state[key];
      var all = allFn();
      // options
      select.innerHTML = '';
      select.appendChild(new Option(sel.length ? 'Add\u2026' : 'Select\u2026', ''));
      all.forEach(function (x) { if (sel.indexOf(numeric ? x : x) < 0) select.appendChild(new Option(String(x), String(x))); });
      select.value = '';
      // chips
      chips.innerHTML = '';
      chips.style.display = sel.length ? 'flex' : 'none';
      sel.slice().sort(function (a, b) { return numeric ? a - b : String(a).localeCompare(String(b)); }).forEach(function (x) {
        chips.appendChild(el('div', { class: 'chip', onclick: function () {
          state[key] = state[key].filter(function (z) { return z !== x; }); render();
        } }, [String(x), el('span', { class: 'chip-x', html: '&times;' })]));
      });
    }
    filterUpdaters.push(update);
  }

  /* ---------------- Render ---------------- */
  var _bubbles = [], _dirBubbles = [], _wriBubbles = [], _world = null, _worldLoading = false, _ro = null, _ro2 = null, _ro3 = null, _ro4 = null, _lastSig = null;

  function render() {
    var fs = filterFilms();

    // counts
    $('films-found').textContent = fs.length;
    $('countries-found').textContent = new Set(fs.map(function (f) { return f.country; })).size;

    // stats
    $('st-total').textContent = fs.length;
    $('st-totalall').textContent = FILMS.length;
    $('st-vimdb').textContent = fmtVotes(sum(fs, 'votesImdb'));
    $('st-vml').textContent = fmtVotes(sum(fs, 'votesMl'));
    $('st-aimdb').textContent = fs.length ? (sum(fs, 'ratingImdb') / fs.length).toFixed(1) : '0.0';
    $('st-aml').textContent = fs.length ? (sum(fs, 'ratingMl') / fs.length).toFixed(1) : '0.0';
    $('st-osc').textContent = sum(fs, 'oscars');
    $('st-oth').textContent = sum(fs, 'otherAwards');

    // group badges
    setBadge('film', (state.search ? 1 : 0) + cnt(['mlGenres','imdbGenres','years','continents','regions','countries']));
    setBadge('director', cnt(['dirGenders','dirRaces','dirRegions','dirCountries']));
    setBadge('writer', cnt(['wriGenders','wriRaces','wriRegions','wriCountries']));

    // filters
    filterUpdaters.forEach(function (u) { u(); });

    // map bubbles (always compute)
    _bubbles = computeBubbles(fs);
    _dirBubbles = computeDirBubbles(fs);
    _wriBubbles = computeWriBubbles(fs);

    // tab content
    if (state.tab === 'map') { renderDist(fs); renderDiversity(fs); ensureMap(); }
    else if (state.tab === 'charts') renderCharts(fs);
    else { state.tablePage = 0; renderTable(fs); }
  }
  function sum(a, k) { return a.reduce(function (s, f) { return s + f[k]; }, 0); }
  function cnt(keys) { return keys.reduce(function (s, k) { return s + state[k].length; }, 0); }
  function setBadge(key, n) {
    var b = groupRefs[key].badge; b.textContent = n; b.style.display = n > 0 ? 'inline-block' : 'none';
  }

  /* ---------------- Distribution strip ---------------- */
  function renderDist(fs) {
    var gc = {}; fs.forEach(function (f) { gc[f.genre] = (gc[f.genre] || 0) + 1; });
    var arr = Object.keys(gc).map(function (g) { return { g: g, n: gc[g] }; }).sort(function (a, b) { return b.n - a.n; });
    var max = Math.max.apply(null, [1].concat(arr.map(function (d) { return d.n; })));
    var row = $('dist-row'); row.innerHTML = '';
    arr.forEach(function (d) {
      row.appendChild(el('div', { class: 'dist-item' }, [
        el('div', { class: 'dist-bar', style: 'height:' + (10 + d.n / max * 42) + 'px;background:' + colorOf(d.g) }),
        el('div', { class: 'dist-cap' }, [el('div', { class: 'dist-genre' }, d.g), el('div', { class: 'dist-count' }, d.n)])
      ]));
    });
  }

  /* ---------------- Diversity ---------------- */
  function renderDiversity(fs) {
    var grid = $('div-grid'); grid.innerHTML = '';
    grid.appendChild(diversityPanel(fs, 'dir', 'DIRECTOR'));
    grid.appendChild(diversityPanel(fs, 'wri', 'WRITER'));
  }
  function diversityPanel(fs, key, title) {
    var total = fs.length || 1;
    // race
    var rc = {}; RACES.forEach(function (r) { rc[r] = 0; });
    fs.forEach(function (f) { rc[f[key].race] = (rc[f[key].race] || 0) + 1; });
    var rMax = Math.max.apply(null, [1].concat(RACES.map(function (r) { return rc[r]; })));
    var raceCol = el('div', {}, [el('div', { class: 'div-sub' }, 'Race')]);
    RACES.forEach(function (r) {
      raceCol.appendChild(el('div', { class: 'race-row' }, [
        el('div', { class: 'race-label' }, [el('span', { class: 'race-dot', style: 'background:' + RACE_COLORS[r] }), r]),
        el('div', { class: 'race-track' }, el('div', { class: 'race-fill', style: 'width:' + (rc[r] / rMax * 100) + '%;background:' + RACE_COLORS[r] })),
        el('div', { class: 'race-pct' }, Math.round(rc[r] / total * 100) + '%')
      ]));
    });
    // gender
    var g = { Male: 0, Female: 0, Unknown: 0 };
    fs.forEach(function (f) { g[f[key].gender] = (g[f[key].gender] || 0) + 1; });
    var gp = function (n) { return Math.round(n / total * 100); };
    var maleFig = '<svg width="34" height="74" viewBox="0 0 40 80"><circle cx="20" cy="11" r="9" fill="' + MALE_C + '"/><rect x="9" y="23" width="22" height="34" rx="9" fill="' + MALE_C + '"/><rect x="13" y="50" width="6" height="26" rx="3" fill="' + MALE_C + '"/><rect x="21" y="50" width="6" height="26" rx="3" fill="' + MALE_C + '"/></svg>';
    var femFig = '<svg width="34" height="74" viewBox="0 0 40 80"><circle cx="20" cy="11" r="9" fill="' + FEMALE_C + '"/><path d="M20 21 L34 60 H6 Z" fill="' + FEMALE_C + '"/><rect x="15" y="58" width="4" height="18" rx="2" fill="' + FEMALE_C + '"/><rect x="21" y="58" width="4" height="18" rx="2" fill="' + FEMALE_C + '"/></svg>';
    var genderCol = el('div', {}, [
      el('div', { class: 'div-sub' }, 'Gender'),
      el('div', { class: 'gender-figs', html: maleFig + femFig }),
      el('div', { class: 'gender-legend' }, [
        glRow('Male', gp(g.Male), MALE_C),
        glRow('Female', gp(g.Female), FEMALE_C),
        glRow('Unknown', gp(g.Unknown), '#8b97a8')
      ])
    ]);
    // age pyramid
    var bands = [['> 60', 61, 999], ['51 a 60', 51, 60], ['41 a 50', 41, 50], ['31 a 40', 31, 40], ['21 a 30', 21, 30], ['ate 20', 0, 20]];
    var rows = bands.map(function (b) {
      var male = 0, female = 0;
      fs.forEach(function (f) { var p = f[key]; if (p.age != null && p.age >= b[1] && p.age <= b[2]) { if (p.gender === 'Male') male++; else if (p.gender === 'Female') female++; } });
      return { label: b[0], male: male, female: female };
    });
    var aMax = Math.max.apply(null, [1].concat(rows.map(function (r) { return Math.max(r.male, r.female); })));
    var ageCol = el('div', {}, [
      el('div', { class: 'age-head' }, [
        el('span', { class: 'age-key age-bar-key m' }), 'Men',
        el('span', { style: 'color:var(--dim)' }, '|'), 'Women',
        el('span', { class: 'age-key age-bar-key f' })
      ])
    ]);
    rows.forEach(function (r) {
      ageCol.appendChild(el('div', { class: 'age-row' }, [
        el('div', { class: 'age-side' }, el('div', { class: 'age-bar male', style: 'width:' + (r.male / aMax * 100) + '%' })),
        el('div', { class: 'age-label' }, r.label),
        el('div', { class: 'age-side' }, el('div', { class: 'age-bar female', style: 'width:' + (r.female / aMax * 100) + '%' }))
      ]));
    });

    return el('div', { class: 'div-panel' }, [
      el('div', { class: 'div-title' }, title + ' DIVERSITY'),
      el('div', { class: 'div-cols' }, [genderCol, ageCol, raceCol])
    ]);
  }
  function glRow(name, pct, color) {
    return el('div', { class: 'gl-row' }, [
      el('span', { class: 'gl-dot', style: 'background:' + color }),
      el('span', { class: 'gl-name' }, name),
      el('span', { class: 'gl-pct' }, pct + '%')
    ]);
  }

  /* ---------------- Charts ---------------- */
  function hbarChart(title, arr, fmtVal) {
    var max = Math.max.apply(null, [1].concat(arr.map(function (d) { return d.n; })));
    var card = chartCard(title);
    arr.forEach(function (d) {
      card.appendChild(el('div', { class: 'hbar-row' }, [
        el('div', { class: 'hbar-label' }, d.label),
        el('div', { class: 'hbar-track' }, el('div', { class: 'hbar-fill', style: 'width:' + (d.n ? Math.max(6, d.n / max * 100) : 0) + '%;' + (d.color ? 'background:' + d.color : '') })),
        el('div', { class: 'hbar-val' }, fmtVal ? fmtVal(d.n) : d.n)
      ]));
    });
    return card;
  }

  function vbarChart(title, buckets, valueKey, fmtVal) {
    var max = Math.max.apply(null, [1].concat(buckets.map(function (b) { return b[valueKey]; })));
    var card = chartCard(title);
    var bars = el('div', { class: 'rbars' });
    buckets.forEach(function (b) {
      var v = b[valueKey];
      bars.appendChild(el('div', { class: 'vcol' }, [
        el('div', { class: 'vval' }, fmtVal ? fmtVal(v) : v),
        el('div', { class: 'vbar' + (v ? '' : ' empty'), style: 'width:46px;height:' + (v / max * 100) + '%;min-height:' + (v ? 4 : 2) + 'px' }),
        el('div', { class: 'vlabel' }, b.label)
      ]));
    });
    card.appendChild(bars);
    return card;
  }

  function renderCharts(fs) {
    var wrap = $('charts-scroll'); wrap.innerHTML = '';

    // ── Pair 1: Genre Distribution | Films by Decade ─────────────────────────
    var gc = {}; fs.forEach(function (f) { gc[f.genre] = (gc[f.genre] || 0) + 1; });
    var gArr = Object.keys(gc).map(function (g) { return { label: g, n: gc[g], color: colorOf(g) }; }).sort(function (a, b) { return b.n - a.n; });
    wrap.appendChild(hbarChart('Genre Distribution', gArr));

    var dc = {};
    fs.forEach(function (f) { if (f.year != null) { var di = Math.floor((f.year - 1) / 10); dc[di] = (dc[di] || 0) + 1; } });
    var allDI = YEARS.map(function (y) { return Math.floor((y - 1) / 10); });
    var minDI = Math.min.apply(null, allDI), maxDI = Math.max.apply(null, allDI);
    var decades = [];
    for (var di = maxDI; di >= minDI; di--) {
      var dStart = di * 10 + 1, dEnd = di === maxDI ? YEARS[YEARS.length - 1] : dStart + 9;
      decades.push({ label: dStart + '–' + dEnd, n: dc[di] || 0 });
    }
    wrap.appendChild(hbarChart('Films by Decade', decades));

    // ── Pair 2: Continent Distribution | Region Distribution ─────────────────
    var cc = {}, rc = {};
    fs.forEach(function (f) {
      if (f.continent && f.continent !== 'Other') cc[f.continent] = (cc[f.continent] || 0) + 1;
      if (f.region) rc[f.region] = (rc[f.region] || 0) + 1;
    });
    wrap.appendChild(hbarChart('Continent Distribution',
      Object.keys(cc).map(function (k) { return { label: k, n: cc[k] }; }).sort(function (a, b) { return b.n - a.n; })));
    wrap.appendChild(hbarChart('Region Distribution',
      Object.keys(rc).map(function (k) { return { label: k, n: rc[k] }; }).sort(function (a, b) { return b.n - a.n; })));

    // ── Pair 3: Rating Distribution ML | Rating Distribution IMDB ────────────
    var mlBuckets = [
      { label: '<3.5', min: 0,   max: 3.5 }, { label: '3.5–4.0', min: 3.5, max: 4.0 },
      { label: '4.0–4.5', min: 4.0, max: 4.5 }, { label: '4.5+',  min: 4.5, max: 99  }
    ];
    mlBuckets.forEach(function (b) { b.count = fs.filter(function (f) { return f.ratingMl >= b.min && f.ratingMl < b.max; }).length; });
    wrap.appendChild(vbarChart('Rating Distribution — ML', mlBuckets, 'count'));

    var imBuckets = [
      { label: '<7.0', min: 0, max: 7 }, { label: '7.0-7.5', min: 7, max: 7.5 },
      { label: '7.5-8.0', min: 7.5, max: 8 }, { label: '8.0+', min: 8, max: 99 }
    ];
    imBuckets.forEach(function (b) { b.count = fs.filter(function (f) { return f.rating >= b.min && f.rating < b.max; }).length; });
    wrap.appendChild(vbarChart('Rating Distribution — IMDB', imBuckets, 'count'));

    // ── Pair 4: Oscars Winning by Continent | Oscars Winning by Region ────────
    var oc = {}, or_ = {};
    fs.forEach(function (f) {
      if (f.oscars) {
        if (f.continent && f.continent !== 'Other') oc[f.continent] = (oc[f.continent] || 0) + f.oscars;
        if (f.region) or_[f.region] = (or_[f.region] || 0) + f.oscars;
      }
    });
    wrap.appendChild(hbarChart('Oscars Winning by Continent',
      Object.keys(oc).map(function (k) { return { label: k, n: oc[k] }; }).sort(function (a, b) { return b.n - a.n; })));
    wrap.appendChild(hbarChart('Oscars Winning by Region',
      Object.keys(or_).map(function (k) { return { label: k, n: or_[k] }; }).sort(function (a, b) { return b.n - a.n; })));

    // ── Pair 5: Other Awards by Continent | Other Awards by Region ────────────
    var awc = {}, awr = {};
    fs.forEach(function (f) {
      if (f.otherAwards) {
        if (f.continent && f.continent !== 'Other') awc[f.continent] = (awc[f.continent] || 0) + f.otherAwards;
        if (f.region) awr[f.region] = (awr[f.region] || 0) + f.otherAwards;
      }
    });
    wrap.appendChild(hbarChart('Other Awards by Continent',
      Object.keys(awc).map(function (k) { return { label: k, n: awc[k] }; }).sort(function (a, b) { return b.n - a.n; })));
    wrap.appendChild(hbarChart('Other Awards by Region',
      Object.keys(awr).map(function (k) { return { label: k, n: awr[k] }; }).sort(function (a, b) { return b.n - a.n; })));

    // ── Single: MovieLens Votes by Rating (full width) ────────────────────────
    if (RATINGS_DIST.length) {
      var mlMax = Math.max.apply(null, RATINGS_DIST.map(function (d) { return d.votes; }));
      var cml = chartCard('MovieLens Votes by Rating');
      cml.style.gridColumn = '1 / -1';
      var mlb = el('div', { class: 'vbars' });
      RATINGS_DIST.forEach(function (d) {
        mlb.appendChild(el('div', { class: 'vcol' }, [
          el('div', { class: 'vval' }, fmtVotes(d.votes)),
          el('div', { class: 'vbar', style: 'height:' + (d.votes / mlMax * 100) + '%;min-height:4px' }),
          el('div', { class: 'vlabel' }, d.rating.toFixed(1))
        ]));
      });
      cml.appendChild(mlb); wrap.appendChild(cml);
    }
  }
  function chartCard(title) { return el('div', { class: 'chart-card' }, [el('div', { class: 'chart-title' }, title)]); }

  /* ---------------- Table ---------------- */
  var COLUMNS = [
    { key: 'title',       label: 'Title' },
    { key: 'director',    label: 'Director' },
    { key: 'year',        label: 'Year',        right: true },
    { key: 'country',     label: 'Country' },
    { key: 'genre',       label: 'Genre' },
    { key: 'rating',      label: 'IMDb ★',  right: true },
    { key: 'ratingMl',    label: 'ML ★',    right: true },
    { key: 'votesMl',     label: 'ML Votes',    right: true },
    { key: 'box',         label: 'Box',         right: true },
    { key: 'oscars',      label: 'Oscars',      right: true },
    { key: 'otherAwards', label: 'Awards',      right: true }
  ];
  function renderTable(fs) {
    // Sort
    var dir = state.sortDir === 'asc' ? 1 : -1;
    var sorted = fs.slice().sort(function (a, b) {
      var av = a[state.sortKey], bv = b[state.sortKey];
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });

    var total = sorted.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.tablePage = Math.min(state.tablePage, totalPages - 1);
    var start = state.tablePage * PAGE_SIZE;
    var page = sorted.slice(start, start + PAGE_SIZE);

    // Header
    var head = $('thead'); head.innerHTML = '';
    COLUMNS.forEach(function (c) {
      var active = state.sortKey === c.key;
      var arrow = active ? (state.sortDir === 'asc' ? ' \u2191' : ' \u2193') : '';
      head.appendChild(el('div', {
        class: 'th' + (c.right ? ' right' : '') + (active ? ' active' : ''),
        onclick: function () {
          if (state.sortKey === c.key) state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
          else { state.sortKey = c.key; state.sortDir = 'desc'; }
          state.tablePage = 0;
          renderTable(fs);
        }
      }, c.label + arrow));
    });

    // Body \u2014 only current page
    var body = $('tbody'); body.innerHTML = '';
    if (!page.length) {
      body.appendChild(el('div', { class: 'empty-row' }, 'No films match the current filters.'));
    } else {
      page.forEach(function (f) {
        body.appendChild(el('div', { class: 'trow' }, [
          el('div', { class: 'cell b' }, f.title),
          el('div', { class: 'cell muted' }, f.director),
          el('div', { class: 'cell mono right' }, f.year),
          el('div', { class: 'cell muted' }, f.country),
          el('div', { class: 'cell genre' }, [el('span', { class: 'gdot', style: 'background:' + colorOf(f.genre) }), f.genre]),
          el('div', { class: 'cell bold right' }, '\u2605 ' + f.rating.toFixed(1)),
          el('div', { class: 'cell mono right' }, f.ratingMl ? '\u2605 ' + f.ratingMl.toFixed(1) : '\u2013'),
          el('div', { class: 'cell mono right' }, f.votesMl ? fmtVotes(f.votesMl) : '\u2013'),
          el('div', { class: 'cell mono right' }, fmtMoney(f.box)),
          el('div', { class: 'cell mono right' }, f.oscars || '\u2013'),
          el('div', { class: 'cell mono right' }, f.otherAwards || '\u2013')
        ]));
      });
    }

    // Pager
    var pager = $('tpager'); pager.innerHTML = '';
    var from = total ? start + 1 : 0;
    var to = Math.min(start + PAGE_SIZE, total);
    pager.appendChild(el('button', {
      class: 'pager-btn' + (state.tablePage === 0 ? ' disabled' : ''),
      onclick: function () {
        if (state.tablePage > 0) { state.tablePage--; renderTable(fs); }
      }
    }, '\u2190 Prev'));
    pager.appendChild(el('span', { class: 'pager-info' },
      from + '\u2013' + to + ' / ' + total + ' filmes'
    ));
    pager.appendChild(el('button', {
      class: 'pager-btn' + (state.tablePage >= totalPages - 1 ? ' disabled' : ''),
      onclick: function () {
        if (state.tablePage < totalPages - 1) { state.tablePage++; renderTable(fs); }
      }
    }, 'Next \u2192'));
  }

  /* ---------------- Map ---------------- */
  function computeBubbles(fs) {
    var groups = {};
    fs.forEach(function (f) { (groups[f.country] = groups[f.country] || []).push(f); });
    return Object.keys(groups).map(function (c) {
      var list = groups[c];
      var top = list.slice().sort(function (a, b) { return b.rating - a.rating; })[0];
      var avg = list.reduce(function (a, f) { return a + f.rating; }, 0) / list.length;
      return {
        country: c,
        count: list.length,
        votesMl: list.reduce(function (a, f) { return a + f.votesMl; }, 0),
        top: top ? top.title : '\u2014',
        rating: avg.toFixed(1),
        box: fmtMoney(list.reduce(function (a, f) { return a + f.box; }, 0))
      };
    });
  }

  function computeDirBubbles(fs) {
    var groups = {};
    fs.forEach(function (f) {
      var c = f.dir.country || f.country;
      var g = groups[c] = groups[c] || { country: c, count: 0, names: {} };
      g.count++;
      if (f.director) g.names[f.director] = (g.names[f.director] || 0) + 1;
    });
    return Object.keys(groups).map(function (c) {
      var g = groups[c];
      var top = Object.keys(g.names).sort(function (a, b) { return g.names[b] - g.names[a]; })[0] || '—';
      return { country: c, count: g.count, top: top };
    });
  }

  function computeWriBubbles(fs) {
    var groups = {};
    fs.forEach(function (f) {
      var c = f.wri.country || f.country;
      var g = groups[c] = groups[c] || { country: c, count: 0, names: {} };
      g.count++;
      if (f.wri.name) g.names[f.wri.name] = (g.names[f.wri.name] || 0) + 1;
    });
    return Object.keys(groups).map(function (c) {
      var g = groups[c];
      var top = Object.keys(g.names).sort(function (a, b) { return g.names[b] - g.names[a]; })[0] || '—';
      return { country: c, count: g.count, top: top };
    });
  }

  function dirTipFn(entry) {
    return '<div class="tt-title">' + entry.country + '</div>' +
      '<div class="tt-row"><span>Directors</span><b>' + entry.count + '</b></div>' +
      '<div class="tt-top">Notable: ' + entry.top + '</div>';
  }

  function wriTipFn(entry) {
    return '<div class="tt-title">' + entry.country + '</div>' +
      '<div class="tt-row"><span>Writers</span><b>' + entry.count + '</b></div>' +
      '<div class="tt-top">Notable: ' + entry.top + '</div>';
  }

  function ensureMap() {
    var h1 = $('map-holder'), h2 = $('map-holder-votes');
    var h3 = $('map-holder-dir'), h4 = $('map-holder-wri');
    if (!window.d3 || !window.topojson) { setTimeout(ensureMap, 120); return; }
    if (!_ro)  { _ro  = new ResizeObserver(function () { drawMap('map-holder',       'tooltip',       'count',   'films'); }); _ro.observe(h1); }
    if (!_ro2) { _ro2 = new ResizeObserver(function () { drawMap('map-holder-votes', 'tooltip-votes', 'votesMl', 'ML votes', '--map-green', '--map-green-faint'); }); _ro2.observe(h2); }
    if (!_ro3 && h3) { _ro3 = new ResizeObserver(function () { drawMap('map-holder-dir', 'tooltip-dir', 'count', 'directors', '--map-purple', '--map-purple-faint', _dirBubbles, dirTipFn); }); _ro3.observe(h3); }
    if (!_ro4 && h4) { _ro4 = new ResizeObserver(function () { drawMap('map-holder-wri', 'tooltip-wri', 'count', 'writers',   '--map-teal',   '--map-teal-faint',   _wriBubbles, wriTipFn); }); _ro4.observe(h4); }
    if (!_world && !_worldLoading) {
      _worldLoading = true;
      fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
        .then(function (r) { return r.json(); })
        .then(function (topo) {
          _world = window.topojson.feature(topo, topo.objects.countries).features;
          drawAllMaps();
        })
        .catch(function () {});
    }
    drawAllMaps();
  }

  function drawAllMaps() {
    drawMap('map-holder',       'tooltip',       'count',   'films');
    drawMap('map-holder-votes', 'tooltip-votes', 'votesMl', 'ML votes', '--map-green',  '--map-green-faint');
    drawMap('map-holder-dir',   'tooltip-dir',   'count',   'directors', '--map-purple', '--map-purple-faint', _dirBubbles, dirTipFn);
    drawMap('map-holder-wri',   'tooltip-wri',   'count',   'writers',   '--map-teal',   '--map-teal-faint',   _wriBubbles, wriTipFn);
  }

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function drawMap(holderId, tooltipId, valueKey, maxLabel, colorVar, faintVar, bubblesData, tipFn) {
    var holder = $(holderId);
    if (!holder || !window.d3) return;
    var w = holder.clientWidth, h = holder.clientHeight;
    if (!w || !h) return;
    var d3 = window.d3;
    var accent    = cssVar(colorVar || '--accent') || '#efa838';
    var sphere    = cssVar('--map-sphere');
    var sphereS   = cssVar('--map-sphere-s');
    var grid      = cssVar('--map-grid');
    var empty     = cssVar('--map-empty');
    var border    = cssVar('--map-border');
    var labelClr  = cssVar('--map-label');
    var legendClr = cssVar('--map-legend');
    var accentFaint = cssVar(faintVar || '--map-accent-faint') || 'rgba(239,168,56,.1)';

    holder.innerHTML = '';
    var svg = d3.select(holder).append('svg').attr('width', w).attr('height', h).attr('viewBox', '0 0 ' + w + ' ' + h);
    var projection = d3.geoNaturalEarth1().fitExtent([[14, 14], [w - 14, h - 14]], { type: 'Sphere' });
    var path = d3.geoPath(projection);

    svg.append('path').attr('d', path({ type: 'Sphere' })).attr('fill', sphere).attr('stroke', sphereS).attr('stroke-width', 0.6);
    svg.append('path').attr('d', path(d3.geoGraticule10())).attr('fill', 'none').attr('stroke', grid).attr('stroke-width', 0.5);

    if (!_world) return;

    var data = bubblesData || _bubbles;
    var byName = {};
    data.forEach(function (b) { byName[b.country] = b; });

    var max = d3.max(data, function (b) { return b[valueKey]; }) || 1;
    var colorScale = d3.scaleSequentialSqrt()
      .domain([0, max])
      .interpolator(d3.interpolate(accentFaint, accent));

    var tip = $(tooltipId);

    svg.append('g').selectAll('path')
      .data(_world)
      .join('path')
      .attr('d', path)
      .attr('fill', function (d) {
        var name = ISO_NUM[+d.id];
        var entry = name ? byName[name] : null;
        return entry ? colorScale(entry[valueKey]) : empty;
      })
      .attr('stroke', border)
      .attr('stroke-width', 0.4)
      .style('cursor', function (d) { return ISO_NUM[+d.id] && byName[ISO_NUM[+d.id]] ? 'pointer' : 'default'; })
      .on('mousemove', function (event, d) {
        var name = ISO_NUM[+d.id];
        var entry = name ? byName[name] : null;
        if (!entry) { tip.style.display = 'none'; return; }
        var p = d3.pointer(event, holder);
        tip.style.display = 'block';
        tip.style.left = p[0] + 'px'; tip.style.top = p[1] + 'px'; tip.style.transform = 'translate(14px,-50%)';
        tip.innerHTML = tipFn ? tipFn(entry) :
          '<div class="tt-title">' + entry.country + '</div>' +
          '<div class="tt-row"><span>Films</span><b>' + entry.count + '</b></div>' +
          '<div class="tt-row"><span>ML votes</span><b>' + fmtVotes(entry.votesMl) + '</b></div>' +
          '<div class="tt-row"><span>Avg rating</span><b>\u2605 ' + entry.rating + '</b></div>' +
          '<div class="tt-row"><span>Box office</span><b>' + entry.box + '</b></div>' +
          '<div class="tt-top">Top: ' + entry.top + '</div>';
      })
      .on('mouseleave', function () { tip.style.display = 'none'; });

    // Continent labels
    var labels = [['NORTH AMERICA', -100, 47], ['SOUTH AMERICA', -58, -13], ['EUROPE', 13, 52], ['AFRICA', 20, 4], ['ASIA', 95, 46], ['OCEANIA', 134, -26]];
    svg.append('g').selectAll('text').data(labels).join('text')
      .attr('transform', function (d) { var p = projection([d[1], d[2]]); return 'translate(' + p[0] + ',' + p[1] + ')'; })
      .text(function (d) { return d[0]; }).attr('text-anchor', 'middle').attr('dy', '0.3em')
      .attr('fill', labelClr).attr('font-size', 10).attr('letter-spacing', 2.5)
      .attr('font-family', 'JetBrains Mono, monospace').style('pointer-events', 'none');

    // Color legend
    var gradId = 'choro-grad-' + holderId;
    var lw = 120, lh = 8, lx = w - lw - 16, ly = h - 24;
    var defs = svg.append('defs');
    var grad = defs.append('linearGradient').attr('id', gradId);
    grad.append('stop').attr('offset', '0%').attr('stop-color', accentFaint);
    grad.append('stop').attr('offset', '100%').attr('stop-color', accent);
    var lg = svg.append('g').attr('transform', 'translate(' + lx + ',' + ly + ')');
    lg.append('rect').attr('width', lw).attr('height', lh).attr('rx', 2).attr('fill', 'url(#' + gradId + ')').attr('opacity', 0.9);
    lg.append('text').attr('x', 0).attr('y', lh + 11).attr('fill', legendClr).attr('font-size', 9).attr('font-family', 'JetBrains Mono, monospace').text('0');
    lg.append('text').attr('x', lw).attr('y', lh + 11).attr('text-anchor', 'end').attr('fill', legendClr).attr('font-size', 9).attr('font-family', 'JetBrains Mono, monospace').text(fmtVotes(max) + ' ' + maxLabel);
  }

  /* ---------------- Tabs & init ---------------- */
  function setTab(tab) {
    state.tab = tab;
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) { b.classList.toggle('active', b.getAttribute('data-tab') === tab); });
    $('pane-map').classList.toggle('active', tab === 'map');
    $('pane-charts').classList.toggle('active', tab === 'charts');
    $('pane-table').classList.toggle('active', tab === 'table');
    render();
  }

  var SUN_SVG = '<path d="M12 4.5V3m0 18v-1.5M4.5 12H3m18 0h-1.5M6.34 6.34 5.28 5.28m13.44 13.44-1.06-1.06M6.34 17.66l-1.06 1.06M18.72 5.28l-1.06 1.06"/><circle cx="12" cy="12" r="4"/>';
  var MOON_SVG = '<path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/>';

  function applyTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    var icon = $('theme-icon');
    if (icon) icon.innerHTML = dark ? MOON_SVG : SUN_SVG;
    if (state.tab === 'map') { drawAllMaps(); }
  }

  function init() {
    // Theme toggle
    var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    applyTheme(isDark);
    $('theme-btn').addEventListener('click', function () {
      isDark = !isDark;
      localStorage.setItem('cinemap-theme', isDark ? 'dark' : 'light');
      applyTheme(isDark);
    });

    buildSidebar();
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.addEventListener('click', function () { setTab(b.getAttribute('data-tab')); });
    });
    $('clear-btn').addEventListener('click', function () {
      ['mlGenres','imdbGenres','years','continents','regions','countries','dirGenders','dirRaces','dirRegions','dirCountries','wriGenders','wriRaces','wriRegions','wriCountries'].forEach(function (k) { state[k] = []; });
      state.search = '';
      var si = document.querySelector('.search'); if (si) si.value = '';
      render();
    });
    render();
  }

  function loadAndInit() {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(10,14,26,0.9);display:flex;align-items:center;justify-content:center;z-index:9999;flex-direction:column;gap:14px;';
    var msg = document.createElement('div');
    msg.style.cssText = 'color:#efa838;font-family:JetBrains Mono,monospace;font-size:13px;letter-spacing:2px;';
    msg.textContent = 'LOADING DATABASE…';
    var dots = document.createElement('div');
    dots.style.cssText = 'color:rgba(239,168,56,0.4);font-family:JetBrains Mono,monospace;font-size:11px;letter-spacing:1px;';
    dots.textContent = 'connecting to oracle';
    overlay.appendChild(msg); overlay.appendChild(dots);
    document.body.appendChild(overlay);

    Promise.all([
      fetch('/api/films').then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }),
      fetch('/api/ratings-dist').then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    ])
      .then(function(results) {
        var data = results[0];
        RATINGS_DIST = results[1];
        FILMS = data;
        YEARS = Array.from(
          new Set(FILMS.map(function(f) { return f.year; }).filter(function(y) { return y != null; }))
        ).sort(function(a, b) { return a - b; });

        // Genres from real data (sorted), fall back to the hardcoded lists
        var mlGs = uniqSort(FILMS.map(function(f) { return f.mlGenre; }).filter(Boolean));
        var imGs = uniqSort(FILMS.map(function(f) { return f.imdbGenre; }).filter(Boolean));
        if (mlGs.length) ML_GENRES = mlGs;
        if (imGs.length) IMDB_GENRES = imGs;

        // Continent/region/country from real data; fall back to country-data.js
        var rows = window.CINEMAP_COUNTRY_ROWS || [];
        var derivedConts = uniqSort(FILMS.map(function(f) { return f.continent; }).filter(function(x) { return x && x !== 'Other'; }));
        var derivedRegs  = uniqSort(FILMS.map(function(f) { return f.region; }).filter(Boolean));
        var derivedCntrs = uniqSort(FILMS.map(function(f) { return f.country; }).filter(function(x) { return x && x !== 'Unknown'; }));
        OD = {
          conts:     derivedConts.length ? derivedConts : uniqSort(rows.map(function(r) { return r[1]; })),
          regs:      derivedRegs.length  ? derivedRegs  : uniqSort(rows.map(function(r) { return r[2]; })),
          countries: derivedCntrs.length ? derivedCntrs : rows.map(function(r) { return r[0]; }).sort(function(a, b) { return a.localeCompare(b); })
        };
        document.body.removeChild(overlay);
        init();
      })
      .catch(function(err) {
        msg.textContent = 'ERRO: servidor não disponível';
        dots.textContent = 'inicie com: uv run uvicorn server:app --reload';
        msg.style.color = '#ef5b5b';
        console.error('[CineMap] failed to load films:', err);
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadAndInit);
  else loadAndInit();
})();
