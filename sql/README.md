# sql/

| File | Purpose |
|---|---|
| `schema.sql` | 9 tables, constraints, 14 indexes, `updated_at` trigger (idempotent) |
| `views.sql` | `v_match_summary`, `v_batting_detail`, `v_bowling_detail`, `v_player_profile` |
| `queries/q01_*.sql ... q25_*.sql` | The 25 analytics questions, one file each, with the question and concepts in a header comment |

Run order: `python -m scripts.init_db` (schema + views) -> `python -m scripts.seed_data`.
Every query file can also be pasted straight into psql, pgAdmin or the Neon SQL editor.
