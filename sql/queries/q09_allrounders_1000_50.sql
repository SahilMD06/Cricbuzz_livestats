-- Q09 | Intermediate
-- Question:
--   Find all-rounder players who have scored more than 1000 runs AND taken more than 50
--   wickets in their career. Display player name, total runs, total wickets, and the
--   cricket format.
-- SQL concepts: JOIN, compound WHERE (AND)
SELECT p.full_name,
       s.match_format,
       s.runs    AS total_runs,
       s.wickets AS total_wickets
FROM player_format_stats s
JOIN players p ON p.player_id = s.player_id
WHERE p.playing_role = 'All-rounder'
  AND s.runs    > 1000
  AND s.wickets > 50
ORDER BY s.runs DESC;
