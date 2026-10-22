"""IngestionService - Extract (API) -> Transform (pure functions) -> Load (SQL).

Each match is loaded in ONE transaction: venue, teams, series, match, players
and every innings row either all commit together or all roll back, so a
failure halfway can never leave a match without its innings.

Re-running is safe (idempotent): matches, teams, venues and players are
upserted on their Cricbuzz ids, and a match's innings are replaced as a whole.

Quota awareness: one scorecard call per match, plus one venue call per NEW
venue (optional) and three calls per player only if profiles are requested.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from api.client import CricbuzzClient
from core.exceptions import APIError, AppError
from database import (IngestionLogRepository, InningsRepository, MatchRepository,
                      PlayerRepository, SeriesRepository, TeamRepository, VenueRepository,
                      translate_db_error)
from services import transformers as tf
from utils.db_connection import get_engine
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class IngestionReport:
    """What happened during one ingestion run."""

    loaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    rows: int = 0

    @property
    def status(self) -> str:
        if self.failed and not self.loaded:
            return "failed"
        return "partial" if self.failed else "success"

    def summary(self) -> str:
        return (f"{len(self.loaded)} loaded, {len(self.skipped)} skipped, "
                f"{len(self.failed)} failed, {self.rows} rows")


def infer_role(batting_position: int | None, bowled: bool, keeper: bool) -> str:
    """Best-effort role from one scorecard (used when profiles are not fetched)."""
    if keeper:
        return "Wicket-keeper"
    if bowled and batting_position is not None and batting_position <= 7:
        return "All-rounder"
    if bowled:
        return "Bowler"
    return "Batsman"


class IngestionService:
    """Loads completed international matches from the API into the database."""

    def __init__(self, client: CricbuzzClient | None = None,
                 engine: Engine | None = None) -> None:
        self.client = client or CricbuzzClient()
        self.engine = engine or get_engine()
        self.log_repo = IngestionLogRepository(self.engine)

    # ------------------------------------------------------------ discovery
    def discover_completed(self, limit: int = 5) -> list[int]:
        """Cricbuzz ids of recent, completed, international Test/ODI/T20I matches."""
        ids: list[int] = []
        for _series, info, _score in tf.iter_matches(self.client.get_recent_matches(),
                                                     international_only=True):
            if not tf.map_format(info.get("matchformat")):
                continue
            if str(info.get("state", "")).lower() not in ("complete", "completed"):
                continue
            ids.append(int(info["matchid"]))
            if len(ids) >= limit:
                break
        return ids

    def already_loaded(self, cb_match_id: int) -> bool:
        with self.engine.connect() as conn:
            return bool(conn.execute(text(
                "SELECT 1 FROM matches m WHERE m.cricbuzz_match_id = :cb AND EXISTS "
                "(SELECT 1 FROM batting_innings b WHERE b.match_id = m.match_id)"),
                {"cb": cb_match_id}).scalar())

    # ------------------------------------------------------------ one match
    def ingest_match(self, cb_match_id: int, fetch_venue: bool = True) -> int:
        """Load one match; returns the number of innings rows written.

        Raises:
            AppError subclasses on API/DB failure; ValueError if the match is
            not a completed international Test/ODI/T20I.
        """
        raw = self.client.get_scorecard(cb_match_id)
        meta = tf.parse_match_meta(raw)
        if not (meta["team1"]["id"] and meta["venue"]["name"] and meta["match_date"]):
            try:                                     # optional extra detail
                meta = tf.parse_match_meta(raw, self.client.get_match_info(cb_match_id))
            except APIError as exc:
                log.warning("Match info for %s unavailable: %s", cb_match_id, exc)
        if not meta["match_format"]:
            raise ValueError("not a Test/ODI/T20I match")
        if not meta["match_date"] or not meta["team1"]["id"] or not meta["team2"]["id"]:
            raise ValueError("match header incomplete (missing date or teams)")
        innings = [i for i in tf.parse_scorecard(raw, meta) if 1 <= i.innings_no <= 4]
        if not innings:
            raise ValueError("scorecard has no innings yet")

        venue_details = None
        venue_cb = meta["venue"]["id"]
        # Newer API versions include country/capacity in match info: no extra call needed.
        if fetch_venue and venue_cb and not meta["venue"]["country"]:
            with self.engine.connect() as conn:
                known = VenueRepository.find_by_cricbuzz_id(conn, venue_cb)
            if not known:
                try:
                    venue_details = tf.parse_venue(self.client.get_venue(venue_cb))
                except APIError as exc:
                    log.warning("Venue %s details unavailable: %s", venue_cb, exc)

        try:
            return self._load(cb_match_id, meta, innings, venue_details)
        except SQLAlchemyError as exc:
            raise translate_db_error(exc) from exc

    def _load(self, cb_match_id: int, meta: dict, innings: list,
              venue_details: dict | None) -> int:
        """Write one parsed match inside a single transaction."""
        venue_cb = meta["venue"]["id"]
        with self.engine.begin() as conn:                # ONE transaction
            team_ids = {}
            for t in (meta["team1"], meta["team2"]):
                team_ids[t["id"]] = TeamRepository.upsert_api(conn, t["id"], t["name"],
                                                              t["short"])
            v = venue_details or {"venue_name": meta["venue"]["name"] or "Unknown ground",
                                  "city": meta["venue"]["city"] or "Unknown",
                                  "country": meta["venue"]["country"] or "Unknown",
                                  "capacity": meta["venue"].get("capacity")}
            venue_id = VenueRepository.find_by_cricbuzz_id(conn, venue_cb) if venue_cb else None
            if venue_id is None:
                venue_id = VenueRepository.upsert_api(conn, venue_cb, v["venue_name"], v["city"],
                                                      v["country"], v["capacity"])
            series_id = SeriesRepository.upsert_api(conn, meta["series_cb_id"],
                                                    meta["series_name"], meta["match_format"],
                                                    meta["match_date"], v["country"])
            vtype = meta["victory_type"] or "no result"
            decided = vtype in ("runs", "wickets", "innings")
            match_id = MatchRepository.upsert_api(conn, {
                "cricbuzz_match_id": cb_match_id, "series_id": series_id,
                "match_description": meta["match_description"],
                "match_format": meta["match_format"], "match_date": meta["match_date"],
                "venue_id": venue_id,
                "team1_id": team_ids[meta["team1"]["id"]],
                "team2_id": team_ids[meta["team2"]["id"]],
                "toss_winner_id": team_ids.get(meta["toss_winner_cb_id"]),
                "toss_decision": meta["toss_decision"]
                if team_ids.get(meta["toss_winner_cb_id"]) else None,
                "winner_id": team_ids.get(meta["winner_cb_id"]) if decided else None,
                "victory_margin": meta["victory_margin"] if decided else None,
                "victory_type": vtype if (not decided or team_ids.get(meta["winner_cb_id"]))
                else "no result",
                "match_status": "Completed"})

            batting_rows, bowling_rows = self._innings_rows(conn, innings, team_ids)
            InningsRepository.replace_for_match(conn, match_id, batting_rows, bowling_rows)
        return len(batting_rows) + len(bowling_rows)

    def _innings_rows(self, conn, innings, team_ids: dict) -> tuple[list[dict], list[dict]]:
        """Upsert every player seen, then build innings rows with database ids."""
        # Gather what each player did across the match to infer a role.
        seen: dict[int, dict] = {}
        for inn in innings:
            for b in inn.batting:
                if b["cricbuzz_player_id"]:
                    p = seen.setdefault(b["cricbuzz_player_id"], {
                        "name": b["name"], "team": inn.batting_team_cb_id, "pos": None,
                        "bowled": False, "keeper": False})
                    p["pos"] = min(p["pos"] or 99, b["batting_position"])
                    p["keeper"] |= b["is_keeper"]
            for bw in inn.bowling:
                if bw["cricbuzz_player_id"]:
                    p = seen.setdefault(bw["cricbuzz_player_id"], {
                        "name": bw["name"], "team": inn.bowling_team_cb_id, "pos": None,
                        "bowled": False, "keeper": False})
                    p["bowled"] |= bw["balls_bowled"] >= 6
        player_ids = {}
        for cb_id, p in seen.items():
            team_id = team_ids.get(p["team"])
            if team_id is None:
                continue
            player_ids[cb_id] = PlayerRepository.upsert_api(
                conn, cb_id, p["name"], team_id, infer_role(p["pos"], p["bowled"], p["keeper"]))

        batting_rows, bowling_rows = [], []
        for inn in innings:
            bat_team = team_ids.get(inn.batting_team_cb_id)
            bowl_team = team_ids.get(inn.bowling_team_cb_id)
            for b in inn.batting:
                pid = player_ids.get(b["cricbuzz_player_id"])
                if pid and bat_team and b["batting_position"] <= 11:
                    fours, sixes = b["fours"], b["sixes"]
                    if fours * 4 + sixes * 6 > b["runs"]:      # defensive: bad feed data
                        fours, sixes = 0, 0
                    batting_rows.append({
                        "player_id": pid, "team_id": bat_team, "innings_no": inn.innings_no,
                        "batting_position": b["batting_position"], "runs": b["runs"],
                        "balls_faced": b["balls_faced"], "fours": fours, "sixes": sixes,
                        "is_out": b["is_out"], "dismissal": b["dismissal"][:100]})
            for bw in inn.bowling:
                pid = player_ids.get(bw["cricbuzz_player_id"])
                if pid and bowl_team:
                    bowling_rows.append({
                        "player_id": pid, "team_id": bowl_team, "innings_no": inn.innings_no,
                        "balls_bowled": bw["balls_bowled"], "maidens": bw["maidens"],
                        "runs_conceded": bw["runs_conceded"],
                        "wickets": min(bw["wickets"], 10)})
        return batting_rows, bowling_rows

    # ------------------------------------------------------------ batches
    def ingest_recent(self, limit: int = 5, skip_loaded: bool = True,
                      fetch_venue: bool = True) -> IngestionReport:
        """Discover and load recent completed matches; logs the run."""
        report = IngestionReport()
        log_id = self.log_repo.start("api", "matches/v1/recent + mcenter scorecards")
        try:
            for cb_id in self.discover_completed(limit):
                if skip_loaded and self.already_loaded(cb_id):
                    report.skipped.append(f"{cb_id}: already loaded")
                    continue
                try:
                    report.rows += self.ingest_match(cb_id, fetch_venue=fetch_venue)
                    report.loaded.append(str(cb_id))
                except ValueError as exc:
                    report.skipped.append(f"{cb_id}: {exc}")
                except AppError as exc:
                    log.error("Match %s failed: %s | %s", cb_id, exc, exc.detail or "")
                    report.failed.append(f"{cb_id}: {exc}")
        except AppError as exc:                    # discovery itself failed
            report.failed.append(f"discovery: {exc}")
        finally:
            self.log_repo.finish(log_id, report.rows, report.status, report.summary())
        return report

    def refresh_career(self, player_id: int) -> int:
        """Fetch a stored API player's career stats (2 API calls)."""
        with self.engine.connect() as conn:
            cb_id = conn.execute(text("SELECT cricbuzz_player_id FROM players "
                                      "WHERE player_id = :id"), {"id": player_id}).scalar()
        if not cb_id:
            raise ValueError("Only players imported from the API have career stats online.")
        rows = tf.parse_career(self.client.get_player_batting(cb_id),
                               self.client.get_player_bowling(cb_id))
        with self.engine.begin() as conn:
            return PlayerRepository.upsert_career(conn, player_id, rows)
