import copy
import secrets
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.zenas import app as room
from agents.zenas.core.engine import retrieve_passages
from agents.zenas.gold_sources import candidates, case_candidate, statute_candidate


def case(region="us-east", holdout=False):
    return {
        "region": region, "jurisdiction": "za" if region == "za" else "us",
        "tenant_id": None, "source": "case", "material_type": "public_record",
        "source_id": "saflii" if region == "za" else "courtlistener",
        "pool_doc_id": "civil-case", "pool_version_id": "v1",
        "text": "The buyer accepted delivery under the supply agreement.",
        "fact_pattern": {"facts": "The buyer accepted delivery under the supply agreement."},
        "element_findings": [{"element_id": "delivery", "finding": "met"}],
        "outcome": "met", "holdout": holdout,
    }


def section(region="us-east"):
    return {
        "jurisdiction": "za" if region == "za" else "us",
        "source_id": "govza" if region == "za" else "govinfo-uscode",
        "kind": "statute", "text": "A civil agreement requires acceptance.",
        "citation": "Civil Act section 1", "document_id": "act", "version_id": "v1",
        "path": "1",
    }


@pytest.mark.parametrize("region", ["za", "us-east"])
def test_public_cases_and_heldout_labels(region):
    for held in (True, False):
        result = case_candidate(case(region, held), region)
        assert set(result) == {"skill_id", "input", "expected", "label_source", "region", "public"}
        assert result["region"] == region
        assert result["public"] is (not held)
        assert result["input"]["holdout"] is held
        assert result["label_source"].startswith("held_out:" if held else "converted:")
    assert case_candidate(case(region), "us-east" if region == "za" else "za") is None


def test_private_unknown_criminal_and_unverified_rows_are_excluded():
    for changes in (
        {"tenant_id": "private"}, {"source": "released"}, {"material_type": "client_work"},
        {"source_id": "unknown"}, {"docket_number": "1:20-cr-123"},
        {"text": "A completely different judgment."},
        {"fact_pattern": {"facts": "criminal prosecution"}},
    ):
        row = copy.deepcopy(case())
        row.update(changes)
        assert case_candidate(row, "us-east") is None


def test_statute_label_matches_retrieval_and_unknown_sources_stay_out():
    row = section()
    result = statute_candidate(row, "us-east")
    assert result["expected"]["passages"] == retrieve_passages(**result["input"])
    row["source_id"] = "client-upload"
    assert statute_candidate(row, "us-east") is None
    assert statute_candidate(section(), "za") is None


class Connection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def fetch(self, query, *args):
        if "worked_matters" in query:
            assert "w.tenant_id IS NULL" in query
            assert args[0:2] == ("us-east", "us")
            return [case()]
        assert args[0] == "us"
        return [section()]


class Pool:
    def acquire(self):
        return Connection()


@pytest.mark.asyncio
async def test_limit_and_mixed_sources():
    assert await candidates(Pool(), region="us-east", limit=0) == []
    assert len(await candidates(Pool(), region="us-east", limit=1)) == 1
    result = await candidates(Pool(), region="us-east", limit=200)
    assert {row["skill_id"] for row in result} == {"zenas.case_facts", "zenas.retrieve"}
    with pytest.raises(ValueError):
        await candidates(Pool(), region="eu")


@pytest.mark.asyncio
async def test_endpoint_requires_room_key_before_reading_and_fails_without_region(monkeypatch):
    key = secrets.token_urlsafe(24)
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(room.app.state, "pool", Pool(), raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url="http://test") as client:
        assert (await client.get("/gold/candidates")).status_code == 401
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": secrets.token_urlsafe(24)})).status_code == 401
        response = await client.get("/gold/candidates?limit=1", headers={"X-Tank-Key": key})
        assert response.status_code == 200 and len(response.json()) == 1
        assert (await client.get("/gold/candidates?limit=201", headers={"X-Tank-Key": key})).status_code == 422
        monkeypatch.delenv("TANK_REGION")
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 409
        monkeypatch.delenv("TANK_KEY")
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 401
