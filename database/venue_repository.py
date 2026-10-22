"""VenueRepository - SQL for the ``venues`` table."""
from __future__ import annotations

from sqlalchemy import Connection, text

from database.base_repository import BaseRepository


class VenueRepository(BaseRepository):
    """Read venues; upsert venues discovered through the API."""

    def list_all(self) -> list[dict]:
        return self.fetch_all(
            "SELECT venue_id, venue_name, city, country, capacity FROM venues "
            "ORDER BY country, venue_name")

    @staticmethod
    def find_by_cricbuzz_id(conn: Connection, cb_id: int) -> int | None:
        return conn.execute(text("SELECT venue_id FROM venues WHERE cricbuzz_venue_id = :cb"),
                            {"cb": cb_id}).scalar()

    @staticmethod
    def upsert_api(conn: Connection, cb_id: int | None, name: str, city: str,
                   country: str, capacity: int | None) -> int:
        """Insert or link a venue; existing (name, city) rows get the Cricbuzz id."""
        return conn.execute(text("""
            INSERT INTO venues (cricbuzz_venue_id, venue_name, city, country, capacity)
            VALUES (:cb, :name, :city, :country, :capacity)
            ON CONFLICT (venue_name, city) DO UPDATE
               SET cricbuzz_venue_id = COALESCE(venues.cricbuzz_venue_id,
                                                EXCLUDED.cricbuzz_venue_id),
                   capacity          = COALESCE(venues.capacity, EXCLUDED.capacity),
                   country           = CASE WHEN venues.country = 'Unknown'
                                            THEN EXCLUDED.country ELSE venues.country END
            RETURNING venue_id
        """), {"cb": cb_id, "name": name, "city": city or "Unknown",
               "country": country or "Unknown", "capacity": capacity}).scalar_one()
