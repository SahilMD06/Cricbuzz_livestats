-- Q12 | Intermediate
-- Question:
--   Analyze each international team's performance when playing at home versus playing
--   away. Determine whether each team played at home or away based on whether the venue
--   country matches the team's country. Count wins for each team in both home and away
--   conditions.
-- SQL concepts: CTE, join on IN (team1, team2), CASE, COUNT ... FILTER
WITH participation AS (
    SELECT t.team_id,
           t.team_name,
           CASE WHEN v.country = t.country THEN 'Home' ELSE 'Away' END AS condition,
           (m.winner_id = t.team_id)                                   AS won
    FROM matches m
    JOIN venues v ON v.venue_id = m.venue_id
    JOIN teams  t ON t.team_id IN (m.team1_id, m.team2_id)
    WHERE m.match_status = 'Completed'
)
SELECT team_name,
       COUNT(*) FILTER (WHERE condition = 'Home')         AS home_matches,
       COUNT(*) FILTER (WHERE condition = 'Home' AND won) AS home_wins,
       COUNT(*) FILTER (WHERE condition = 'Away')         AS away_matches,
       COUNT(*) FILTER (WHERE condition = 'Away' AND won) AS away_wins,
       ROUND(100.0 * COUNT(*) FILTER (WHERE condition = 'Home' AND won)
             / NULLIF(COUNT(*) FILTER (WHERE condition = 'Home'), 0), 1) AS home_win_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE condition = 'Away' AND won)
             / NULLIF(COUNT(*) FILTER (WHERE condition = 'Away'), 0), 1) AS away_win_pct
FROM participation
GROUP BY team_id, team_name
-- An alias can be used alone in ORDER BY, but not inside an expression,
-- so the total-wins expression is written out in full.
ORDER BY COUNT(*) FILTER (WHERE won) DESC, team_name;
