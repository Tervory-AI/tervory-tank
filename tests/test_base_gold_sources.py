"""Synthetic evidence tests. No real list download or network call occurs."""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/_chassis"))
sys.path.insert(0, str(ROOT / "agents/base"))

from base_gold.gold_sources import candidates, read_candidates  # noqa: E402

TODAY = date(2026, 10, 20)


def evidence():
    return json.loads((ROOT / "tests/fixtures/base-gold-synthetic.jsonl").read_text())


def produce(rows, **kwargs):
    return candidates(rows, region="us-east", today=TODAY, **kwargs)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_four_public_candidates_and_deduplication():
    rows = produce([evidence(), evidence()])
    assert [row["skill_id"] for row in rows] == [
        "base.find_site", "base.verify", "base.normalize", "base.resolve",
    ]
    for row in rows:
        assert set(row) == {"skill_id", "input", "expected", "label_source", "region", "public"} | (
            {"needs_network"} if row["skill_id"] == "base.find_site" else set()
        )
        assert row["public"] is True and row["region"] == "us-east"
        assert "ATF Federal Firearms Licensees" in row["label_source"]
    assert len(produce([evidence()], limit=1)) == 1
    assert produce([evidence()], limit=0) == []


@pytest.mark.parametrize(("section", "key", "value"), [
    (None, "public", False),
    (None, "public", "true"),
    (None, "tenant_id", "00000000-0000-0000-0000-000000000099"),
    (None, "record_kind", "person"),
    (None, "region", "za"),
    (None, "source_id", "unreviewed-source"),
    ("official", "active", False),
    ("official", "valid_until", "2026-10-01"),
    ("official", "observed_on", "2026-01-01"),
    ("official", "source_url", "https://atf.gov.evil.example/firearms/listing-federal-firearms-licensees"),
    ("official", "source_url", "https://atf.gov/irrelevant"),
    ("site", "source_url", "https://directory.example/example-business"),
    ("site", "observed_on", "2026-08-01"),
    ("site", "observed_on", "2026-12-01"),
    ("site", "blocked", True),
    ("site", "status", 403),
])
def test_rejects_untrusted_stale_private_or_disagreeing_evidence(section, key, value):
    row = evidence()
    target = row[section] if section else row
    target[key] = value
    assert produce([row]) == []


def test_missing_or_malformed_data_never_becomes_gold():
    for section in ("official", "site"):
        row = evidence()
        row[section] = None
        assert produce([row]) == []
    for field in ("name", "address", "city", "state", "zip"):
        row = evidence()
        row["site"][field] = row["official"][field] = ""
        assert produce([row]) == []
    assert candidates([evidence()], region="za", today=TODAY) == []
    with pytest.raises(ValueError):
        candidates([evidence()], region="../us-east")


def test_projection_removes_unrelated_private_fields():
    row = evidence()
    row["site"]["people"] = [{"name": "DO_NOT_EXPORT"}]
    row["official"]["email"] = "DO_NOT_EXPORT"
    row["client_notes"] = "DO_NOT_EXPORT"
    assert "DO_NOT_EXPORT" not in json.dumps(produce([row]))


def test_state_registry_names_its_own_source():
    row = evidence()
    row["source_id"] = "ca-business-registry"
    row["official"]["source_url"] = "https://bizfileonline.sos.ca.gov/search/business"
    assert all("California Secretary of State" in item["label_source"] for item in produce([row]))
    assert len(produce([row])) == 4


def test_labels_match_existing_offline_skill_contracts():
    for candidate in produce([evidence()]):
        if candidate.get("needs_network"):
            continue
        skill = candidate["skill_id"]
        module = load(f"gold_test_{skill}", ROOT / f"tank/skills/{skill}/1.0.0/run.py")
        result = asyncio.run(module.run(copy.deepcopy(candidate["input"]), None))
        for key, expected in candidate["expected"].items():
            assert result[key] == expected


def test_find_site_is_discovery_not_an_input_echo():
    candidate = produce([evidence()])[0]
    assert candidate["needs_network"] is True
    assert set(candidate["input"]) == {"name", "address", "city", "state", "zip"}
    assert candidate["expected"] == {"website": {"value": "https://example.com"}}
    assert "example.com" not in json.dumps(candidate["input"])


def test_atf_individual_and_home_premises_stay_public():
    row = evidence()
    row["entity_type"] = "sole_proprietor"
    row["official"]["name"] = "Published Licensee"
    row["official"]["address"] = row["site"]["address"] = "10 Home Lane"
    assert len(produce([row])) == 4
    assert all(candidate["public"] for candidate in produce([row]))
    row["source_id"] = "ca-business-registry"
    row["official"]["source_url"] = "https://bizfileonline.sos.ca.gov/search/business"
    assert produce([row]) == []


def test_phone_or_address_independently_suffices():
    row = evidence()
    row["site"]["phone"] = "6175550199"
    rows = produce([row])
    assert {item["skill_id"] for item in rows} == {"base.find_site", "base.normalize", "base.resolve"}
    assert "6175550199" not in json.dumps(rows)
    row["site"]["address"] = "Another address"
    assert produce([row]) == []


def test_limit_is_global_and_bounded():
    rows = []
    for number in range(100):
        row = evidence()
        row["official"]["id"] = str(number)
        row["official"]["name"] = row["site"]["name"] = f"Business {number}"
        rows.append(row)
    assert len(produce(rows, limit=999)) == 200


def test_local_snapshot_and_region(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert read_candidates(limit=200, region="us-east") == []
    directory = tmp_path / "gold/us-east"
    directory.mkdir(parents=True)
    row = evidence()
    row["official"]["observed_on"] = row["site"]["observed_on"] = date.today().isoformat()
    row["official"]["valid_until"] = date.today().isoformat()
    (directory / "official-matches.jsonl").write_text("broken\n" + json.dumps(row) + "\n")
    assert len(read_candidates(limit=200, region="us-east")) == 4
    assert read_candidates(limit=200, region="za") == []


def test_http_requires_exact_room_key_before_read(monkeypatch):
    module = load("base_gold_http_app", ROOT / "agents/base/app.py")
    monkeypatch.setenv("TANK_KEY", "synthetic-room-key")
    reads = []

    def read(**kwargs):
        reads.append(kwargs)
        return produce([evidence()], limit=kwargs["limit"])

    monkeypatch.setattr(module, "read_candidates", read)
    monkeypatch.setenv("TANK_REGION", "us-east")

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://room") as client:
            for headers in ({}, {"X-Tank-Key": "wrong"}, {"Authorization": "Bearer synthetic-room-key"}):
                assert (await client.get("/gold/candidates", headers=headers)).status_code == 401
            assert not reads
            response = await client.get("/gold/candidates?limit=2", headers={"X-Tank-Key": "synthetic-room-key"})
            assert response.status_code == 200 and len(response.json()) == 2
            assert reads == [{"limit": 2, "region": "us-east"}]
            assert (await client.get("/gold/candidates?limit=201", headers={"X-Tank-Key": "synthetic-room-key"})).status_code == 422
            monkeypatch.delenv("TANK_KEY")
            assert (await client.get("/gold/candidates", headers={"X-Tank-Key": "synthetic-room-key"})).status_code == 401
    asyncio.run(run())
