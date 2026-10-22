"""Pure validation functions for user input (CRUD forms).

Each validator returns a list of human-readable error messages; an empty list
means the input is valid. Validation happens here first (friendly messages
per field) and again in the database (CHECK constraints) as a safety net.
"""
from __future__ import annotations

from datetime import date

from models.entities import (BATTING_STYLES, MATCH_FORMATS, MATCH_STATUSES,
                             PLAYING_ROLES, TOSS_DECISIONS, VICTORY_TYPES, Match, Player)

MAX_NAME_LENGTH = 120


def validate_player(player: Player) -> list[str]:
    """Validate a Player before INSERT/UPDATE."""
    errors: list[str] = []
    name = (player.full_name or "").strip()
    if not name:
        errors.append("Full name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Full name must be at most {MAX_NAME_LENGTH} characters.")
    elif any(ch.isdigit() for ch in name):
        errors.append("Full name should not contain digits.")
    if not player.team_id:
        errors.append("Team is required.")
    if player.playing_role not in PLAYING_ROLES:
        errors.append(f"Playing role must be one of: {', '.join(PLAYING_ROLES)}.")
    if player.batting_style and player.batting_style not in BATTING_STYLES:
        errors.append(f"Batting style must be one of: {', '.join(BATTING_STYLES)}.")
    if player.date_of_birth:
        if player.date_of_birth >= date.today():
            errors.append("Date of birth must be in the past.")
        elif player.date_of_birth.year < 1900:
            errors.append("Date of birth looks wrong (before 1900).")
    return errors


def validate_match(match: Match) -> list[str]:
    """Validate a Match, including cross-field cricket rules."""
    errors: list[str] = []
    if not (match.match_description or "").strip():
        errors.append("Match description is required.")
    if match.match_format not in MATCH_FORMATS:
        errors.append(f"Format must be one of: {', '.join(MATCH_FORMATS)}.")
    if match.match_status not in MATCH_STATUSES:
        errors.append(f"Status must be one of: {', '.join(MATCH_STATUSES)}.")
    if not match.venue_id:
        errors.append("Venue is required.")
    if not match.team1_id or not match.team2_id:
        errors.append("Both teams are required.")
    elif match.team1_id == match.team2_id:
        errors.append("A team cannot play against itself.")
    teams = {match.team1_id, match.team2_id}

    # Toss: both fields or neither.
    if (match.toss_winner_id is None) != (match.toss_decision is None):
        errors.append("Enter both the toss winner and the toss decision, or neither.")
    if match.toss_winner_id is not None and match.toss_winner_id not in teams:
        errors.append("The toss winner must be one of the two teams.")
    if match.toss_decision is not None and match.toss_decision not in TOSS_DECISIONS:
        errors.append("Toss decision must be 'bat' or 'bowl'.")

    # Result rules.
    if match.match_status == "Completed":
        if match.victory_type not in VICTORY_TYPES:
            errors.append("A completed match needs a result type.")
        elif match.victory_type in ("runs", "wickets", "innings"):
            if match.winner_id not in teams:
                errors.append("Choose the winning team.")
            if not match.victory_margin or match.victory_margin <= 0:
                errors.append("Victory margin must be a positive number.")
            elif match.victory_type == "wickets" and match.victory_margin > 10:
                errors.append("A win by wickets cannot exceed 10 wickets.")
        elif match.winner_id is not None or match.victory_margin is not None:
            errors.append(f"A '{match.victory_type}' result has no winner or margin.")
    else:
        if match.winner_id is not None or match.victory_type not in (None, "no result"):
            errors.append("Only completed matches can have a winner or result.")
        if match.match_status == "Upcoming" and match.match_date and \
                match.match_date < date.today():
            errors.append("An upcoming match cannot be dated in the past.")
    return errors
