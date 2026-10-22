"""Deterministic seed-data generator for Cricbuzz LiveStats.

Why seed data at all?
    Ten of the 25 SQL questions need years of per-innings history (e.g. Q25
    needs 6+ quarters with 3+ matches each). The free Cricbuzz API quota
    cannot backfill that, so we generate a realistic, clearly-labelled
    (source = 'seed') history that every query can run against.

How it works
    1. Reference data: 10 national teams, 25 real grounds, 140 FICTIONAL
       players (14 per team). Fictional names mean real players imported
       later from the API never collide with seed rows.
    2. Schedule: every quarter from 2021-Q1 to today, the 10 teams are
       paired into 5 bilateral series of 2-5 matches (with a bias towards
       the big rivalries), hosted at home grounds.
    3. Simulation: each match is played innings by innings - toss, batting
       order, runs/balls per batter, bowling spells, chases, results - so
       every number is internally consistent (a chase stops when the target
       is reached, bowlers' balls add up to the innings, etc.).
    4. Career stats: per-format career totals = our simulated matches PLUS a
       simulated pre-2021 career, so totals are always >= what the match
       tables contain.
    5. Verification: after loading, a set of threshold checks confirms that
       each SQL question has rows to return.

Deterministic: ``random.Random(42)`` -> the same data for the same --today.
Dates are relative to today, so "last 30 days" (Q2) always has matches.

Usage (from the project root):
    python -m scripts.seed_data              # refuses if data already exists
    python -m scripts.seed_data --reset      # wipe ALL tables first (asks)
    python -m scripts.seed_data --reset --yes
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import MetaData, insert, text

from config import ConfigError
from core.exceptions import AppError
from utils.db_connection import check_connection, get_engine
from utils.logger import get_logger

log = get_logger(__name__)

SEED = 42
HISTORY_START = date(2021, 1, 1)

# --------------------------------------------------------------------------
#  Reference data
# --------------------------------------------------------------------------
# (team_name, short_name, country, home_venue_country, strength)
TEAMS: list[tuple[str, str, str, str, float]] = [
    ("India", "IND", "India", "India", 1.08),
    ("Australia", "AUS", "Australia", "Australia", 1.07),
    ("England", "ENG", "England", "England", 1.03),
    ("South Africa", "RSA", "South Africa", "South Africa", 1.02),
    ("New Zealand", "NZ", "New Zealand", "New Zealand", 1.00),
    ("Pakistan", "PAK", "Pakistan", "Pakistan", 0.99),
    ("Sri Lanka", "SL", "Sri Lanka", "Sri Lanka", 0.95),
    ("West Indies", "WI", "West Indies", "West Indies", 0.94),
    ("Bangladesh", "BAN", "Bangladesh", "Bangladesh", 0.92),
    # Afghanistan host their "home" games in the UAE -> counted as AWAY in Q12.
    ("Afghanistan", "AFG", "Afghanistan", "United Arab Emirates", 0.93),
]

# (venue_name, city, country, capacity) - approximate public capacities.
# Sharjah has capacity NULL on purpose, to exercise NULL handling (Q4).
VENUES: list[tuple[str, str, str, int | None]] = [
    ("Narendra Modi Stadium", "Ahmedabad", "India", 132000),
    ("Eden Gardens", "Kolkata", "India", 68000),
    ("M. A. Chidambaram Stadium", "Chennai", "India", 50000),  # boundary case for > 50000
    ("M. Chinnaswamy Stadium", "Bengaluru", "India", 40000),
    ("Wankhede Stadium", "Mumbai", "India", 33108),
    ("Melbourne Cricket Ground", "Melbourne", "Australia", 100024),
    ("Perth Stadium", "Perth", "Australia", 60000),
    ("Adelaide Oval", "Adelaide", "Australia", 53583),
    ("Sydney Cricket Ground", "Sydney", "Australia", 48000),
    ("The Gabba", "Brisbane", "Australia", 37000),
    ("Lord's", "London", "England", 31100),
    ("The Oval", "London", "England", 27500),
    ("Old Trafford", "Manchester", "England", 26000),
    ("Edgbaston", "Birmingham", "England", 25000),
    ("Newlands", "Cape Town", "South Africa", 25000),
    ("Wanderers Stadium", "Johannesburg", "South Africa", 34000),
    ("Eden Park", "Auckland", "New Zealand", 42000),
    ("Hagley Oval", "Christchurch", "New Zealand", 18000),
    ("Gaddafi Stadium", "Lahore", "Pakistan", 27000),
    ("National Stadium", "Karachi", "Pakistan", 34228),
    ("R. Premadasa Stadium", "Colombo", "Sri Lanka", 35000),
    ("Kensington Oval", "Bridgetown", "West Indies", 28000),
    ("Shere Bangla National Stadium", "Dhaka", "Bangladesh", 25000),
    ("Dubai International Cricket Stadium", "Dubai", "United Arab Emirates", 25000),
    ("Sharjah Cricket Stadium", "Sharjah", "United Arab Emirates", None),
]

# Name pools for FICTIONAL players, keyed by team.
NAME_POOLS: dict[str, tuple[list[str], list[str]]] = {
    "India": (["Aarav", "Rohan", "Vikram", "Arjun", "Karan", "Siddharth", "Aditya",
               "Nikhil", "Pranav", "Varun", "Kunal", "Dev", "Ishaan"],
              ["Mehra", "Iyer", "Patil", "Reddy", "Nair", "Kulkarni", "Rathore",
               "Menon", "Chauhan", "Joshi", "Bhat", "Saxena", "Gill"]),
    "Australia": (["Liam", "Cooper", "Mitchell", "Jack", "Riley", "Hamish", "Noah",
                   "Lachlan", "Brody", "Tom", "Callum", "Jarrod", "Fraser"],
                  ["Harper", "Whitfield", "Doyle", "Prentice", "Bancroft", "Kellaway",
                   "Ashby", "Thornton", "McLeod", "Granger", "Pryce", "Dalton", "Wren"]),
    "England": (["Oliver", "Harry", "George", "Freddie", "Alfie", "Ben", "Rory",
                 "Toby", "Ethan", "Max", "Archie", "Joe", "Sam"],
                ["Ashworth", "Pemberton", "Holloway", "Carver", "Fenwick", "Blackwood",
                 "Hartley", "Langford", "Mercer", "Thorne", "Whitlock", "Sutton", "Rowe"]),
    "South Africa": (["Thabo", "Pieter", "Sipho", "Ruan", "Kagiso", "Dewald", "Lungile",
                      "Jacques", "Mandla", "Wiaan", "Tristan", "Kyle", "Bongani"],
                     ["van Wyk", "Botha", "Nkosi", "Pretorius", "Mokoena", "du Toit",
                      "Mahlangu", "Coetzee", "Dlamini", "Venter", "Steyn", "Ndlovu", "Kruger"]),
    "New Zealand": (["Tane", "Hunter", "Blair", "Finn", "Corey", "Ross", "Wiremu",
                     "Logan", "Hayden", "Mason", "Jesse", "Reid", "Nathan"],
                    ["Paterson", "Ngata", "McCrae", "Tipene", "Sinclair", "Rangi",
                     "Fleming", "Hobson", "Kerr", "Waititi", "Dunlop", "Ormsby", "Lyall"]),
    "Pakistan": (["Hamza", "Bilal", "Usman", "Faheem", "Zain", "Haris", "Saad",
                  "Imad", "Junaid", "Rizwan", "Shadab", "Kamran", "Talha"],
                 ["Qureshi", "Siddiqui", "Malik", "Abbasi", "Chaudhry", "Durrani",
                  "Raza", "Mirza", "Butt", "Shah", "Jamil", "Niazi", "Aslam"]),
    "Sri Lanka": (["Kasun", "Dilan", "Nuwan", "Charith", "Pathum", "Lahiru", "Isuru",
                   "Dushan", "Ravindu", "Chamika", "Sahan", "Minod", "Asitha"],
                  ["Perera", "Fernando", "Jayasinghe", "Wickramasinghe", "Bandara",
                   "Rajapaksha", "Herath", "Gunaratne", "Silva", "Dissanayake",
                   "Kumara", "Wijesinghe", "Rathnayake"]),
    "West Indies": (["Andre", "Shai", "Kemar", "Jaden", "Rovman", "Akeem", "Darnell",
                     "Kevon", "Jermaine", "Shamar", "Tevin", "Odean", "Romario"],
                    ["Joseph", "Charles", "Greaves", "Walcott", "Holder", "Mayers",
                     "Bascombe", "Forde", "Carty", "Alleyne", "Thomas", "Gittens", "Lewis"]),
    "Bangladesh": (["Tanvir", "Mahmud", "Rakib", "Sabbir", "Nayeem", "Arif", "Tawhid",
                    "Rishad", "Parvez", "Shoriful", "Mominul", "Yasir", "Afif"],
                   ["Hossain", "Rahman", "Islam", "Ahmed", "Karim", "Chowdhury",
                    "Sarkar", "Uddin", "Haque", "Alam", "Mia", "Talukder", "Kabir"]),
    "Afghanistan": (["Rahim", "Noor", "Farid", "Ihsan", "Zubair", "Qais", "Hashmat",
                     "Sediq", "Waheed", "Karim", "Hazrat", "Najib", "Azmat"],
                    ["Zadran", "Safi", "Stanikzai", "Shinwari", "Atal", "Kharoti",
                     "Omarzai", "Ahmadzai", "Hamidi", "Mangal", "Jalal", "Wardak", "Sultani"]),
}

# Squad template: batting order is the squad order. Index 4 and 12 are the
# rotation players (5th batter, 5th bowler). Index 13 is an uncapped youngster
# who only plays as an injury replacement, so some players have few matches
# (lets thresholds like Q20's "20+ matches" visibly filter someone out).
SQUAD_ROLES = ["Batsman"] * 5 + ["Wicket-keeper"] + ["All-rounder"] * 2 + ["Bowler"] * 5
DEBUTANT_SLOT = 13
PACE_STYLES = ["Right-arm fast", "Right-arm fast-medium", "Left-arm fast", "Right-arm medium"]
SPIN_STYLES = ["Right-arm offbreak", "Legbreak googly", "Slow left-arm orthodox"]

# Per-format simulation parameters.
FMT = {
    "Test": dict(run_factor=1.05, sr=52, ball_cap=900, quota=None, cap_score=300,
                 extras=(8, 25), boundary=(0.40, 0.60), six=0.10, maiden_p=0.20),
    "ODI": dict(run_factor=1.18, sr=90, ball_cap=300, quota=60, cap_score=200,
                extras=(4, 15), boundary=(0.45, 0.65), six=0.25, maiden_p=0.07),
    "T20I": dict(run_factor=0.78, sr=138, ball_cap=120, quota=24, cap_score=130,
                 extras=(2, 10), boundary=(0.55, 0.75), six=0.40, maiden_p=0.02),
}
RIVALRIES = [("India", "Australia", 0.55), ("England", "Australia", 0.45),
             ("India", "England", 0.30), ("India", "Pakistan", 0.20)]


# --------------------------------------------------------------------------
#  In-memory model
# --------------------------------------------------------------------------
@dataclass
class Player:
    """A seed player and the hidden skill numbers used by the simulator."""

    player_id: int
    team_id: int
    full_name: str
    role: str
    slot: int                 # squad index 0-12 (= preferred batting order)
    bat_mean: float           # expected ODI runs per innings before modifiers
    sr_factor: float
    bowls: bool
    econ_factor: float        # <1 = economical
    wkt_weight: float
    spinner: bool
    experience: int           # international years before 2021
    batting_style: str
    bowling_style: str | None
    date_of_birth: date


@dataclass
class Team:
    team_id: int
    name: str
    short: str
    country: str
    home_country: str
    strength: float
    squad: list[Player] = field(default_factory=list)


@dataclass
class Innings:
    """Result of one simulated innings."""

    batting: list[dict]
    bowling: list[dict]
    total: int
    wickets: int
    balls: int
    target_reached: bool = False


@dataclass
class Rows:
    """All rows to insert, keyed by table name."""

    teams: list[dict] = field(default_factory=list)
    venues: list[dict] = field(default_factory=list)
    players: list[dict] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)
    matches: list[dict] = field(default_factory=list)
    batting_innings: list[dict] = field(default_factory=list)
    bowling_innings: list[dict] = field(default_factory=list)
    player_format_stats: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------
#  Generator
# --------------------------------------------------------------------------
class SeedGenerator:
    """Builds every seed row in memory; ``SeedLoader`` writes them."""

    def __init__(self, today: date, seed: int = SEED) -> None:
        self.today = today
        self.rng = random.Random(seed)
        self.rows = Rows()
        self.teams: dict[int, Team] = {}
        self.players: dict[int, Player] = {}
        self.venues_by_country: dict[str, list[int]] = defaultdict(list)
        self.fielding: dict[tuple[int, str], dict[str, int]] = defaultdict(
            lambda: {"catches": 0, "stumpings": 0})
        self.next_match_id = 1
        self.next_series_id = 1

    # ---------------- reference data ----------------
    def build_reference_data(self) -> None:
        """Create teams, venues and 13-player squads."""
        for i, (name, short, country, home, strength) in enumerate(TEAMS, start=1):
            self.teams[i] = Team(i, name, short, country, home, strength)
            self.rows.teams.append(dict(team_id=i, team_name=name, short_name=short,
                                        country=country, team_type="international"))
        for i, (vname, city, country, cap) in enumerate(VENUES, start=1):
            self.venues_by_country[country].append(i)
            self.rows.venues.append(dict(venue_id=i, venue_name=vname, city=city,
                                         country=country, capacity=cap))
        pid = 1
        used_names: set[str] = set()
        for team in self.teams.values():
            firsts, lasts = NAME_POOLS[team.name]
            debutant_role = "Batsman" if team.team_id % 2 else "Bowler"
            for slot, role in enumerate(SQUAD_ROLES + [debutant_role]):
                name = self._unique_name(firsts, lasts, used_names)
                player = self._make_player(pid, team, slot, role, name)
                team.squad.append(player)
                self.players[pid] = player
                self.rows.players.append(dict(
                    player_id=pid, full_name=name, team_id=team.team_id,
                    playing_role=role, batting_style=player.batting_style,
                    bowling_style=player.bowling_style,
                    date_of_birth=player.date_of_birth, source="seed"))
                pid += 1

    def _unique_name(self, firsts: list[str], lasts: list[str], used: set[str]) -> str:
        while True:
            name = f"{self.rng.choice(firsts)} {self.rng.choice(lasts)}"
            if name not in used:
                used.add(name)
                return name

    def _make_player(self, pid: int, team: Team, slot: int, role: str, name: str) -> Player:
        """Assign hidden skills based on role and batting slot."""
        rng = self.rng
        bat_mean = {0: (34, 45), 1: (32, 43), 2: (38, 48), 3: (28, 38), 4: (26, 36),
                    5: (24, 32), 6: (20, 30), 7: (18, 27)}.get(slot, (4, 12))
        if slot == DEBUTANT_SLOT and role == "Batsman":
            bat_mean = (22, 32)
        bowls = role in ("Bowler", "All-rounder")
        spinner = bowls and rng.random() < 0.35
        if role == "Bowler":
            econ, wkt = rng.uniform(0.85, 1.02), rng.uniform(1.0, 1.4)
        elif role == "All-rounder":
            econ, wkt = rng.uniform(0.95, 1.10), rng.uniform(0.7, 1.0)
        else:
            econ, wkt = 1.15, 0.3
        if bowls:
            bowling_style = rng.choice(SPIN_STYLES if spinner else PACE_STYLES)
        elif role == "Batsman" and rng.random() < 0.35:
            bowling_style = "Right-arm offbreak"   # part-timer
        else:
            bowling_style = None
        experience = rng.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
        if role == "All-rounder" and slot == 6:
            experience = max(experience, 7)       # guarantees seasoned all-rounders (Q9)
        if slot == DEBUTANT_SLOT:
            experience = 0
        age_2021 = 19 + experience + rng.randint(0, 4)
        if slot == DEBUTANT_SLOT:
            age_2021 = rng.randint(15, 17)
        dob = date(2021 - age_2021, rng.randint(1, 12), rng.randint(1, 28))
        return Player(
            player_id=pid, team_id=team.team_id, full_name=name, role=role, slot=slot,
            bat_mean=rng.uniform(*bat_mean), sr_factor=rng.gauss(1.0, 0.10),
            bowls=bowls, econ_factor=econ, wkt_weight=wkt, spinner=spinner,
            experience=experience,
            batting_style="Left-hand bat" if rng.random() < 0.3 else "Right-hand bat",
            bowling_style=bowling_style, date_of_birth=dob)

    # ---------------- schedule ----------------
    def build_schedule(self) -> list[dict]:
        """Return planned matches (dicts) for every quarter up to today."""
        planned: list[dict] = []
        q_start = HISTORY_START
        while q_start <= self.today:
            for t1, t2 in self._pair_teams():
                planned.extend(self._plan_series(t1, t2, q_start))
            q_start = _add_months(q_start, 3)
        # Guarantee recent matches for "last 30 days" queries (Q2).
        recent = [m for m in planned
                  if self.today - timedelta(days=30) <= m["match_date"] < self.today]
        if len(recent) < 4:
            planned.extend(self._plan_series(1, 3, self.today - timedelta(days=14),
                                             fmt="T20I", n=3, fixed_start=True))
        return planned

    def _pair_teams(self) -> list[tuple[int, int]]:
        """Pair the 10 teams into 5 opponents, favouring the big rivalries."""
        ids = {t.name: t.team_id for t in self.teams.values()}
        free = set(self.teams)
        pairs: list[tuple[int, int]] = []
        for a, b, prob in RIVALRIES:
            if ids[a] in free and ids[b] in free and self.rng.random() < prob:
                pairs.append((ids[a], ids[b]))
                free -= {ids[a], ids[b]}
        rest = sorted(free)
        self.rng.shuffle(rest)
        pairs.extend(zip(rest[0::2], rest[1::2]))
        return pairs

    def _plan_series(self, t1: int, t2: int, q_start: date, *, fmt: str | None = None,
                     n: int | None = None, fixed_start: bool = False) -> list[dict]:
        """Plan one bilateral series and add its row to ``rows.series``."""
        rng = self.rng
        fmt = fmt or rng.choices(["ODI", "T20I", "Test"], weights=[0.4, 0.4, 0.2])[0]
        n = n or (rng.randint(2, 4) if fmt == "Test" else rng.randint(3, 5))
        host, visitor = (t1, t2) if rng.random() < 0.5 else (t2, t1)
        host_team, visitor_team = self.teams[host], self.teams[visitor]
        gap = {"Test": 8, "ODI": 3, "T20I": 2}[fmt]
        start = q_start if fixed_start else q_start + timedelta(days=rng.randint(0, 60))
        dates = [start + timedelta(days=i * gap) for i in range(n)]

        sid = self.next_series_id
        self.next_series_id += 1
        if host_team.home_country == host_team.country:
            title = f"{visitor_team.name} tour of {host_team.name}"
        else:
            title = f"{host_team.name} v {visitor_team.name} in {host_team.home_country}"
        self.rows.series.append(dict(
            series_id=sid, series_name=f"{title} {start.year} - {fmt} series",
            host_country=host_team.home_country, match_type=fmt,
            start_date=dates[0], end_date=dates[-1] + timedelta(days=4 if fmt == "Test" else 0),
            total_matches_planned=n, source="seed"))
        venues = self.venues_by_country[host_team.home_country]
        return [dict(series_id=sid, fmt=fmt, n=i + 1, match_date=d, host=host,
                     visitor=visitor, venue_id=rng.choice(venues))
                for i, d in enumerate(dates)]

    # ---------------- simulation ----------------
    def play_all(self, planned: list[dict]) -> None:
        """Simulate every planned match (or store it as Upcoming)."""
        for plan in sorted(planned, key=lambda m: m["match_date"]):
            match_id = self.next_match_id
            self.next_match_id += 1
            row = dict(match_id=match_id, series_id=plan["series_id"],
                       match_description=f"{_ordinal(plan['n'])} {plan['fmt']}",
                       match_format=plan["fmt"], match_date=plan["match_date"],
                       venue_id=plan["venue_id"], team1_id=plan["host"],
                       team2_id=plan["visitor"], source="seed")
            if plan["match_date"] >= self.today:
                row.update(match_status="Upcoming", toss_winner_id=None,
                           toss_decision=None, winner_id=None,
                           victory_margin=None, victory_type=None)
            else:
                row.update(self._play_match(match_id, plan))
            self.rows.matches.append(row)

    def _select_xi(self, team: Team, fmt: str) -> list[Player]:
        """Pick the playing XI in batting order, with format-based rotation."""
        s = team.squad
        batters = [s[0], s[1], s[2], s[4] if fmt == "T20I" else s[3]]
        bowlers = [s[8], s[9], s[10], s[12] if fmt == "T20I" else s[11]]
        xi = batters + [s[5], s[6], s[7]] + bowlers
        if self.rng.random() < 0.15:                      # occasional injury/rest
            out = self.rng.randrange(1, 11)
            bench = [p for p in s if p not in xi]
            xi[out] = self.rng.choice(bench)
        return xi

    def _play_match(self, match_id: int, plan: dict) -> dict:
        """Simulate a completed match; returns toss/result columns."""
        rng, fmt = self.rng, plan["fmt"]
        host, visitor = self.teams[plan["host"]], self.teams[plan["visitor"]]
        xis = {host.team_id: self._select_xi(host, fmt),
               visitor.team_id: self._select_xi(visitor, fmt)}
        toss_winner = rng.choice([host.team_id, visitor.team_id])
        bat_prob = {"Test": 0.7, "ODI": 0.4, "T20I": 0.35}[fmt]
        decision = "bat" if rng.random() < bat_prob else "bowl"
        other = visitor.team_id if toss_winner == host.team_id else host.team_id
        a, b = (toss_winner, other) if decision == "bat" else (other, toss_winner)
        home_boost = {host.team_id: 1.06, visitor.team_id: 1.0}

        def innings(no: int, bat: int, bowl: int, cap: int, target: int | None = None) -> Innings:
            inn = self._simulate_innings(xis[bat], xis[bowl], fmt, cap, target,
                                         self.teams[bat].strength * home_boost[bat],
                                         self.teams[bowl].strength * home_boost[bowl])
            for r in inn.batting:
                r.update(match_id=match_id, team_id=bat, innings_no=no)
            for r in inn.bowling:
                r.update(match_id=match_id, team_id=bowl, innings_no=no)
            self.rows.batting_innings.extend(inn.batting)
            self.rows.bowling_innings.extend(inn.bowling)
            self._record_fielding(inn, fmt)
            return inn

        result = dict(toss_winner_id=toss_winner, toss_decision=decision,
                      match_status="Completed")
        cap = FMT[fmt]["ball_cap"]
        if fmt != "Test":
            first = innings(1, a, b, cap)
            second = innings(2, b, a, cap, target=first.total + 1)
            if second.target_reached:
                result.update(winner_id=b, victory_type="wickets",
                              victory_margin=10 - second.wickets)
            elif second.total == first.total:
                result.update(winner_id=None, victory_type="tie", victory_margin=None)
            else:
                result.update(winner_id=a, victory_type="runs",
                              victory_margin=first.total - second.total)
            return result

        # Test match: A, B, A, then B chases (or B wins by an innings).
        i1 = innings(1, a, b, cap)
        i2 = innings(2, b, a, cap)
        i3 = innings(3, a, b, 600)
        lead_needed = i1.total + i3.total - i2.total
        if lead_needed < 0:
            result.update(winner_id=b, victory_type="innings", victory_margin=-lead_needed)
            return result
        i4 = innings(4, b, a, 540, target=lead_needed + 1)
        if i4.target_reached:
            result.update(winner_id=b, victory_type="wickets", victory_margin=10 - i4.wickets)
        elif i4.wickets == 10:
            margin = lead_needed - i4.total
            if margin == 0:
                result.update(winner_id=None, victory_type="tie", victory_margin=None)
            else:
                result.update(winner_id=a, victory_type="runs", victory_margin=margin)
        else:
            result.update(winner_id=None, victory_type="draw", victory_margin=None)
        return result

    def _sample_runs(self, player: Player, fmt: str, strength: float) -> int:
        """Gamma-distributed score: many low scores, occasional big ones."""
        mean = max(1.5, player.bat_mean * FMT[fmt]["run_factor"] * strength)
        runs = self.rng.gammavariate(1.1, mean / 1.1)
        return int(min(runs, FMT[fmt]["cap_score"]))

    def _simulate_innings(self, bat_xi: list[Player], bowl_xi: list[Player], fmt: str,
                          ball_cap: int, target: int | None, bat_strength: float,
                          bowl_strength: float) -> Innings:
        """Simulate one innings batter by batter, then derive bowling figures."""
        rng, p = self.rng, FMT[fmt]
        extras = rng.randint(*p["extras"])
        total, balls_used, wickets = extras, 0, 0
        batting: list[dict] = []
        outs: list[Player] = []
        reached = False
        # Strong bowling attacks reduce runs a little.
        strength = bat_strength / bowl_strength

        for pos, batter in enumerate(bat_xi, start=1):
            runs = self._sample_runs(batter, fmt, strength)
            tail = 0.75 if batter.slot >= 8 else 1.0
            sr = max(20.0, rng.gauss(p["sr"], p["sr"] * 0.15) * batter.sr_factor * tail)
            balls = max(1, round(runs * 100 / sr)) if runs else rng.randint(1, 8)
            is_out = pos < 11
            end = False
            if balls_used + balls >= ball_cap:                    # overs run out
                balls = max(1, ball_cap - balls_used)
                runs = min(runs, round(balls * sr / 100))
                is_out, end = False, True
            if target is not None and total + runs >= target:     # target reached
                runs = max(0, target - total) + rng.choice([0, 0, 0, 1, 2, 3])
                balls = max(1, min(balls, round(runs * 100 / sr) or 1))
                is_out, end, reached = False, True, True
            fours, sixes = self._boundaries(runs, fmt)
            balls = max(balls, fours + sixes)
            total += runs
            balls_used += balls
            batting.append(dict(player_id=batter.player_id, batting_position=pos,
                                runs=runs, balls_faced=balls, fours=fours, sixes=sixes,
                                is_out=is_out, dismissal=None if is_out else "not out"))
            if is_out:
                wickets += 1
                outs.append(batter)
            if end:
                if pos == 11 and batting[-2]["is_out"]:
                    # No. 11 finished the innings, so No. 10 was still batting
                    # with him: un-dismiss No. 10 (max 9 wickets, never 10).
                    batting[-2].update(is_out=False, dismissal="not out")
                    wickets -= 1
                    outs.pop()
                break

        bowling = self._bowling_figures(bowl_xi, fmt, balls_used, total - extras, batting, outs)
        return Innings(batting, bowling, total, wickets, balls_used, reached)

    def _boundaries(self, runs: int, fmt: str) -> tuple[int, int]:
        """Split runs into fours/sixes so that 4*fours + 6*sixes <= runs."""
        p = FMT[fmt]
        boundary_runs = int(runs * self.rng.uniform(*p["boundary"]))
        sixes = int(boundary_runs * self.rng.uniform(0, 2 * p["six"]) / 6)
        fours = (boundary_runs - 6 * sixes) // 4
        return fours, sixes

    def _bowling_figures(self, bowl_xi: list[Player], fmt: str, balls: int, bat_runs: int,
                         batting: list[dict], outs: list[Player]) -> list[dict]:
        """Share the innings' balls, runs and wickets among the bowlers."""
        rng, p = self.rng, FMT[fmt]
        attack = [pl for pl in bowl_xi if pl.bowls]
        quota = p["quota"]
        overs_total = math.ceil(balls / 6)
        overs = {pl.player_id: 0 for pl in attack}
        weights = {pl.player_id: 1.0 if pl.role == "Bowler" else 0.55 for pl in attack}
        for _ in range(overs_total):
            options = [pid for pid in overs if quota is None or overs[pid] * 6 < quota]
            if not options:                      # everyone at quota: part-timer bowls
                options = list(overs)
            pick = rng.choices(options, weights=[weights[o] for o in options])[0]
            overs[pick] += 1
        bowled = {pid: o * 6 for pid, o in overs.items() if o}
        if balls % 6 and bowled:                  # last over unfinished
            last = rng.choice(list(bowled))
            bowled[last] = max(1, bowled[last] - (6 - balls % 6))

        by_id = {pl.player_id: pl for pl in attack}
        cost = {pid: b * by_id[pid].econ_factor * rng.uniform(0.75, 1.25)
                for pid, b in bowled.items()}
        cost_sum = sum(cost.values()) or 1.0
        conceded = {pid: round(bat_runs * c / cost_sum) for pid, c in cost.items()}

        wickets = {pid: 0 for pid in bowled}
        keeper = next((pl for pl in bowl_xi if pl.role == "Wicket-keeper"), bowl_xi[0])
        fielders = [pl for pl in bowl_xi]
        out_rows = [r for r in batting if r["is_out"]]
        for row in out_rows:
            if rng.random() < 0.06 or not bowled:
                row["dismissal"] = f"run out ({rng.choice(fielders).full_name})"
                continue
            pid = rng.choices(list(bowled),
                              weights=[by_id[i].wkt_weight * bowled[i] for i in bowled])[0]
            wickets[pid] += 1
            bowler = by_id[pid].full_name
            roll = rng.random()
            if roll < 0.55:
                catcher = keeper if rng.random() < 0.3 else rng.choice(fielders)
                row["dismissal"] = (f"c & b {bowler}" if catcher.player_id == pid
                                    else f"c {catcher.full_name} b {bowler}")
                row["_catcher"] = catcher.player_id
            elif roll < 0.78:
                row["dismissal"] = f"b {bowler}"
            elif roll < 0.95 or not by_id[pid].spinner:
                row["dismissal"] = f"lbw b {bowler}"
            else:
                row["dismissal"] = f"st {keeper.full_name} b {bowler}"
                row["_stumper"] = keeper.player_id

        figures = []
        for pid, b in bowled.items():
            full_overs = b // 6
            maidens = sum(rng.random() < p["maiden_p"] for _ in range(full_overs))
            figures.append(dict(player_id=pid, balls_bowled=b, maidens=maidens,
                                runs_conceded=max(0, conceded[pid]), wickets=wickets[pid]))
        return figures

    def _record_fielding(self, inn: Innings, fmt: str) -> None:
        """Count catches/stumpings for career fielding stats; strip temp keys."""
        for row in inn.batting:
            if "_catcher" in row:
                self.fielding[(row.pop("_catcher"), fmt)]["catches"] += 1
            if "_stumper" in row:
                self.fielding[(row.pop("_stumper"), fmt)]["stumpings"] += 1

    # ---------------- career stats ----------------
    def build_career_stats(self) -> None:
        """Career totals per format = simulated matches + simulated pre-2021 career."""
        rng = self.rng
        fmt_of = {m["match_id"]: m["match_format"] for m in self.rows.matches}
        agg: dict[tuple[int, str], dict] = defaultdict(lambda: dict(
            matches=set(), innings=0, runs=0, not_outs=0, balls_faced=0, scores=[],
            balls_bowled=0, runs_conceded=0, wickets=0))
        for r in self.rows.batting_innings:
            a = agg[(r["player_id"], fmt_of[r["match_id"]])]
            a["matches"].add(r["match_id"])
            a["innings"] += 1
            a["runs"] += r["runs"]
            a["not_outs"] += 0 if r["is_out"] else 1
            a["balls_faced"] += r["balls_faced"]
            a["scores"].append(r["runs"])
        for r in self.rows.bowling_innings:
            a = agg[(r["player_id"], fmt_of[r["match_id"]])]
            a["matches"].add(r["match_id"])
            a["balls_bowled"] += r["balls_bowled"]
            a["runs_conceded"] += r["runs_conceded"]
            a["wickets"] += r["wickets"]

        per_year = {"Test": 5, "ODI": 13, "T20I": 9}
        bowl_balls = {"Test": 150, "ODI": 48, "T20I": 22}
        strike = {"Test": 62, "ODI": 38, "T20I": 21}
        for player in self.players.values():
            for fmt in ("Test", "ODI", "T20I"):
                a = agg.get((player.player_id, fmt))
                prior_m = int(player.experience * per_year[fmt] * rng.uniform(0.5, 1.0))
                if fmt == "T20I" and player.slot == 3:
                    prior_m //= 3              # Test/ODI specialist
                if not a and prior_m == 0:
                    continue
                a = a or agg[(player.player_id, fmt)]
                # Pre-2021 batting: simulate each prior innings for realistic 50s/100s.
                inn_per_match = 1.8 if fmt == "Test" else 0.9
                prior_inn = int(prior_m * inn_per_match * (0.6 if player.slot >= 8 else 1.0))
                prior_scores = [self._sample_runs(player, fmt, 1.0) for _ in range(prior_inn)]
                no_rate = 0.25 if player.slot >= 8 else 0.09
                prior_no = sum(rng.random() < no_rate for _ in range(prior_inn))
                sr_est = FMT[fmt]["sr"] * player.sr_factor * (0.75 if player.slot >= 8 else 1)
                scores = a["scores"] + prior_scores
                innings = a["innings"] + prior_inn
                runs = a["runs"] + sum(prior_scores)
                not_outs = min(innings, a["not_outs"] + prior_no)
                balls_faced = a["balls_faced"] + round(sum(prior_scores) * 100 / sr_est)
                # Pre-2021 bowling.
                pb = 0
                if player.bowls:
                    share = 1.0 if player.role == "Bowler" else 0.5
                    pb = int(prior_m * bowl_balls[fmt] * share * rng.uniform(0.8, 1.1))
                p_conc = round(pb * FMT[fmt]["sr"] / 100 * player.econ_factor
                               * rng.uniform(0.85, 1.0) * (0.55 if fmt == "Test" else 0.95))
                p_wkts = round(pb / (strike[fmt] / player.wkt_weight) * rng.uniform(0.8, 1.2))
                balls_bowled = a["balls_bowled"] + pb
                conceded = a["runs_conceded"] + p_conc
                wkts = a["wickets"] + p_wkts
                matches = len(a["matches"]) + prior_m
                field_db = self.fielding.get((player.player_id, fmt),
                                             {"catches": 0, "stumpings": 0})
                keeper = player.role == "Wicket-keeper"
                catches = field_db["catches"] + int(prior_m * (1.6 if keeper else 0.35))
                stumpings = field_db["stumpings"] + (int(prior_m * 0.12) if keeper else 0)
                dismissals = innings - not_outs
                self.rows.player_format_stats.append(dict(
                    player_id=player.player_id, match_format=fmt, matches=matches,
                    innings=innings, runs=runs,
                    highest_score=max(scores) if scores else None,
                    batting_average=round(runs / dismissals, 2) if dismissals else None,
                    batting_strike_rate=round(runs * 100 / balls_faced, 2) if balls_faced else None,
                    hundreds=sum(s >= 100 for s in scores),
                    fifties=sum(50 <= s < 100 for s in scores),
                    balls_bowled=balls_bowled, wickets=wkts,
                    bowling_average=round(conceded / wkts, 2) if wkts else None,
                    economy=round(conceded * 6 / balls_bowled, 2) if balls_bowled else None,
                    catches=catches, stumpings=stumpings))

    def generate(self) -> Rows:
        """Run every step and return the rows."""
        self.build_reference_data()
        self.play_all(self.build_schedule())
        self.build_career_stats()
        return self.rows


