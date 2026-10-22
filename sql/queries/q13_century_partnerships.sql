-- Q13 | Intermediate
-- Question:
--   Identify batting partnerships where two consecutive batsmen (batting positions next to
--   each other) scored a combined total of 100 or more runs in the same innings. Show both
--   player names, their combined partnership runs, and which innings it occurred in.
-- SQL concepts: Self-join on adjacent positions, multi-column join condition
SELECT p1.full_name            AS batter_1,
       p2.full_name            AS batter_2,
       b1.batting_position || '-' || b2.batting_position AS positions,
       b1.runs + b2.runs       AS partnership_runs,
       b1.innings_no,
       m.match_description || ' (' || m.match_date || ')' AS match
FROM batting_innings b1
JOIN batting_innings b2
  ON  b2.match_id         = b1.match_id
  AND b2.innings_no       = b1.innings_no
  AND b2.batting_position = b1.batting_position + 1
JOIN players p1 ON p1.player_id = b1.player_id
JOIN players p2 ON p2.player_id = b2.player_id
JOIN matches m  ON m.match_id   = b1.match_id
WHERE b1.runs + b2.runs >= 100
ORDER BY partnership_runs DESC, m.match_date DESC;
