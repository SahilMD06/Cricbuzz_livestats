-- Q20 | Advanced
-- Question:
--   Analyze how many matches each player has played in different cricket formats and their
--   batting average in each format. Show the count of Test matches, ODI matches, and T20
--   matches for each player, along with their respective batting averages. Only include
--   players who have played at least 20 total matches across all formats.
-- SQL concepts: Pivot with MAX(...) FILTER, HAVING on a SUM
SELECT p.full_name,
       COALESCE(MAX(s.matches) FILTER (WHERE s.match_format = 'Test'), 0) AS test_matches,
       MAX(s.batting_average)  FILTER (WHERE s.match_format = 'Test')     AS test_avg,
       COALESCE(MAX(s.matches) FILTER (WHERE s.match_format = 'ODI'),  0) AS odi_matches,
       MAX(s.batting_average)  FILTER (WHERE s.match_format = 'ODI')      AS odi_avg,
       COALESCE(MAX(s.matches) FILTER (WHERE s.match_format = 'T20I'), 0) AS t20i_matches,
       MAX(s.batting_average)  FILTER (WHERE s.match_format = 'T20I')     AS t20i_avg,
       SUM(s.matches)                                                     AS total_matches
FROM player_format_stats s
JOIN players p ON p.player_id = s.player_id
GROUP BY p.player_id, p.full_name
HAVING SUM(s.matches) >= 20
ORDER BY total_matches DESC;
