"""Metadata for the 25 analytics queries (titles, levels, chart settings).

The SQL itself lives in ``sql/queries/qNN_*.sql`` so it can be run directly in
psql/pgAdmin and read by examiners; this module only describes each query.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import PROJECT_ROOT

QUERY_DIR = PROJECT_ROOT / "sql" / "queries"
LEVELS = ("Beginner", "Intermediate", "Advanced")


@dataclass(frozen=True)
class ChartSpec:
    """How to visualise a query result (columns must exist in the result)."""

    kind: str                 # bar | barh | line | pie | scatter | grouped_bar
    x: str
    y: str | tuple[str, ...]
    color: str | None = None
    title: str = ""


@dataclass(frozen=True)
class QuerySpec:
    """One analytics question."""

    number: int
    title: str
    level: str
    file: str
    insight: str               # one line shown under the result
    chart: ChartSpec | None = None

    @property
    def path(self):
        return QUERY_DIR / self.file

    @property
    def label(self) -> str:
        return f"Q{self.number:02d} · {self.title}"

    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def question(self) -> str:
        """The question text, taken from the SQL file's header comment."""
        lines, capture = [], False
        for line in self.sql().splitlines():
            if line.startswith("-- Question:"):
                capture = True
                continue
            if line.startswith("-- SQL concepts:"):
                break
            if capture:
                lines.append(line.removeprefix("--").strip())
        return " ".join(lines)

    def concepts(self) -> str:
        for line in self.sql().splitlines():
            if line.startswith("-- SQL concepts:"):
                return line.split(":", 1)[1].strip()
        return ""


