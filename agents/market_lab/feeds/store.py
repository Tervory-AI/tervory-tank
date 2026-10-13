"""Append-only points and events. A re-run does not overwrite a number."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from feeds.models import SourceSpec


def canonical_number(value: object) -> str:
    if value is None or value == "":
        raise ValueError("empty number")
    number = Decimal(str(value))
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_source(self, source: SourceSpec) -> None:
        self.conn.execute(
            """
            INSERT INTO feed_sources (
                id, name, kind, url, licence, terms_checked_at, cadence, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                kind = excluded.kind,
                url = excluded.url,
                licence = excluded.licence,
                terms_checked_at = excluded.terms_checked_at,
                cadence = excluded.cadence,
                enabled = excluded.enabled
            """,
            (
                source.id,
                source.name,
                source.kind,
                source.url,
                source.licence,
                source.terms_checked_at,
                source.cadence,
                1 if source.enabled else 0,
            ),
        )

    def ensure_series(
        self,
        source_id: str,
        ref: str,
        title: str,
        unit: str,
        geo_level: str,
        geo: str,
        frequency: str,
    ) -> str:
        series_id = f"{source_id}:{ref}"
        self.conn.execute(
            """
            INSERT INTO series (
                id, source_id, ref, title, unit, geo_level, geo, frequency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (series_id, source_id, ref, title, unit, geo_level, geo, frequency),
        )
        return series_id

    def put_point(self, series_id: str, date: str, value: object, revision: str) -> bool:
        """Keep every vintage. Never update a stored number in place."""
        stored = canonical_number(value)
        candidate = revision
        while True:
            row = self.conn.execute(
                "SELECT value FROM points WHERE series_id = ? AND date = ? AND revision = ?",
                (series_id, date, candidate),
            ).fetchone()
            if row is None:
                self.conn.execute(
                    """
                    INSERT INTO points (series_id, date, value, fetched_at, revision)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (series_id, date, stored, utc_now(), candidate),
                )
                return True
            if canonical_number(row["value"]) == stored:
                return False
            if "#" in candidate:
                base, _, suffix = candidate.rpartition("#")
                candidate = f"{base}#{int(suffix) + 1}"
            else:
                candidate = f"{revision}#2"

    def put_event(
        self,
        source_id: str,
        kind: str,
        geo: str,
        date: str,
        title: str,
        body: str,
        url: str,
    ) -> bool:
        existing = self.conn.execute(
            """
            SELECT 1 FROM events
            WHERE source_id = ? AND kind = ? AND geo = ? AND date = ?
              AND title = ? AND body = ? AND url = ?
            """,
            (source_id, kind, geo, date, title, body, url),
        ).fetchone()
        if existing is not None:
            return False
        self.conn.execute(
            """
            INSERT INTO events (
                id, source_id, kind, geo, date, title, body, url, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), source_id, kind, geo, date, title, body, url, utc_now()),
        )
        return True

    def finish_run(self, source_id: str, started: str, rows: int, error: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO fetch_runs (id, source_id, started, finished, rows, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), source_id, started, utc_now(), rows, error),
        )
        self.conn.commit()

    def status(self) -> list[dict[str, Any]]:
        sources = self.conn.execute(
            "SELECT * FROM feed_sources ORDER BY id"
        ).fetchall()
        rows: list[dict[str, Any]] = []
        for source in sources:
            points = self.conn.execute(
                """
                SELECT COUNT(*) AS n FROM points p
                JOIN series s ON s.id = p.series_id
                WHERE s.source_id = ?
                """,
                (source["id"],),
            ).fetchone()["n"]
            events = self.conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE source_id = ?",
                (source["id"],),
            ).fetchone()["n"]
            last = self.conn.execute(
                """
                SELECT started, finished, rows, error FROM fetch_runs
                WHERE source_id = ?
                ORDER BY started DESC, rowid DESC
                LIMIT 1
                """,
                (source["id"],),
            ).fetchone()
            mode = "copy" if not str(source["licence"]).startswith("Linked only.") else "linked"
            rows.append(
                {
                    "id": source["id"],
                    "name": source["name"],
                    "kind": source["kind"],
                    "url": source["url"],
                    "licence": source["licence"],
                    "terms_checked_at": source["terms_checked_at"],
                    "cadence": source["cadence"],
                    "enabled": source["enabled"],
                    "mode": mode,
                    "points": points,
                    "events": events,
                    "last_started": None if last is None else last["started"],
                    "last_finished": None if last is None else last["finished"],
                    "last_rows": None if last is None else last["rows"],
                    "last_error": None if last is None else last["error"],
                }
            )
        return rows

