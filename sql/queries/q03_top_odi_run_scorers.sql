-- Q03 | Beginner
-- Question:
--   List the top 10 highest run scorers in ODI cricket. Show player name, total runs
--   scored, batting average, and number of centuries. Display the highest run scorer
--   first.
-- SQL concepts: JOIN, WHERE, ORDER BY ... DESC, LIMIT
SELECT p.full_name,
       t.team_name,
       s.runs             AS total_runs,
       s.batting_average,
       s.hundreds         AS centuries
FROM player_format_stats s
JOIN players p ON p.player_id = s.player_id
JOIN teams   t ON t.team_id   = p.team_id
WHERE s.match_format = 'ODI'
ORDER BY s.runs DESC
LIMIT 10;
