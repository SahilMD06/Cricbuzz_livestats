-- Q24 | Advanced
-- Question:
--   Study successful batting partnerships to identify the best player combinations. For
--   pairs of players who have batted together as consecutive batsmen (positions differ by
--   1) in at least 5 partnerships, calculate their average partnership runs, count of
--   partnerships over 50 runs, highest partnership score, and success rate (percentage of
--   good partnerships). Rank the most successful partnerships.
-- SQL concepts: Self-join, unordered pair keys (LEAST/GREATEST), RANK() window over aggregates
WITH partnerships AS (
    SELECT LEAST(b1.player_id, b2.player_id)    AS player_a,
           GREATEST(b1.player_id, b2.player_id) AS player_b,
           b1.runs + b2.runs                    AS runs
    FROM batting_innings b1
    JOIN batting_innings b2
      ON  b2.match_id         = b1.match_id
      AND b2.innings_no       = b1.innings_no
      AND b2.batting_position = b1.batting_position + 1
),
summary AS (
    SELECT player_a, player_b,
           COUNT(*)                             AS partnerships,
           ROUND(AVG(runs), 1)                  AS avg_partnership,
           COUNT(*) FILTER (WHERE runs > 50)    AS fifty_plus,
           MAX(runs)                            AS highest,
           ROUND(100.0 * COUNT(*) FILTER (WHERE runs > 50) / COUNT(*), 1) AS success_rate_pct
    FROM partnerships
    GROUP BY player_a, player_b
    HAVING COUNT(*) >= 5
)
SELECT RANK() OVER (ORDER BY s.success_rate_pct DESC, s.avg_partnership DESC) AS rank,
       pa.full_name AS batter_1,
       pb.full_name AS batter_2,
       s.partnerships, s.avg_partnership, s.fifty_plus, s.highest, s.success_rate_pct
FROM summary s
JOIN players pa ON pa.player_id = s.player_a
JOIN players pb ON pb.player_id = s.player_b
ORDER BY rank
LIMIT 25;
