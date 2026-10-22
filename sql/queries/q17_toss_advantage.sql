-- Q17 | Advanced
-- Question:
--   Investigate whether winning the toss gives teams an advantage in winning matches.
--   Calculate what percentage of matches are won by the team that wins the toss, broken
--   down by their toss decision (choosing to bat first or bowl first).
-- SQL concepts: GROUP BY ROLLUP (adds an 'Overall' total row), conditional counts, percentages
SELECT COALESCE(toss_decision, 'Overall')                  AS toss_decision,
       COUNT(*)                                            AS decided_matches,
       COUNT(*) FILTER (WHERE winner_id = toss_winner_id) AS won_by_toss_winner,
       ROUND(100.0 * COUNT(*) FILTER (WHERE winner_id = toss_winner_id)
             / COUNT(*), 2)                                AS toss_winner_win_pct
FROM matches
WHERE match_status = 'Completed'
  AND winner_id IS NOT NULL                -- exclude draws, ties, no results
  AND toss_winner_id IS NOT NULL
GROUP BY ROLLUP (toss_decision)
-- GROUPING() is 1 on the ROLLUP total row, so 'Overall' sorts last.
ORDER BY GROUPING(toss_decision), toss_decision;
