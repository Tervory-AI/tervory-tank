"""L1: tenant vocabulary, literal migration and complete main-output equivalence."""

from __future__ import annotations
import asyncio
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4
import asyncpg
import pytest
from rig_fixture_loader import load_catalogue

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/rig"))
from rigbox.service import RecordingHandoff, Service
from rigbox.store import MemoryStore
from rigbox.vocabulary import validate
from rigbox.rank import search as plain_search
from test_rig_postgres import (
    _admin_url,
    _create_database,
    _database_url,
    _drop_database,
)

BAN = re.compile(
    r"\b(pistols?|holsters?|calibers?|ammo|ammunition|cartridges?|magazines?|optics?|sights?|barrels?|suppressors?|compensators?|lasers?|slings?|rounds?|archon|glocks?|sigs?|trijicon|rmr|acp|9mm|9x19)\b",
    re.I,
)


def vocabulary():
    return json.loads(
        (ROOT / "tests/fixtures/rig_catalogues/aurora/publish.json").read_text()
    )["shop"]["vocabulary"]


def migration():
    schema = (ROOT / "agents/rig/schema.sql").read_text()
    match = re.search(
        r"UPDATE agent_rig\.retailers SET shop = shop \|\| '((?:''|[^'])*)'::jsonb\s+WHERE shop->>'search' = 'true' AND NOT \(shop \? 'vocabulary'\);",
        schema,
    )
    assert match
    return match.group(0), json.loads(match.group(1).replace("''", "'"))["vocabulary"]


def test_literal_vocabulary_matches_fixture_and_runtime_is_neutral():
    assert migration()[1] == vocabulary()
    assert validate(vocabulary())
    assert not (ROOT / "agents/rig/rigbox/cn.py").exists()
    assert not BAN.search((ROOT / "agents/rig/rigbox/guided_search.py").read_text())


@pytest.mark.asyncio
async def test_vocabulary_migration_fills_only_missing_search_records_and_is_idempotent():
    admin, name = _admin_url(), "rig_l1_placeholder_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        conn = await asyncpg.connect(_database_url(admin, name))
        try:
            await conn.execute(
                "CREATE SCHEMA agent_rig; CREATE TABLE agent_rig.retailers (tenant_id uuid PRIMARY KEY, shop jsonb NOT NULL);"
            )
            before = [
                {"search": True},
                {"search": True, "vocabulary": {"placeholder": "existing"}},
                {"search": False},
                {},
            ]
            tenants = [uuid4() for _ in before]
            for tenant, shop in zip(tenants, before):
                await conn.execute(
                    "INSERT INTO agent_rig.retailers VALUES ($1,$2::jsonb)",
                    tenant,
                    json.dumps(shop),
                )
            sql, expected = migration()
            await conn.execute(sql)
            once = [
                json.loads(
                    await conn.fetchval(
                        "SELECT shop FROM agent_rig.retailers WHERE tenant_id=$1",
                        tenant,
                    )
                )
                for tenant in tenants
            ]
            assert once == [{**before[0], "vocabulary": expected}, *before[1:]]
            await conn.execute(sql)
            twice = [
                json.loads(
                    await conn.fetchval(
                        "SELECT shop FROM agent_rig.retailers WHERE tenant_id=$1",
                        tenant,
                    )
                )
                for tenant in tenants
            ]
            assert once == twice
        finally:
            await conn.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_second_store_owns_categories_parts_and_sentences_without_fallback():
    service = Service(MemoryStore(), handoff=RecordingHandoff())
    await load_catalogue(service, ROOT / "tests/fixtures/rig_catalogues/second")
    tenant = "22222222-2222-4222-8222-222222222222"
    lamps = await service.search(tenant, "lamps", 24)
    shades = await service.search(tenant, "shades", 24)
    assert lamps["focus_id"] == "SECOND-LAMP-01"
    assert shades["ids"] == ["SECOND-SHADE-01"]
    parts = await service.search(tenant, "parts", 24)
    assert parts["ids"] == ["SECOND-SHADE-01"]
    related = await service.search(tenant, "shade to go with the lamp", 3)
    assert related["ids"][0] == "SECOND-SHADE-01"
    assert {row["category"] for row in shades["results"]} == {"shade"}
    packed = await service.search(tenant, "2 pack lamps", 24)
    assert packed["message"] == "We list lamps separately."
    assert not BAN.search(json.dumps([lamps, shades, packed]))
    first, second = await asyncio.gather(
        service.search(tenant, "lamps", 24), service.search(tenant, "shades", 24)
    )
    assert first == lamps and second == shades
    service.store.retailers[tenant]["shop"].pop("vocabulary")
    expected = plain_search(
        {
            "q": "lamps",
            "limit": 24,
            "products": await service._shopper_products(tenant),
            "fits": await service._approved_fits(tenant),
            "filters": {},
            "shop": await service._shop(tenant),
        }
    )
    assert await service.search(tenant, "lamps", 24) == expected


@pytest.mark.parametrize("bad", ["shape", "pattern", "limit", "template"])
@pytest.mark.asyncio
async def test_invalid_vocabulary_is_ignored_whole_and_logs_only_reason(caplog, bad):
    value = copy.deepcopy(vocabulary())
    marker = "placeholder-private-vocabulary"
    if bad == "shape":
        value["part_categories"] = marker
    elif bad == "pattern":
        value["size_patterns"]["size"] = "[" + marker
    elif bad == "limit":
        value["model_words"]["placeholder"] = marker * 2048
    else:
        value["sentences"]["pack_note"] = "{placeholder-private-vocabulary.__class__}"
    assert validate(value) == {}
    assert marker not in caplog.text
    assert "Guided search vocabulary ignored: " + bad in caplog.text
    store = MemoryStore()
    tenant = "11111111-1111-4111-8111-111111111111"
    await store.put_retailer(tenant, "placeholder", None, None)
    store.retailers[tenant]["shop"] = {"search": True, "vocabulary": value}
    assert await Service(store)._shop(tenant) == {"search": True}


def test_complete_search_detail_and_reservation_golden(tmp_path):
    output = tmp_path / "placeholder-golden.json"
    env = {
        **os.environ,
        "RIG_L1_GOLDEN_OUTPUT": str(output),
        "PYTHONPATH": os.pathsep.join(
            [
                str(ROOT / "tests"),
                str(ROOT / "agents/rig"),
                str(ROOT / "agents/_chassis"),
                os.environ.get("PYTHONPATH", ""),
            ]
        ),
    }
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_rig_cn_archon.py",
        "tests/test_rig_archon_search_memory.py",
        "-p",
        "rig_l1.golden_plugin",
        "-q",
        "--disable-socket",
        "--allow-unix-socket",
        "--allow-hosts=127.0.0.1,localhost,::1",
    ]
    result = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_bytes() == (ROOT / "tests/rig_l1/golden.json").read_bytes()
