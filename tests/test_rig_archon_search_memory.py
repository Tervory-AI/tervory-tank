"""Build Spec: every finished Archon shopper search is kept on fixtures.

Part-by-part reuse at $0 for non-shop catalogues is covered by test_rig_recall.py.
Archon uses shop_search (pure code on the stand-in catalogue) and still persists
each finished search so past shopper queries are not lost.
"""

from __future__ import annotations

from rig_fixture_loader import load_catalogue

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.service import RecordingHandoff, Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

ARCHON = ROOT / "tests" / "fixtures" / "rig_catalogues" / "aurora"
TENANT = "44444444-4444-4444-8444-444444444444"


async def _archon() -> Service:
    service = Service(MemoryStore(), handoff=RecordingHandoff())
    report = await load_catalogue(service, ARCHON)
    assert report["products"]["added"] == 15
    return service


@pytest.mark.asyncio
async def test_archon_shop_search_keeps_every_finished_search() -> None:
    service = await _archon()
    first = await service.search(TENANT, "Archon Type B, red dot", 24)
    assert first["honest"] == "exact"
    assert first["focus_id"] == "ARCHON-TYPE-B"
    version = await service._catalogue_version(TENANT)
    saved = await service.store.searches_for(TENANT, version, 90)
    assert len(saved) == 1
    assert saved[0]["query"] == "Archon Type B, red dot"
    assert "ARCHON-TYPE-B" in saved[0]["ids"]
    again = await service.search(TENANT, "Archon Type B, red dot", 24)
    assert again["focus_id"] == first["focus_id"]
    saved2 = await service.store.searches_for(TENANT, version, 90)
    assert len(saved2) == 2


@pytest.mark.asyncio
async def test_archon_out_of_catalogue_is_kept_as_empty() -> None:
    service = await _archon()
    body = await service.search(TENANT, "Glock 19 compensator", 12)
    assert body["results"] == []
    assert body["honest"] == "not_stocked"
    version = await service._catalogue_version(TENANT)
    saved = await service.store.searches_for(TENANT, version, 90)
    assert len(saved) == 1
    assert saved[0]["ids"] == []
