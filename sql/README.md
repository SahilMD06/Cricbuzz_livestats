# sql/

| File | Purpose | Phase |
|---|---|---|
| `schema.sql` | CREATE TABLE + constraints + indexes | 8 |
| `views.sql` | Reusable views (match summary, batting detail) | 8 |
| `queries/q01_*.sql ... q25_*.sql` | The 25 analytics questions, one file each | 11 |

Run order: `schema.sql` -> `views.sql` -> seed (scripts/seed_data.py).
