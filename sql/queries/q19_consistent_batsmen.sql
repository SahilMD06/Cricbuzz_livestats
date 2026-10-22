-- Q19 | Advanced
-- Question:
--   Determine which batsmen are most consistent in their scoring. Calculate the average
--   runs scored and the standard deviation of runs for each player. Only include players
--   who have faced at least 10 balls per innings and played since 2022. A lower standard
--   deviation indicates more consistent performance.
-- SQL concepts: STDDEV_SAMP, coefficient of variation, filtering before aggregating
SELECT p.full_name,
       COUNT(*)                              AS innings,
       ROUND(AVG(b.runs), 2)                 AS avg_runs,
       ROUND(STDDEV_SAMP(b.runs), 2)         AS stddev_runs,
       ROUND(STDDEV_SAMP(b.runs) / NULLIF(AVG(b.runs), 0), 2) AS coeff_of_variation
FROM batting_innings b
JOIN matches m ON m.match_id  = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE b.balls_faced >= 10
  AND m.match_date  >= DATE '2022-01-01'
GROUP BY p.player_id, p.full_name
HAVING COUNT(*) >= 10                       -- added: a deviation needs enough innings
ORDER BY stddev_runs
LIMIT 25;
