-- Q21 | Advanced
-- Question:
--   Create a comprehensive performance ranking system for players. Combine batting
--   performance (runs scored, batting average, strike rate), bowling performance (wickets
--   taken, bowling average, economy rate), and fielding performance (catches, stumpings)
--   into a single weighted score using the given formula, and rank the top performers in
--   each cricket format.
-- SQL concepts: CTE, COALESCE for NULL-safe arithmetic, RANK() OVER (PARTITION BY)
-- Formula from the brief (its bowling line has an unbalanced parenthesis; read as):
--   batting  = runs*0.01 + batting_avg*0.5 + strike_rate*0.3
--   bowling  = wickets*2 + (50 - bowling_avg)*0.5 + (6 - economy)*2   (0 if no wickets)
--   fielding = catches*3 + stumpings*5
WITH points AS (
    SELECT s.match_format,
           p.full_name,
           p.playing_role,
           s.runs * 0.01
             + COALESCE(s.batting_average, 0) * 0.5
             + COALESCE(s.batting_strike_rate, 0) * 0.3                  AS batting_points,
           CASE WHEN s.wickets > 0 THEN
                s.wickets * 2
                + (50 - COALESCE(s.bowling_average, 50)) * 0.5
                + (6 - COALESCE(s.economy, 6)) * 2
                ELSE 0 END                                               AS bowling_points,
           s.catches * 3 + s.stumpings * 5                               AS fielding_points
    FROM player_format_stats s
    JOIN players p ON p.player_id = s.player_id
),
ranked AS (
    SELECT *,
           batting_points + bowling_points + fielding_points AS total_points,
           RANK() OVER (PARTITION BY match_format
                        ORDER BY batting_points + bowling_points + fielding_points DESC) AS format_rank
    FROM points
)
SELECT match_format,
       format_rank,
       full_name,
       playing_role,
       ROUND(batting_points, 1)  AS batting_points,
       ROUND(bowling_points, 1)  AS bowling_points,
       ROUND(fielding_points, 1) AS fielding_points,
       ROUND(total_points, 1)    AS total_points
FROM ranked
WHERE format_rank <= 10
ORDER BY CASE match_format WHEN 'Test' THEN 1 WHEN 'ODI' THEN 2 ELSE 3 END, format_rank;
