-- Q07 | Beginner
-- Question:
--   Find the highest individual batting score achieved in each cricket format (Test, ODI,
--   T20I). Display the format and the highest score for that format.
-- SQL concepts: JOIN, GROUP BY, MAX
SELECT m.match_format,
       MAX(b.runs) AS highest_score
FROM batting_innings b
JOIN matches m ON m.match_id = b.match_id
GROUP BY m.match_format
ORDER BY CASE m.match_format WHEN 'Test' THEN 1 WHEN 'ODI' THEN 2 ELSE 3 END;
