"""Pool status for this box, and a load of one source.

The routes are scoped to TANK_REGION. A source from the other region is
refused. Key values are never written into a response.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agents.zenas.pool.bulk import load_wave
from agents.zenas.pool.catalogue import CATALOGUE, sources_for_region
from agents.zenas.pool.model import SourceSpec
from agents.zenas.pool.region import RegionError, assert_source_region
from agents.zenas.pool.status import pool_status
from agents.zenas.pool.store import Store, key_is_set


def _blank_row(source: SourceSpec) -> dict:
    return {
        "source_id": source.source_id,
        "name": source.name,
        "region": source.region,
        "jurisdiction": source.jurisdiction,
        "licence": source.licence,
        "terms_url": source.terms_url,
        "bulk_use": source.bulk_use,
        "enabled": source.enabled,
        "key_name": source.key_name,
        "key_required": source.key_required,
        "key_set": key_is_set(source.key_name),
        "documents": 0,
        "versions": 0,
        "last_update": None,
        "last_load": None,
        "last_status": "never",
        "detail": "",
        "errors": [],
        "link_only": False,
    }


async def status_for_box(store: Store, region: str) -> dict:
    """Every catalogue source for this region, with counts from the store."""
    report = await pool_status(store, region=region)
    by_id = {row["source_id"]: row for row in report["sources"]}
    sources = []
    for source in sources_for_region(region):
        sources.append(by_id.get(source.source_id) or _blank_row(source))
    return {"region": region, "sources": sources}


def _find(source_id: str) -> SourceSpec | None:
    for source in CATALOGUE:
        if source.source_id == source_id:
            return source
    return None


def create_app(
    store: Store,
    *,
    region: str,
    http_get=None,
    snapshots: dict[str, list[bytes]] | None = None,
    live: bool | None = None,
) -> FastAPI:
    """HTTP surface for the feeds switchboard. `region` is this box."""
    app = FastAPI()
    use_live = live if live is not None else snapshots is None

    @app.get("/pool/status")
    async def get_status() -> dict:
        return await status_for_box(store, region)

    @app.post("/pool/sources/{source_id}/load")
    async def load_one(source_id: str) -> dict:
        source = _find(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="unknown source")
        try:
            assert_source_region(source, region)
        except RegionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await load_wave(
            store,
            region=region,
            only=[source],
            live=use_live,
            http_get=http_get,
            snapshots=snapshots,
        )
        report = await status_for_box(store, region)
        row = next(item for item in report["sources"] if item["source_id"] == source_id)
        return {"ok": True, "region": region, "source": row}

    return app
