-- Q10 | Intermediate
-- Question:
--   Get details of the last 20 completed matches. Show match description, both team names,
--   winning team, victory margin, victory type (runs/wickets), and venue name. Display
--   most recent matches first.
-- SQL concepts: View with multiple role-playing joins, LIMIT
SELECT match_description,
       team1_name,
       team2_name,
       COALESCE(winner_name, 'No winner') AS winning_team,
       victory_margin,
       victory_type,
       venue_name,
       match_date
FROM v_match_summary
WHERE match_status = 'Completed'
ORDER BY match_date DESC, match_id DESC
LIMIT 20;
