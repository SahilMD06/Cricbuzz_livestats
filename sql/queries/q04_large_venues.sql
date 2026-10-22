-- Q04 | Beginner
-- Question:
--   Display all cricket venues that have a seating capacity of more than 50,000
--   spectators. Show venue name, city, country, and capacity. Order by largest capacity
--   first.
-- SQL concepts: WHERE with a numeric comparison (NULL capacities are excluded automatically)
SELECT venue_name,
       city,
       country,
       capacity
FROM venues
WHERE capacity > 50000
ORDER BY capacity DESC;
