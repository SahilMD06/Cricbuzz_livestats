-- Q11 | Intermediate
-- Question:
--   Compare each player's performance across different cricket formats. For players who
--   have played at least 2 different formats, show their total runs in Test cricket, ODI
--   cricket, and T20I cricket, along with their overall batting average across all
--   formats.
-- SQL concepts: Conditional aggregation (SUM ... FILTER), HAVING, weighted average via derived dismissals
-- Overall average must be weighted: total runs / total dismissals.
-- Dismissals per format = runs / batting_average (averaging the averages would be wrong).
SELECT p.full_name,
       COALESCE(SUM(s.runs) FILTER (WHERE s.match_format = 'Test'), 0) AS test_runs,
       COALESCE(SUM(s.runs) FILTER (WHERE s.match_format = 'ODI'),  0) AS odi_runs,
       COALESCE(SUM(s.runs) FILTER (WHERE s.match_format = 'T20I'), 0) AS t20i_runs,
       COUNT(*)                                                     AS formats_played,
       ROUND(SUM(s.runs)::NUMERIC
             / NULLIF(SUM(s.runs / NULLIF(s.batting_average, 0)), 0), 2) AS overall_batting_avg
FROM player_format_stats s
JOIN players p ON p.player_id = s.player_id
WHERE s.matches > 0
GROUP BY p.player_id, p.full_name
HAVING COUNT(*) >= 2
ORDER BY (SUM(s.runs)) DESC;
