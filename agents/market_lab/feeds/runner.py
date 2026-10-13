"""Run adapters and print status. Linked sources are recorded and not copied."""

from __future__ import annotations

from pathlib import Path

from feeds.adapters import ADAPTERS
from feeds.catalog import sources
from feeds.db import apply_schema, connect
from feeds.reader import FixtureReader
from feeds.store import Store, utc_now


def fixture_roots(explicit: str | None) -> list[Path]:
    roots: list[Path] = []
    if explicit:
        roots.append(Path(explicit))
    roots.append(Path(__file__).resolve().parent / "engines" / "ffl" / "fixtures")
    return roots


def run(
    db: str,
    *,
    engine: str = "ffl",
    source: str | None = None,
    backfill: bool = False,
    fixtures: str | None = None,
) -> list[dict[str, object]]:
    specs = sources(engine)
    if source is not None:
        specs = [item for item in specs if item.id == source]
        if not specs:
            known = ", ".join(item.id for item in sources(engine))
            raise SystemExit(f"unknown source {source}. Known: {known}")
    conn = connect(db)
    apply_schema(conn)
    store = Store(conn)
    reader = FixtureReader(fixture_roots(fixtures)) if fixtures else None
    for spec in specs:
        started = utc_now()
        store.upsert_source(spec)
        rows = 0
        error: str | None = None
        try:
            if not spec.enabled:
                error = "disabled"
            elif not spec.allow_bulk:
                rows = 0
            elif reader is None:
                raise RuntimeError(
                    "refusing to open the network. Pass --fixtures for a saved "
                    "backfill. URL builders are in feeds.live and are not called here."
                )
            else:
                adapter = ADAPTERS[spec.adapter]
                rows = adapter(spec, reader, store, backfill=backfill)
        except Exception as exc:
            rows = 0
            error = f"{type(exc).__name__}: {exc}"
        store.finish_run(spec.id, started, rows, error)
    report = store.status()
    conn.close()
    return [row for row in report if source is None or row["id"] == source]


def status(db: str, *, engine: str = "ffl") -> list[dict[str, object]]:
    conn = connect(db)
    apply_schema(conn)
    store = Store(conn)
    for spec in sources(engine):
        store.upsert_source(spec)
    conn.commit()
    report = store.status()
    conn.close()
    return report


def format_status(rows: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for row in rows:
        lines.append(
            f"{row['id']}\t{row['mode']}\tcadence={row['cadence']}\t"
            f"points={row['points']}\tevents={row['events']}\t"
            f"last_rows={row['last_rows']}\tlast={row['last_finished'] or ''}\t"
            f"error={row['last_error'] or ''}"
        )
        lines.append(f"  name: {row['name']}")
        lines.append(f"  url: {row['url']}")
        lines.append(f"  licence: {row['licence']}")
    return "\n".join(lines) + ("\n" if lines else "")
