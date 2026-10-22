-- Q15 | Intermediate
-- Question:
--   Identify players who perform exceptionally well in close matches. A close match is
--   defined as one decided by less than 50 runs OR less than 5 wickets. For these close
--   matches, calculate each player's average runs scored, total close matches played, and
--   how many of those close matches their team won when they batted.
-- SQL concepts: CTEs, OR conditions, per-match aggregation, COUNT ... FILTER
WITH close_matches AS (
    SELECT match_id, winner_id
    FROM matches
    WHERE (victory_type = 'runs'    AND victory_margin < 50)
       OR (victory_type = 'wickets' AND victory_margin < 5)
),
per_match AS (                                  -- a Test has two innings per player
    SELECT b.player_id, b.team_id, b.match_id, SUM(b.runs) AS runs
    FROM batting_innings b
    JOIN close_matches c ON c.match_id = b.match_id
    GROUP BY b.player_id, b.team_id, b.match_id
)
SELECT p.full_name,
       ROUND(AVG(pm.runs), 2)                         AS avg_runs_in_close_matches,
       COUNT(*)                                       AS close_matches_batted,
       COUNT(*) FILTER (WHERE pm.team_id = c.winner_id) AS close_matches_won
FROM per_match pm
JOIN close_matches c ON c.match_id  = pm.match_id
JOIN players p       ON p.player_id = pm.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(*) >= 3                            -- added: ignore one-off appearances
ORDER BY avg_runs_in_close_matches DESC;