# --------------------------------------------------------------------------
#  Loader + verification
# --------------------------------------------------------------------------
INSERT_ORDER = ["teams", "venues", "players", "series", "matches",
                "batting_innings", "bowling_innings", "player_format_stats"]
EXPLICIT_ID_TABLES = {"teams": "team_id", "venues": "venue_id", "players": "player_id",
                      "series": "series_id", "matches": "match_id"}

# Simplified threshold checks - NOT the final answers to the 25 questions.
CHECKS: list[tuple[str, str]] = [
    ("Q2  completed matches in last 30 days",
     "SELECT COUNT(*) FROM matches WHERE match_status = 'Completed' "
     "AND match_date >= CURRENT_DATE - 30"),
    ("Q4  venues with capacity > 50,000",
     "SELECT COUNT(*) FROM venues WHERE capacity > 50000"),
    ("Q8  series starting in 2024",
     "SELECT COUNT(*) FROM series WHERE EXTRACT(YEAR FROM start_date) = 2024"),
    ("Q9  all-rounders >1000 runs and >50 wkts",
     "SELECT COUNT(*) FROM player_format_stats s JOIN players p USING (player_id) "
     "WHERE p.playing_role = 'All-rounder' AND s.runs > 1000 AND s.wickets > 50"),
    ("Q13 consecutive pairs scoring 100+ together",
     "SELECT COUNT(*) FROM batting_innings a JOIN batting_innings b "
     "ON a.match_id = b.match_id AND a.innings_no = b.innings_no "
     "AND b.batting_position = a.batting_position + 1 WHERE a.runs + b.runs >= 100"),
    ("Q14 bowler-venue pairs, 3+ matches of 4+ overs",
     "SELECT COUNT(*) FROM (SELECT bw.player_id, m.venue_id FROM bowling_innings bw "
     "JOIN matches m USING (match_id) WHERE bw.balls_bowled >= 24 "
     "GROUP BY bw.player_id, m.venue_id HAVING COUNT(DISTINCT bw.match_id) >= 3) x"),
    ("Q15 close matches (<50 runs or <5 wkts)",
     "SELECT COUNT(*) FROM matches WHERE (victory_type = 'runs' AND victory_margin < 50) "
     "OR (victory_type = 'wickets' AND victory_margin < 5)"),
    ("Q16 player-years since 2020 with 5+ matches",
     "SELECT COUNT(*) FROM (SELECT b.player_id FROM batting_innings b JOIN matches m "
     "USING (match_id) WHERE m.match_date >= DATE '2020-01-01' "
     "GROUP BY b.player_id, EXTRACT(YEAR FROM m.match_date) "
     "HAVING COUNT(DISTINCT b.match_id) >= 5) x"),
    ("Q18 limited-overs bowlers, 10+ matches",
     "SELECT COUNT(*) FROM (SELECT bw.player_id FROM bowling_innings bw JOIN matches m "
     "USING (match_id) WHERE m.match_format IN ('ODI', 'T20I') GROUP BY bw.player_id "
     "HAVING COUNT(DISTINCT bw.match_id) >= 10 "
     "AND SUM(bw.balls_bowled) / COUNT(DISTINCT bw.match_id) >= 12) x"),
    ("Q20 players with 20+ career matches",
     "SELECT COUNT(*) FROM (SELECT player_id FROM player_format_stats GROUP BY player_id "
     "HAVING SUM(matches) >= 20) x"),
    ("Q22 team pairs, 5+ meetings in last 3 years",
     "SELECT COUNT(*) FROM (SELECT LEAST(team1_id, team2_id), GREATEST(team1_id, team2_id) "
     "FROM matches WHERE match_status = 'Completed' "
     "AND match_date >= CURRENT_DATE - INTERVAL '3 years' "
     "GROUP BY 1, 2 HAVING COUNT(*) >= 5) x"),
    ("Q24 batting pairs with 5+ partnerships",
     "SELECT COUNT(*) FROM (SELECT a.player_id, b.player_id FROM batting_innings a "
     "JOIN batting_innings b ON a.match_id = b.match_id AND a.innings_no = b.innings_no "
     "AND b.batting_position = a.batting_position + 1 GROUP BY 1, 2 "
     "HAVING COUNT(*) >= 5) x"),
    ("Q25 players with 6+ quarters of 3+ matches",
     "SELECT COUNT(*) FROM (SELECT player_id FROM (SELECT b.player_id, "
     "DATE_TRUNC('quarter', m.match_date) q FROM batting_innings b JOIN matches m "
     "USING (match_id) GROUP BY 1, 2 HAVING COUNT(DISTINCT b.match_id) >= 3) pq "
     "GROUP BY player_id HAVING COUNT(*) >= 6) x"),
]


