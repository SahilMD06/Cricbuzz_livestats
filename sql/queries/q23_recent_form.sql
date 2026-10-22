-- Q23 | Advanced
-- Question:
--   Analyze recent player form and momentum. For each player's last 10 batting
--   performances, calculate average runs in the last 5 vs last 10, recent strike rate
--   trends, number of scores above 50, and a consistency score based on standard
--   deviation. Categorize players as 'Excellent Form', 'Good Form', 'Average Form', or
--   'Poor Form'.
-- SQL concepts: ROW_NUMBER() window, FILTER on window rank, STDDEV, CASE categorisation
WITH ranked AS (
    SELECT b.player_id,
           b.runs,
           b.balls_faced,
           ROW_NUMBER() OVER (PARTITION BY b.player_id
                              ORDER BY m.match_date DESC, b.match_id DESC,
                                       b.innings_no DESC) AS rn
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
),
form AS (
    SELECT player_id,
           AVG(runs) FILTER (WHERE rn <= 5)                                    AS avg_last_5,
           AVG(runs)                                                           AS avg_last_10,
           SUM(runs) FILTER (WHERE rn <= 5) * 100.0
               / NULLIF(SUM(balls_faced) FILTER (WHERE rn <= 5), 0)            AS sr_last_5,
           SUM(runs) * 100.0 / NULLIF(SUM(balls_faced), 0)                     AS sr_last_10,
           COUNT(*) FILTER (WHERE runs >= 50)                                  AS scores_50_plus,
           STDDEV_SAMP(runs)                                                   AS stddev_runs
    FROM ranked
    WHERE rn <= 10
    GROUP BY player_id
    HAVING COUNT(*) = 10                     -- needs 10 innings to judge form
)
SELECT p.full_name,
       ROUND(f.avg_last_5, 1)  AS avg_last_5,
       ROUND(f.avg_last_10, 1) AS avg_last_10,
       ROUND(f.sr_last_5, 1)   AS sr_last_5,
       ROUND(f.sr_last_10, 1)  AS sr_last_10,
       CASE WHEN f.sr_last_5 > f.sr_last_10 THEN 'Rising'
            WHEN f.sr_last_5 < f.sr_last_10 THEN 'Falling' ELSE 'Flat' END AS sr_trend,
       f.scores_50_plus,
       ROUND(f.stddev_runs, 1) AS consistency_stddev,
       CASE WHEN f.avg_last_5 >= 45 AND f.scores_50_plus >= 3 THEN 'Excellent Form'
            WHEN f.avg_last_5 >= 30                           THEN 'Good Form'
            WHEN f.avg_last_5 >= 15                           THEN 'Average Form'
            ELSE 'Poor Form' END AS form_category
FROM form f
JOIN players p ON p.player_id = f.player_id
ORDER BY f.avg_last_5 DESC;
