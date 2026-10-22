-- Q16 | Intermediate
-- Question:
--   Track how players' batting performance changes over different years. For matches since
--   2020, show each player's average runs per match and average strike rate for each year.
--   Only include players who played at least 5 matches in that year.
-- SQL concepts: EXTRACT(YEAR), per-match CTE, GROUP BY two columns, HAVING
WITH per_match AS (
    SELECT b.player_id,
           EXTRACT(YEAR FROM m.match_date)::INT AS year,
           b.match_id,
           SUM(b.runs)        AS runs,
           SUM(b.balls_faced) AS balls
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
    WHERE m.match_date >= DATE '2020-01-01'
    GROUP BY b.player_id, year, b.match_id
)
SELECT p.full_name,
       pm.year,
       COUNT(*)                                             AS matches,
       ROUND(AVG(pm.runs), 2)                               AS avg_runs_per_match,
       ROUND(SUM(pm.runs) * 100.0 / NULLIF(SUM(pm.balls), 0), 2) AS strike_rate
FROM per_match pm
JOIN players p ON p.player_id = pm.player_id
GROUP BY p.full_name, pm.year
HAVING COUNT(*) >= 5
ORDER BY p.full_name, pm.year;
