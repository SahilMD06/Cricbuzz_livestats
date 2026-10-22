-- Q18 | Advanced
-- Question:
--   Find the most economical bowlers in limited-overs cricket (ODI and T20 formats).
--   Calculate each bowler's overall economy rate and total wickets taken. Only consider
--   bowlers who have bowled in at least 10 matches and bowled at least 2 overs per match
--   on average.
-- SQL concepts: Aggregate ratio (not average of ratios), HAVING with computed averages
SELECT p.full_name,
       COUNT(DISTINCT bw.match_id)                              AS matches,
       ROUND(SUM(bw.balls_bowled) / 6.0 / COUNT(DISTINCT bw.match_id), 2) AS avg_overs_per_match,
       ROUND(SUM(bw.runs_conceded) * 6.0 / SUM(bw.balls_bowled), 2)       AS economy_rate,
       SUM(bw.wickets)                                          AS total_wickets
FROM bowling_innings bw
JOIN matches m ON m.match_id  = bw.match_id
JOIN players p ON p.player_id = bw.player_id
WHERE m.match_format IN ('ODI', 'T20I')
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT bw.match_id) >= 10
   AND SUM(bw.balls_bowled) >= 12 * COUNT(DISTINCT bw.match_id)   -- >= 2 overs/match
ORDER BY economy_rate, total_wickets DESC
LIMIT 25;
