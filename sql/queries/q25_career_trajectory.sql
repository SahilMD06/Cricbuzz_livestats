-- Q25 | Advanced
-- Question:
--   Perform a time-series analysis of player performance evolution: quarterly averages for
--   runs and strike rate, compare each quarter with the previous quarter, identify
--   improving/declining/stable quarters, determine the overall trajectory, and categorise
--   players as 'Career Ascending', 'Career Declining', or 'Career Stable'. Only analyze
--   players with data spanning at least 6 quarters and a minimum of 3 matches per quarter.
-- SQL concepts: DATE_TRUNC('quarter'), LAG() window, REGR_SLOPE, multi-stage CTE pipeline
WITH per_match AS (
    SELECT b.player_id,
           DATE_TRUNC('quarter', m.match_date)::DATE AS quarter,
           b.match_id,
           SUM(b.runs) AS runs, SUM(b.balls_faced) AS balls
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
    GROUP BY b.player_id, quarter, b.match_id
),
quarterly AS (                                  -- quarters with >= 3 matches only
    SELECT player_id, quarter,
           AVG(runs)                                AS avg_runs,
           SUM(runs) * 100.0 / NULLIF(SUM(balls), 0) AS strike_rate
    FROM per_match
    GROUP BY player_id, quarter
    HAVING COUNT(*) >= 3
),
compared AS (
    SELECT q.*,
           ROW_NUMBER() OVER w                     AS q_index,
           q.avg_runs - LAG(q.avg_runs) OVER w     AS runs_change,
           CASE WHEN q.avg_runs - LAG(q.avg_runs) OVER w >  5 THEN 'Improving'
                WHEN q.avg_runs - LAG(q.avg_runs) OVER w < -5 THEN 'Declining'
                WHEN LAG(q.avg_runs) OVER w IS NOT NULL      THEN 'Stable' END AS movement
    FROM quarterly q
    WINDOW w AS (PARTITION BY q.player_id ORDER BY q.quarter)
),
trajectory AS (
    SELECT player_id,
           COUNT(*)                                     AS quarters,
           MIN(quarter)                                 AS first_quarter,
           MAX(quarter)                                 AS last_quarter,
           ROUND(AVG(avg_runs), 1)                      AS avg_runs_overall,
           ROUND(AVG(strike_rate), 1)                   AS avg_strike_rate,
           COUNT(*) FILTER (WHERE movement = 'Improving') AS improving_q,
           COUNT(*) FILTER (WHERE movement = 'Declining') AS declining_q,
           COUNT(*) FILTER (WHERE movement = 'Stable')    AS stable_q,
           ROUND(REGR_SLOPE(avg_runs, q_index)::NUMERIC, 2) AS runs_trend_per_quarter
    FROM compared
    GROUP BY player_id
    HAVING COUNT(*) >= 6
)
SELECT p.full_name,
       t.quarters, t.first_quarter, t.last_quarter,
       t.avg_runs_overall, t.avg_strike_rate,
       t.improving_q, t.declining_q, t.stable_q,
       t.runs_trend_per_quarter,
       CASE WHEN t.runs_trend_per_quarter >  0.5 THEN 'Career Ascending'
            WHEN t.runs_trend_per_quarter < -0.5 THEN 'Career Declining'
            ELSE 'Career Stable' END AS career_phase
FROM trajectory t
JOIN players p ON p.player_id = t.player_id
ORDER BY t.runs_trend_per_quarter DESC;