QUERIES: list[QuerySpec] = [
    QuerySpec(1, "Players representing India", "Beginner", "q01_indian_players.sql",
              "Squad composition by role.",
              ChartSpec("pie", "playing_role", "full_name", title="India squad by role")),
    QuerySpec(2, "Matches in the last 30 days", "Beginner", "q02_matches_last_30_days.sql",
              "Most recent completed matches first."),
    QuerySpec(3, "Top 10 ODI run scorers", "Beginner", "q03_top_odi_run_scorers.sql",
              "Career ODI runs.", ChartSpec("barh", "full_name", "total_runs",
                                            title="Top ODI run scorers")),
    QuerySpec(4, "Venues over 50,000 capacity", "Beginner", "q04_large_venues.sql",
              "A venue with capacity exactly 50,000 is correctly excluded.",
              ChartSpec("barh", "venue_name", "capacity", title="Largest venues")),
    QuerySpec(5, "Wins per team", "Beginner", "q05_wins_per_team.sql",
              "LEFT JOIN keeps teams with zero wins.",
              ChartSpec("bar", "team_name", "total_wins", title="Total wins")),
    QuerySpec(6, "Players per playing role", "Beginner", "q06_players_per_role.sql",
              "Role distribution.", ChartSpec("pie", "playing_role", "player_count",
                                              title="Players by role")),
    QuerySpec(7, "Highest score by format", "Beginner", "q07_highest_score_by_format.sql",
              "Highest individual innings per format.",
              ChartSpec("bar", "match_format", "highest_score", title="Highest score")),
    QuerySpec(8, "Series started in 2024", "Beginner", "q08_series_started_2024.sql",
              "Uses a date range so the start_date index can be used."),
    QuerySpec(9, "All-rounders: 1000+ runs & 50+ wickets", "Intermediate",
              "q09_allrounders_1000_50.sql", "Both conditions must hold in the same format.",
              ChartSpec("scatter", "total_runs", "total_wickets", color="match_format",
                        title="Runs vs wickets")),
    QuerySpec(10, "Last 20 completed matches", "Intermediate", "q10_last_20_completed.sql",
              "Results with margin and type."),
    QuerySpec(11, "Player performance across formats", "Intermediate",
              "q11_player_format_comparison.sql",
              "Overall average is weighted by dismissals, not an average of averages.",
              ChartSpec("grouped_bar", "full_name", ("test_runs", "odi_runs", "t20i_runs"),
                        title="Runs by format (top players)")),
    QuerySpec(12, "Home vs away performance", "Intermediate", "q12_home_vs_away.sql",
              "Home = venue country equals team country.",
              ChartSpec("grouped_bar", "team_name", ("home_win_pct", "away_win_pct"),
                        title="Win % at home vs away")),
    QuerySpec(13, "100+ consecutive-batter partnerships", "Intermediate",
              "q13_century_partnerships.sql",
              "Brief's definition: adjacent batting positions in the same innings."),
    QuerySpec(14, "Bowling performance by venue", "Intermediate", "q14_bowling_by_venue.sql",
              "Aggregated per match first, so Tests are not double counted.",
              ChartSpec("scatter", "avg_economy", "total_wickets", color="venue_name",
                        title="Economy vs wickets per bowler-venue")),
    QuerySpec(15, "Close-match performers", "Intermediate",
              "q15_close_match_performers.sql", "Close = under 50 runs or under 5 wickets.",
              ChartSpec("barh", "full_name", "avg_runs_in_close_matches",
                        title="Average runs in close matches")),
    QuerySpec(16, "Yearly batting trend since 2020", "Intermediate",
              "q16_yearly_batting_trend.sql", "Players with 5+ matches in a year.",
              ChartSpec("line", "year", "avg_runs_per_match", color="full_name",
                        title="Average runs per match by year")),
    QuerySpec(17, "Does winning the toss help?", "Advanced", "q17_toss_advantage.sql",
              "ROLLUP adds the 'Overall' row.",
              ChartSpec("bar", "toss_decision", "toss_winner_win_pct",
                        title="Win % of toss winners")),
    QuerySpec(18, "Most economical limited-overs bowlers", "Advanced",
              "q18_economical_bowlers.sql", "Economy = total runs x 6 / total balls.",
              ChartSpec("barh", "full_name", "economy_rate", title="Economy rate")),
    QuerySpec(19, "Most consistent batsmen since 2022", "Advanced",
              "q19_consistent_batsmen.sql", "Lower standard deviation = more consistent.",
              ChartSpec("scatter", "avg_runs", "stddev_runs", title="Average vs spread")),
    QuerySpec(20, "Matches and averages by format", "Advanced",
              "q20_matches_and_avg_by_format.sql", "Players with 20+ matches in total.",
              ChartSpec("grouped_bar", "full_name",
                        ("test_matches", "odi_matches", "t20i_matches"),
                        title="Matches by format (top players)")),
    QuerySpec(21, "Weighted performance ranking", "Advanced", "q21_player_ranking.sql",
              "Top 10 per format using the brief's formula. Note: wickets x 2 outweighs "
              "runs x 0.01, so the formula as given favours bowlers.",
              ChartSpec("barh", "full_name", "total_points", color="match_format",
                        title="Total points")),
    QuerySpec(22, "Head-to-head analysis", "Advanced", "q22_head_to_head.sql",
              "Pairs with 5+ meetings in the last 3 years.",
              ChartSpec("grouped_bar", "matchup", ("team_a_win_pct", "team_b_win_pct"),
                        title="Head-to-head win % (team A vs team B)")),
    QuerySpec(23, "Recent form and momentum", "Advanced", "q23_recent_form.sql",
              "Last 10 innings per player.",
              ChartSpec("pie", "form_category", "full_name", title="Players by form")),
    QuerySpec(24, "Best batting partnerships", "Advanced", "q24_best_partnerships.sql",
              "Success = partnerships over 50 runs.",
              ChartSpec("scatter", "avg_partnership", "success_rate_pct",
                        title="Average vs success rate")),
    QuerySpec(25, "Career trajectory (quarterly)", "Advanced", "q25_career_trajectory.sql",
              "Trend = regression slope of quarterly averages.",
              ChartSpec("pie", "career_phase", "full_name", title="Career phase")),
]

QUERY_BY_NUMBER = {q.number: q for q in QUERIES}
