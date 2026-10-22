-- Q02 | Beginner
-- Question:
--   Show all cricket matches that were played in the last 30 days. Include the match
--   description, both team names, venue name with city, and the match date. Sort by most
--   recent matches first.
-- SQL concepts: View, date arithmetic (CURRENT_DATE - INTERVAL), string concatenation
SELECT match_description,
       team1_name,
       team2_name,
       venue_name || ', ' || venue_city AS venue,
       match_date,
       result_text
FROM v_match_summary
WHERE match_status = 'Completed'
  AND match_date >= CURRENT_DATE - INTERVAL '30 days'
  AND match_date <= CURRENT_DATE
ORDER BY match_date DESC, match_id DESC;
