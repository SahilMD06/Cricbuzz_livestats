-- Q14 | Intermediate
-- Question:
--   Examine bowling performance at different venues. For bowlers who have played at least
--   3 matches at the same venue, calculate their average economy rate, total wickets
--   taken, and number of matches played at each venue. Focus on bowlers who bowled at
--   least 4 overs in each match.
-- SQL concepts: Two-step aggregation with a CTE (innings -> match -> venue), HAVING
-- Step 1: one row per bowler per match (a Test has two bowling innings).
WITH per_match AS (
    SELECT bw.player_id,
           m.venue_id,
           bw.match_id,
           SUM(bw.balls_bowled)  AS balls,
           SUM(bw.runs_conceded) AS runs,
           SUM(bw.wickets)       AS wickets
    FROM bowling_innings bw
    JOIN matches m ON m.match_id = bw.match_id
    GROUP BY bw.player_id, m.venue_id, bw.match_id
    HAVING SUM(bw.balls_bowled) >= 24          -- at least 4 overs in the match
)
-- Step 2: aggregate per bowler per venue.
SELECT p.full_name,
       v.venue_name,
       COUNT(*)                                AS matches_at_venue,
       ROUND(AVG(pm.runs * 6.0 / pm.balls), 2) AS avg_economy,
       SUM(pm.wickets)                         AS total_wickets
FROM per_match pm
JOIN players p ON p.player_id = pm.player_id
JOIN venues  v ON v.venue_id  = pm.venue_id
GROUP BY p.full_name, v.venue_name
HAVING COUNT(*) >= 3
ORDER BY avg_economy, total_wickets DESC;