class SeedLoader:
    """Writes generated rows to the database in one transaction."""

    def __init__(self) -> None:
        self.engine = get_engine()

    def existing_matches(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM matches")).scalar_one()

    def load(self, rows: Rows, reset: bool) -> dict[str, int]:
        """Insert all rows; on any error, everything is rolled back."""
        meta = MetaData()
        meta.reflect(bind=self.engine, only=INSERT_ORDER + ["ingestion_log"])
        counts: dict[str, int] = {}
        started = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            if reset:
                conn.execute(text(
                    "TRUNCATE " + ", ".join(INSERT_ORDER + ["ingestion_log"])
                    + " RESTART IDENTITY CASCADE"))
            for name in INSERT_ORDER:
                data = getattr(rows, name)
                # SQLAlchemy batches executemany INSERTs into multi-row VALUES
                # ("insertmanyvalues"), so 10k rows take a handful of round trips.
                conn.execute(insert(meta.tables[name]), data)
                counts[name] = len(data)
                log.info("Inserted %6d rows into %s", len(data), name)
            # Explicit ids were supplied, so move each identity sequence past them;
            # otherwise the next INSERT from the app would collide with id 1.
            for table, pk in EXPLICIT_ID_TABLES.items():
                conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), "
                    f"(SELECT MAX({pk}) FROM {table}))"))
            conn.execute(insert(meta.tables["ingestion_log"]), dict(
                source="seed", endpoint="scripts/seed_data.py",
                records=sum(counts.values()), status="success",
                message=f"Deterministic seed (random seed {SEED})",
                started_at=started, finished_at=datetime.now(timezone.utc)))
        return counts

    def verify(self) -> bool:
        """Run threshold checks; return True if every check finds rows."""
        ok = True
        with self.engine.connect() as conn:
            for label, sql in CHECKS:
                n = conn.execute(text(sql)).scalar_one()
                ok &= n > 0
                print(f"  {'PASS' if n > 0 else 'FAIL'}  {label:<46} {n:>6}")
        return ok


