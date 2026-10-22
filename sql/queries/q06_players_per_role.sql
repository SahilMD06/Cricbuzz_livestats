-- Q06 | Beginner
-- Question:
--   Count how many players belong to each playing role (like Batsman, Bowler, All-rounder,
--   Wicket-keeper). Show the role and count of players for each role.
-- SQL concepts: GROUP BY, COUNT
SELECT playing_role,
       COUNT(*) AS player_count
FROM players
GROUP BY playing_role
ORDER BY player_count DESC;
