-- Q01 | Beginner
-- Question:
--   Find all players who represent India. Display their full name, playing role, batting
--   style, and bowling style.
-- SQL concepts: JOIN, WHERE, ORDER BY, COALESCE
SELECT p.full_name,
       p.playing_role,
       COALESCE(p.batting_style, 'Unknown')       AS batting_style,
       COALESCE(p.bowling_style, 'Does not bowl') AS bowling_style
FROM players p
JOIN teams   t ON t.team_id = p.team_id
WHERE t.team_name = 'India'
ORDER BY p.playing_role, p.full_name;
