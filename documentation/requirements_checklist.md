# Requirements Checklist

Legend: ✅ done · 🔶 needs your input/action · ☐ not started

## Mandatory
| ID | Requirement | Status | Where |
|---|---|---|---|
| M-01..07 | API integration: requests, live matches, player stats, series, error handling, key security | ✅ (live verification pending your key) | `api/`, `services/` |
| M-08 | SQL database with player and match data | ✅ | `sql/schema.sql` |
| M-09 | Database-agnostic design | ✅ SQLAlchemy URL; PostgreSQL chosen for STDDEV/window functions | `utils/db_connection.py` |
| M-10 | Centralised connection in `utils/db_connection.py` | ✅ | |
| M-11 | Optimised queries, indexes | ✅ 14 indexes, FKs indexed | `sql/schema.sql` |
| M-12 | Schema + sample data | ✅ | `sql/`, `scripts/seed_data.py` |
| M-13 | Secure DB credentials | ✅ `.env` / `st.secrets` | `config.py` |
| M-14 | DB exception handling | ✅ | `database/base_repository.py` |
| M-15 | NULL checks / data quality | ✅ COALESCE/NULLIF in queries; CHECK constraints | |
| M-16..18 | 25 SQL questions | ✅ 25/25 return rows | `sql/queries/` |
| M-19 | Results shown in Streamlit | ✅ | `pages/sql_queries.py` |
| M-20..23 | CRUD create/read/update/delete | ✅ players + matches | `pages/crud_operations.py` |
| M-24..25 | Home page with docs and structure | ✅ | `pages/home.py` |
| M-26..27 | Live matches + scorecards | ✅ (needs API key for live data) | `pages/live_matches.py` |
| M-28..29 | Top stats + charts | ✅ (needs API key for live data) | `pages/top_stats.py` |
| M-30 | SQL analytics page | ✅ | |
| M-31 | CRUD page | ✅ | |
| M-32 | Multi-page app | ✅ `st.navigation` | `app.py` |
| M-33..35 | PEP 8, modular, docstrings | ✅ pycodestyle + pyflakes clean | |
| M-36 | Git version control | ✅ | |
| M-37 | Complete source code | ✅ | |
| M-38 | requirements.txt | ✅ | |
| M-39 | README with setup + API key configuration | ✅ | `README.md` |
| M-40 | Working demo, all modules | 🔶 run locally with your Neon URL + API key | |
| M-41 | Recorded demo video | 🔶 you | |
| M-42 | Submit within 14 days | 🔶 you | |

## Optional / Bonus
| ID | Feature | Status |
|---|---|---|
| O-01 | data_fetching notebook | ✅ `notebooks/data_fetching.ipynb` |
| O-02 | Custom read-only SQL console | ✅ |
| O-03 | Recent / upcoming tabs + DB fallback | ✅ |
| B-01 | Charts on analytics page | ✅ |
| B-02 | Show SQL tab | ✅ |
| B-03 | CSV download | ✅ |
| B-04 | Live auto-refresh | ✅ `st.fragment(run_every=60)` |
| B-05 | Player comparison | ☐ (Q11/Q20 cover cross-format comparison) |
| B-06 | Custom theme | ✅ |
| B-07 | Deployment | 🔶 steps in README |
| B-08 | pytest suite | ✅ 85 tests |
| B-09 | Ingestion log on Home | ✅ |
| B-10 | Database views | ✅ 4 views |
