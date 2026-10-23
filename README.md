# 🏏 Cricbuzz LiveStats: Real-Time Cricket Insights & SQL-Based Analytics

A multi-page **Streamlit** dashboard that pulls live cricket data from the **Cricbuzz API**,
stores it in **PostgreSQL**, answers **25 SQL analytics questions**, and provides full
**CRUD** management of players and matches.

**Domain:** Sports Analytics · **Skills:** Python · SQL · Streamlit · REST API · JSON · pandas

**🔗 Live demo:** https://cricbuzzlivestats-sahilmd06.streamlit.app/
**💻 Source code:** https://github.com/SahilMD06/Cricbuzz_livestats

![Home page](documentation/screenshots/01_home.png)

---

## Contents
1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Setup (local)](#setup-local)
6. [API setup (Cricbuzz on RapidAPI)](#api-setup-cricbuzz-on-rapidapi)
7. [Database setup](#database-setup)
8. [Running the app and tests](#running-the-app-and-tests)
9. [The 25 SQL questions](#the-25-sql-questions)
10. [About the data](#about-the-data)
11. [Deployment](#deployment)
12. [Security](#security)
13. [Troubleshooting](#troubleshooting)
14. [Screenshots](#screenshots)
15. [Future improvements](#future-improvements)

---

## Features

| Page | What it does |
|---|---|
| **Home** | Project overview, tools, live database/API status, row counts by data source, recent data loads, README and folder structure. |
| **Live Matches** | Live / recent / upcoming matches as cards (teams, scores, status, venue). Opens a full scorecard: every innings with batting (R, B, 4s, 6s, SR, dismissal) and bowling (O, M, R, W, Econ) tables and a runs chart. Optional 60-second auto-refresh. Falls back to stored matches if no API key is set. |
| **Top Player Stats** | Cricbuzz leaderboards per format: most runs, highest score, best average and strike rate, most 100s/50s/6s/4s, most wickets, best bowling average and economy, five-wicket hauls. Table + chart + CSV download. |
| **SQL Analytics** | All 25 questions (beginner → advanced). Each shows the question, SQL concepts, result table, chart, the SQL itself and a CSV download. A **read-only SQL console** lets you run your own SELECTs safely. |
| **CRUD Operations** | Search, view, add, update and delete **players** and **matches** with validated forms; view stored scorecards and career stats; import recent real matches from the API. Writes require an admin password. |

---

## Architecture

```
┌──────────────────────── Streamlit (pages/, components/) ────────────────────────┐
│ Home · Live Matches · Top Stats · SQL Analytics · CRUD                          │
└───────────────┬───────────────────────────────┬─────────────────────────────────┘
                │                               │
     services/ (business rules)          analytics/ (25 query specs + runner)
     live · stats · ingestion · CRUD            │
        │                 │                     │
   api/client.py     database/ repositories ────┘   (all CRUD SQL lives here)
   (HTTP only)             │
        │           utils/db_connection.py  ← the single engine (required by brief)
        ▼                  ▼
  Cricbuzz API       PostgreSQL (Neon)
  (RapidAPI)         tables · views · indexes · trigger
```

**Rule:** each layer only calls the layer below it. Pages never import `requests` or write
SQL; the API client never touches the database.

**Data flows**
- **Live view:** page → `LiveMatchService` (cached 60 s) → `CricbuzzClient` → API. Nothing
  is written: live data changes every ball.
- **Ingestion:** `IngestionService` → scorecard JSON → pure transformers → one transaction
  writes teams, venue, series, match, players and innings. Idempotent (safe to re-run).
- **Analytics:** page → `analytics.runner` → `sql/queries/qNN.sql` → DataFrame → table + chart.
- **CRUD:** form → service validation → repository (parameterised SQL, transaction) →
  cache cleared so every page sees the change.

---

## Tech stack

| Area | Choice | Why |
|---|---|---|
| Web app | Streamlit ≥ 1.48 | Multi-page app with `st.navigation`, forms, caching |
| Database | PostgreSQL 14+ (Neon) | Window functions, `STDDEV`, `FILTER`, `ROLLUP`, generated columns |
| DB access | SQLAlchemy 2 + psycopg2 | Connection pooling, transactions, bound parameters; dialect-portable |
| API | `requests` + `tenacity` | Timeouts, retries with exponential backoff |
| Data | pandas | Query results and API tables as DataFrames |
| Charts | Plotly | Interactive charts that match the dark theme |
| Config | python-dotenv / `st.secrets` | Secrets out of the code |
| Tests | pytest | 85 tests: unit (offline) + integration (database) |

---

## Project structure

```
cricbuzz_livestats/
├── app.py                     # entry point: page config + st.navigation
├── config.py                  # Settings from st.secrets / environment / .env
├── requirements.txt
├── pytest.ini
├── .env.example               # copy to .env (never commit .env)
├── .streamlit/
│   ├── config.toml            # dark theme
│   └── secrets.toml.example   # for Streamlit Community Cloud
├── pages/                     # home, live_matches, top_stats, sql_queries, crud_operations
├── components/                # cards.py (styling, match cards, errors), charts.py (Plotly)
├── api/                       # client.py (CricbuzzClient), endpoints.py
├── services/                  # transformers, live/stats/ingestion services, CRUD services
├── database/                  # base + 7 repositories (all CRUD SQL)
├── analytics/                 # registry.py (25 query specs), runner.py
├── models/                    # entities.py (dataclasses + allowed values)
├── core/                      # exceptions.py (one hierarchy for every layer)
├── utils/                     # db_connection.py, logger.py, validators.py, formatters.py
├── sql/                       # schema.sql, views.sql, queries/q01..q25.sql
├── scripts/                   # init_db, seed_data, ingest, api_probe
├── notebooks/                 # data_fetching.ipynb (optional exploration)
├── tests/                     # unit/, integration/, fixtures/ (sample API JSON)
├── data/raw/                  # saved API responses (gitignored)
└── documentation/             # requirements_checklist.md, screenshots/
```

---

## Setup (local)

**Prerequisites:** Python 3.10+, Git, a PostgreSQL database (free [Neon](https://neon.tech)
project recommended), and optionally a RapidAPI account.

```powershell
# Windows PowerShell (macOS/Linux: use `source .venv/bin/activate`)
git clone <your-repo-url> cricbuzz_livestats
cd cricbuzz_livestats
python -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env              # then edit .env (see below)
```

### `.env` settings

| Variable | Required | Example / meaning |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require` |
| `RAPIDAPI_KEY` | for live pages | Your RapidAPI key |
| `RAPIDAPI_HOST` | no | `cricbuzz-cricket.p.rapidapi.com` (default) |
| `ADMIN_PASSWORD` | recommended | Password that unlocks CRUD writes (default `change_me`) |
| `CACHE_TTL_LIVE` / `CACHE_TTL_STATS` | no | Seconds to cache live lists (60) / leaderboards (3600) |
| `API_TIMEOUT` | no | Read timeout in seconds (15) |
| `LOG_LEVEL` | no | `INFO` (logs go to the console and `logs/app.log`) |

> **Neon tip:** copy the connection string from *Dashboard → Connect*, insert `+psycopg2`
> after `postgresql`, keep `?sslmode=require`, and remove `&channel_binding=require` if present.
> If the password contains `@`, `:` or `/`, URL-encode it (e.g. `@` → `%40`).

---

## API setup (Cricbuzz on RapidAPI)

1. Create a free account at [rapidapi.com](https://rapidapi.com).
2. Search **"Cricbuzz Cricket"** and click **Subscribe to Test** on the free (Basic) plan.
   *Without subscribing, every call returns 403.*
3. Copy the **X-RapidAPI-Key** into `RAPIDAPI_KEY` in `.env`.
4. Optional check (≈ 6 calls; saves raw JSON to `data/raw/`):
   `python -m scripts.api_probe`

**Endpoints used**

| Endpoint | Used for |
|---|---|
| `GET /matches/v1/live` · `/recent` · `/upcoming` | Live Matches page; discovering matches to import |
| `GET /mcenter/v1/{matchId}/scard` (fallback `/hscard`) | Scorecards (display + ingestion) |
| `GET /mcenter/v1/{matchId}` | Match info when the scorecard lacks it |
| `GET /stats/v1/topstats/0?statsType=..&matchType=..` | Top Player Stats |
| `GET /venues/v1/{venueId}` | Venue country/capacity for newly imported grounds |
| `GET /stats/v1/player/{id}` · `/batting` · `/bowling` | Player profile and career stats |

**Quota:** the free plan has a small monthly allowance. The app protects it by caching
(live lists 60 s, leaderboards 1 h), by never calling the API on reruns, and by skipping
already-imported matches. `CricbuzzClient.quota` tracks the remaining calls from response
headers. The parser handles both the older camelCase and the newer lowercase Cricbuzz JSON
formats and falls back to parsing results from the status text (e.g. "India won by 6 wkts").

---

## Database setup

```powershell
python -m scripts.init_db        # create tables, constraints, indexes, trigger, views
python -m scripts.seed_data      # load the labelled seed dataset (~2 s)
python -m scripts.ingest         # optional: import up to 5 recent real matches (API key needed)
```

`init_db` is idempotent; `--reset` drops and recreates everything. `seed_data` refuses to
run on a non-empty database unless given `--reset`. Both print a summary; `seed_data` also
runs 13 threshold checks proving every SQL question has data.

### Schema (9 tables, 3NF)

| Table | Purpose | Key constraints |
|---|---|---|
| `teams` | National sides | `team_name` UNIQUE, `cricbuzz_team_id` UNIQUE |
| `venues` | Grounds with city, country, capacity | UNIQUE (name, city); capacity > 0 |
| `players` | Players with role and styles | role ∈ 4 values; FK team (RESTRICT) |
| `series` | Tours / tournaments | end ≥ start |
| `matches` | One row per match; **4 role-playing FKs** to teams | team1 ≠ team2; toss/winner must be a participant; completed ⇒ result |
| `batting_innings` | Batter per innings (M:N players↔matches) | UNIQUE position per innings; 4·fours + 6·sixes ≤ runs; generated `strike_rate` |
| `bowling_innings` | Bowler per innings | `balls_bowled` is the truth; generated `overs`, `economy` |
| `player_format_stats` | Career snapshot per format | PK (player, format) |
| `ingestion_log` | Every data load | status ∈ success/partial/failed |

Views: `v_match_summary` (readable result text), `v_batting_detail`, `v_bowling_detail`,
`v_player_profile`. Foreign keys are explicitly indexed (PostgreSQL does not do this
automatically). A trigger maintains `updated_at`.

---

## Running the app and tests

```powershell
streamlit run app.py                         # opens http://localhost:8501
pytest                                       # 85 tests (integration tests need DATABASE_URL)
pytest -m "not integration"                  # offline unit tests only
python -m analytics.runner                   # run all 25 queries with timings
```

Always run commands from the project root (use `python -m scripts.x`, not
`python scripts/x.py`) so imports resolve.

---

## The 25 SQL questions

Every query lives in `sql/queries/` with the question and the SQL concepts in its header.

| # | Level | Question (short) | Key techniques |
|---|---|---|---|
| 1 | Beginner | Players representing India | JOIN, WHERE |
| 2 | Beginner | Matches in the last 30 days | view, date arithmetic |
| 3 | Beginner | Top 10 ODI run scorers | ORDER BY, LIMIT |
| 4 | Beginner | Venues > 50,000 capacity | numeric filter, NULL behaviour |
| 5 | Beginner | Wins per team | LEFT JOIN, COUNT |
| 6 | Beginner | Players per role | GROUP BY |
| 7 | Beginner | Highest score per format | MAX |
| 8 | Beginner | Series started in 2024 | sargable date range |
| 9 | Intermediate | All-rounders 1000+ runs & 50+ wickets | compound WHERE |
| 10 | Intermediate | Last 20 completed matches | multi-role joins |
| 11 | Intermediate | Runs by format, overall average | `SUM … FILTER`, weighted average |
| 12 | Intermediate | Home vs away wins | CTE, join on `IN`, CASE |
| 13 | Intermediate | 100+ consecutive-batter partnerships | self-join |
| 14 | Intermediate | Bowling by venue (3+ matches, 4+ overs) | two-stage aggregation |
| 15 | Intermediate | Close-match performers | CTEs, OR conditions |
| 16 | Intermediate | Yearly batting trend since 2020 | EXTRACT, HAVING |
| 17 | Advanced | Toss advantage | `GROUP BY ROLLUP`, `GROUPING()` |
| 18 | Advanced | Most economical limited-overs bowlers | ratio of sums |
| 19 | Advanced | Most consistent batsmen | `STDDEV_SAMP`, coefficient of variation |
| 20 | Advanced | Matches and averages per format | pivot with FILTER |
| 21 | Advanced | Weighted performance ranking | `RANK() OVER (PARTITION BY)` |
| 22 | Advanced | Head-to-head analysis | LEAST/GREATEST pairs, derived batting-first team |
| 23 | Advanced | Recent form (last 10 innings) | `ROW_NUMBER()`, CASE categories |
| 24 | Advanced | Best batting partnerships | self-join, `RANK()` |
| 25 | Advanced | Career trajectory by quarter | `DATE_TRUNC`, `LAG()`, `REGR_SLOPE` |

**Interpretation notes** (documented in the SQL files):
- *Q13/Q24* follow the brief's definition of a partnership: batters in adjacent batting
  positions in the same innings. (A real partnership is whoever was at the crease together.)
- *Q15/Q19* add a small minimum-sample filter so one-off appearances don't top the list.
- *Q21:* the brief's bowling formula has an unbalanced parenthesis; it is implemented as
  `wickets×2 + (50 − bowling_avg)×0.5 + (6 − economy)×2`. With these weights, wickets
  dominate runs, so the ranking favours bowlers. That is a property of the given formula.

---

## About the data

The free API quota cannot backfill years of scorecards, which ten of the questions need
(e.g. Q25 needs 6+ quarters with 3+ matches each). The database therefore combines:

| Source | `source` value | Contents |
|---|---|---|
| Cricbuzz API | `api` | Real recent matches imported by `scripts/ingest.py` or the CRUD page |
| Seed generator | `seed` | **Fictional** players (14 per team), real grounds, simulated tours 2021→today |
| CRUD forms | `manual` | Anything you add by hand |

The seed generator (`scripts/seed_data.py`) simulates every match innings by innings so the
numbers are internally consistent, uses a fixed random seed (42) and dates relative to today
(so "last 30 days" always has data). Player names are fictional so they can never be
confused with, or collide with, real players imported from the API. **Re-seed shortly before a
demo** with `python -m scripts.seed_data --reset` so the recent-match questions stay current.

---

## Deployment

### Streamlit Community Cloud (free)
1. Push the project to a **GitHub** repository (`.env` stays out because of `.gitignore`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app** → choose the repo,
   branch `main`, main file `app.py`.
3. Under **Advanced settings → Secrets**, paste the contents of
   `.streamlit/secrets.toml.example` with real values.
4. Deploy. The database must be reachable from the internet (Neon is), so a local
   PostgreSQL will not work here.

### Other options
- **Render / Railway:** start command `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`; set the same variables as environment variables.
- **Docker:** a `python:3.12-slim` image with `pip install -r requirements.txt` and the start
  command above; pass secrets as environment variables, never bake them into the image.

---

## Security

- Secrets come only from `.env` / `st.secrets`; `.env` and `secrets.toml` are gitignored.
  `Settings` hides secrets from `repr()`, and logs never print the database password.
- All data-manipulation SQL uses **bound parameters**; user input is never formatted into SQL.
- The SQL console accepts a single SELECT and runs it inside a **READ ONLY** transaction
  with a 10-second timeout.
- CRUD writes require `ADMIN_PASSWORD` (constant-time comparison).
- API/DB text is HTML-escaped before it is placed into custom HTML.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `403` / "API rejected the key" | Click **Subscribe** on the Cricbuzz Cricket free plan; check `RAPIDAPI_KEY`. |
| "Monthly API quota used up" | Wait for the reset; the database pages keep working. |
| `could not connect` / SSL error | Check `DATABASE_URL`, keep `?sslmode=require`, check internet access. |
| `ModuleNotFoundError: config` | Run from the project root; use `python -m scripts.<name>`. |
| PowerShell won't activate venv | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Git: "dubious ownership" | `git config --global --add safe.directory <project path>` |
| A question shows no rows | Re-seed: `python -m scripts.seed_data --reset` |

---

## Screenshots

| | |
|---|---|
| ![Home](documentation/screenshots/01_home.png) | ![Live matches](documentation/screenshots/02_live_matches.png) |
| ![Top stats](documentation/screenshots/03_top_stats.png) | ![SQL analytics](documentation/screenshots/04_sql_analytics.png) |
| ![CRUD](documentation/screenshots/05_crud.png) | |

*(The Live Matches and Top Stats screenshots show the database fallback; with an API key
they show live Cricbuzz data.)*

---

## Future improvements
- Scheduled ingestion (GitHub Actions / cron) instead of manual imports
- Ball-by-ball commentary storage for deeper analytics
- Match-outcome prediction using the Q17/Q22 features
- Player form alerts based on Q23 categories
- User accounts with viewer/admin roles
- Docker image and CI pipeline running the test suite on every push
