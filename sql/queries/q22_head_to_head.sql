-- Q22 | Advanced
-- Question:
--   Build a head-to-head match prediction analysis between teams. For each pair of teams
--   that have played at least 5 matches against each other in the last 3 years, calculate
--   total matches, wins for each team, average victory margin when each team wins,
--   performance when batting first vs bowling first at different venues, and overall win
--   percentage for each team.
-- SQL concepts: Normalised pairs with LEAST/GREATEST, derived 'batted first' team, multiple CTEs
WITH recent AS (
    SELECT m.*,
           LEAST(m.team1_id, m.team2_id)    AS team_a,
           GREATEST(m.team1_id, m.team2_id) AS team_b,
           CASE WHEN m.toss_decision = 'bat' THEN m.toss_winner_id
                WHEN m.toss_winner_id = m.team1_id THEN m.team2_id
                ELSE m.team1_id END        AS batted_first
    FROM matches m
    WHERE m.match_status = 'Completed'
      AND m.match_date  >= CURRENT_DATE - INTERVAL '3 years'
),
pairs AS (
    SELECT team_a, team_b FROM recent GROUP BY team_a, team_b HAVING COUNT(*) >= 5
)
SELECT ta.team_name || ' vs ' || tb.team_name                         AS matchup,
       ta.team_name                                                    AS team_a,
       tb.team_name                                                    AS team_b,
       COUNT(*)                                                        AS matches,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_a)                  AS team_a_wins,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_b)                  AS team_b_wins,
       COUNT(*) FILTER (WHERE r.winner_id IS NULL)                     AS no_winner,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_a
                                          AND r.victory_type = 'runs'), 1)    AS a_avg_win_runs,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_a
                                          AND r.victory_type = 'wickets'), 1) AS a_avg_win_wkts,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_b
                                          AND r.victory_type = 'runs'), 1)    AS b_avg_win_runs,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_b
                                          AND r.victory_type = 'wickets'), 1) AS b_avg_win_wkts,
       COUNT(*) FILTER (WHERE r.winner_id = r.batted_first)            AS won_batting_first,
       COUNT(*) FILTER (WHERE r.winner_id IS NOT NULL
                          AND r.winner_id <> r.batted_first)           AS won_chasing,
       COUNT(DISTINCT r.venue_id)                                      AS venues_used,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.winner_id = r.team_a) / COUNT(*), 1) AS team_a_win_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.winner_id = r.team_b) / COUNT(*), 1) AS team_b_win_pct
FROM recent r
JOIN pairs p  ON p.team_a = r.team_a AND p.team_b = r.team_b
JOIN teams ta ON ta.team_id = r.team_a
JOIN teams tb ON tb.team_id = r.team_b
GROUP BY ta.team_name, tb.team_name
ORDER BY matches DESC;
