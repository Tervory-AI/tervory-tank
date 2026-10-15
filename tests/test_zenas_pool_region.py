"""US and ZA pools stay on their own boxes. The loader refuses the other region."""

import asyncio
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.zenas.pool.bulk import load_wave
from agents.zenas.pool.catalogue import CATALOGUE, sources_for_region
from agents.zenas.pool.model import SourceSpec
from agents.zenas.pool.nightly import packaged_snapshots
from agents.zenas.pool.region import RegionError
from agents.zenas.pool.status import pool_status
from agents.zenas.pool.store import MemoryStore

ON = date(2026, 10, 15)


def _za_source() -> SourceSpec:
    return SourceSpec(
        source_id="za-fixture",
        name="South African fixture",
        region="za",
        jurisdiction="za",
        licence="Public record.",
        terms="Publisher terms are recorded as information.",
        terms_url="https://www.gov.za/",
        bulk_use="allowed",
        store_full_text=True,
        canonical_url="https://www.gov.za/",
        notes="",
        adapter="refused",
        enabled=True,
    )


def _us_source():
    return next(item for item in CATALOGUE if item.source_id == "frcp")


def test_us_loader_refuses_a_za_source_before_any_fetch():
    asyncio.run(_us_refuses())


async def _us_refuses():
    seen: list[str] = []

    async def get(url, headers):
        seen.append(url)
        return b"ZA-TEXT-MUST-NOT-BE-READ"

    store = MemoryStore()
    with pytest.raises(RegionError):
        await load_wave(
            store,
            region="us-east",
            only=[_za_source()],
            live=True,
            http_get=get,
            on=ON,
            snapshots={"za-fixture": [b"ZA-TEXT-MUST-NOT-BE-STORED"]},
        )
    assert seen == []
    assert await store.get_source("za-fixture") is None
    assert await store.version_count() == 0
    assert "ZA-TEXT" not in await store.all_text()


def test_za_loader_refuses_a_us_source():
    asyncio.run(_za_refuses())


async def _za_refuses():
    seen: list[str] = []

    async def get(url, headers):
        seen.append(url)
        return b"US-TEXT"

    store = MemoryStore()
    with pytest.raises(RegionError):
        await load_wave(
            store,
            region="za",
            only=[_us_source()],
            live=True,
            http_get=get,
            on=ON,
            snapshots={"frcp": [b"US-TEXT-MUST-NOT-CROSS"]},
        )
    assert seen == []
    assert await store.get_source("frcp") is None
    assert "US-TEXT" not in await store.all_text()


def test_a_bound_store_does_not_read_or_write_the_other_region():
    asyncio.run(_bound())


async def _bound():
    store = MemoryStore(home_region="us-east")
    await store.record_source(_us_source())
    with pytest.raises(RegionError):
        await store.record_source(_za_source())
    with pytest.raises(RegionError):
        await store.find_by_citation("Fed. R. Civ. P. 1", jurisdiction="za", as_at=None)
    with pytest.raises(RegionError):
        await store.search_text("procedure", jurisdiction="za", as_at=None)
    assert await store.get_source("za-fixture") is None

    other = MemoryStore(home_region="za")
    assert await other.all_text() == ""
    assert await other.status_rows() == []


def test_status_for_one_region_omits_the_other():
    asyncio.run(_status())


async def _status():
    store = MemoryStore()
    await store.record_source(_us_source())
    await store.record_source(_za_source())
    us = await pool_status(store, region="us-east")
    za = await pool_status(store, region="za")
    assert {row["source_id"] for row in us["sources"]} == {"frcp"}
    assert {row["source_id"] for row in za["sources"]} == {"za-fixture"}
    assert us["region"] == "us-east"
    assert za["region"] == "za"


def test_snapshot_directories_do_not_overlap():
    us = set(packaged_snapshots("us-east"))
    za = set(packaged_snapshots("za"))
    assert "govinfo-uscode" in us
    assert us.isdisjoint(za)
    assert [source.region for source in sources_for_region("us-east")]
    assert all(source.region == "us-east" for source in sources_for_region("us-east"))
    assert all(source.region == "za" for source in sources_for_region("za"))
