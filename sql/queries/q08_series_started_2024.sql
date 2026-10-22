-- Q08 | Beginner
-- Question:
--   Show all cricket series that started in the year 2024. Include series name, host
--   country, match type, start date, and total number of matches planned.
-- SQL concepts: Sargable date range (index-friendly) instead of EXTRACT(YEAR ...)
SELECT series_name,
       host_country,
       match_type,
       start_date,
       total_matches_planned
FROM series
WHERE start_date >= DATE '2024-01-01'
  AND start_date <  DATE '2025-01-01'
ORDER BY start_date;
