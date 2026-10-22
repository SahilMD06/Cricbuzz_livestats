-- =====================================================================
--  Cricbuzz LiveStats - views.sql
--
--  Views are saved SELECT statements. They store no data; every query on
--  a view runs its SELECT against the live tables. We use them to write
--  the 4-way team/venue joins ONCE, so pages and queries stay readable.
--
--  CREATE OR REPLACE makes this file safe to re-run. Note that OR REPLACE
--  can only ADD columns at the end; to rename or reorder columns, run
--  python -m scripts.init_db --reset  (drops and recreates everything).
-- =====================================================================

-- ---------------------------------------------------------------------
--  v_match_summary - one readable row per match (team/venue names,
--  human-readable result). Used by Q2, Q10, the Home page and CRUD lists.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_match_summary AS
SELECT
    m.match_id,
    m.match_date,
    m.match_format,
    m.match_description,
    s.series_name,
    t1.team_name                       AS team1_name,
    t2.team_name                       AS team2_name,
    v.venue_name,
    v.city                             AS venue_city,
    v.country                          AS venue_country,
    tw.team_name                       AS toss_winner_name,
    m.toss_decision,
    w.team_name                        AS winner_name,
    m.victory_margin,
    m.victory_type,
    CASE
        WHEN m.match_status <> 'Completed'   THEN m.match_status
        WHEN m.victory_type = 'draw'         THEN 'Match drawn'
        WHEN m.victory_type = 'tie'          THEN 'Match tied'
        WHEN m.victory_type = 'no result'    THEN 'No result'
        WHEN m.victory_type = 'innings'
             THEN w.team_name || ' won by an innings and ' || m.victory_margin || ' runs'
        WHEN m.victory_margin = 1                                      -- singular
             THEN w.team_name || ' won by 1 ' || RTRIM(m.victory_type, 's')
        ELSE w.team_name || ' won by ' || m.victory_margin || ' ' || m.victory_type
    END                                AS result_text,
    m.match_status,
    m.source
FROM matches m
JOIN teams  t1 ON t1.team_id = m.team1_id
JOIN teams  t2 ON t2.team_id = m.team2_id
JOIN venues v  ON v.venue_id = m.venue_id
LEFT JOIN series s  ON s.series_id = m.series_id      -- series is optional
LEFT JOIN teams  tw ON tw.team_id  = m.toss_winner_id -- no toss for upcoming
LEFT JOIN teams  w  ON w.team_id   = m.winner_id;     -- no winner for draws

-- ---------------------------------------------------------------------
--  v_batting_detail - batting rows enriched with player, team, match
--  context and time buckets. Used by Q13, Q15, Q16, Q19, Q23-Q25.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_batting_detail AS
SELECT
    b.batting_id,
    b.match_id,
    m.match_date,
    m.match_format,
    m.venue_id,
    EXTRACT(YEAR FROM m.match_date)::INT            AS match_year,
    DATE_TRUNC('quarter', m.match_date)::DATE       AS match_quarter,
    b.innings_no,
    b.player_id,
    p.full_name                                      AS player_name,
    p.playing_role,
    b.team_id,
    t.team_name,
    b.batting_position,
    b.runs,
    b.balls_faced,
    b.fours,
    b.sixes,
    b.is_out,
    b.dismissal,
    b.strike_rate
FROM batting_innings b
JOIN matches m ON m.match_id  = b.match_id
JOIN players p ON p.player_id = b.player_id
JOIN teams   t ON t.team_id   = b.team_id;

-- ---------------------------------------------------------------------
--  v_bowling_detail - bowling rows with player, team and venue context.
--  Used by Q14 and Q18.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_bowling_detail AS
SELECT
    bw.bowling_id,
    bw.match_id,
    m.match_date,
    m.match_format,
    m.venue_id,
    v.venue_name,
    bw.innings_no,
    bw.player_id,
    p.full_name     AS player_name,
    bw.team_id,
    t.team_name,
    bw.balls_bowled,
    bw.overs,
    bw.maidens,
    bw.runs_conceded,
    bw.wickets,
    bw.economy
FROM bowling_innings bw
JOIN matches m ON m.match_id  = bw.match_id
JOIN venues  v ON v.venue_id  = m.venue_id
JOIN players p ON p.player_id = bw.player_id
JOIN teams   t ON t.team_id   = bw.team_id;

-- ---------------------------------------------------------------------
--  v_player_profile - player with team name; used by CRUD lists and Q1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_player_profile AS
SELECT
    p.player_id,
    p.full_name,
    t.team_name,
    t.country,
    p.playing_role,
    p.batting_style,
    p.bowling_style,
    p.date_of_birth,
    p.source
FROM players p
JOIN teams t ON t.team_id = p.team_id;
