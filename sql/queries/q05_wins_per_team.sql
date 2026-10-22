-- Q05 | Beginner
-- Question:
--   Calculate how many matches each team has won. Show team name and total number of wins.
--   Display teams with most wins first.
-- SQL concepts: LEFT JOIN (keeps teams with zero wins), COUNT, GROUP BY
SELECT t.team_name,
       COUNT(m.match_id) AS total_wins
FROM teams t
LEFT JOIN matches m ON m.winner_id = t.team_id
GROUP BY t.team_id, t.team_name
ORDER BY total_wins DESC, t.team_name;