# --------------------------------------------------------------------------
#  Helpers + CLI
# --------------------------------------------------------------------------
def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    return date(d.year + m // 12, m % 12 + 1, 1)


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 = success)."""
    parser = argparse.ArgumentParser(description="Load deterministic seed data.")
    parser.add_argument("--reset", action="store_true",
                        help="TRUNCATE all project tables first (DELETES ALL DATA)")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today(),
                        help="pretend today is YYYY-MM-DD (for reproducible tests)")
    args = parser.parse_args(argv)

    try:
        print(f"Connected: {check_connection().split(',')[0]}")
        loader = SeedLoader()
        existing = loader.existing_matches()
        if existing and not args.reset:
            print(f"The database already has {existing} matches. "
                  "Re-run with --reset to wipe and reseed.")
            return 1
        if args.reset and not args.yes:
            answer = input("This deletes ALL project data. Type 'yes' to continue: ")
            if answer.strip().lower() != "yes":
                print("Cancelled.")
                return 1

        print(f"Generating seed data (today = {args.today}) ...")
        rows = SeedGenerator(args.today).generate()
        counts = loader.load(rows, reset=args.reset)
        print("\nRows loaded:")
        for table, n in counts.items():
            print(f"  {table:<22} {n:>7}")
        print("\nThreshold checks (does each SQL question have data?):")
        all_ok = loader.verify()
        print("\nSeed complete." if all_ok else "\nSeed loaded, but some checks FAILED.")
        return 0 if all_ok else 3

    except (AppError, ConfigError) as exc:
        detail = getattr(exc, "detail", None)
        log.error("%s | %s", exc, detail or "")
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
