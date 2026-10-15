"""Feeds switchboard: status for this box, and a load of one source."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.zenas.pool.api import create_app
from agents.zenas.pool.catalogue import sources_for_region
from agents.zenas.pool.nightly import packaged_snapshots
from agents.zenas.pool.store import MemoryStore

MARKER = "marker-" + ("b" * 16)


def _client(region: str, *, snapshots=None, http_get=None, live=None) -> TestClient:
    app = create_app(
        MemoryStore(),
        region=region,
        snapshots=snapshots,
        http_get=http_get,
        live=live,
    )
    return TestClient(app)


def test_status_lists_this_region_and_never_the_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LAWS_AFRICA_API_TOKEN", MARKER)
    client = _client("za")
    response = client.get("/pool/status")
    assert response.status_code == 200
    body = response.json()
    assert body["region"] == "za"
    ids = {row["source_id"] for row in body["sources"]}
    assert ids == {source.source_id for source in sources_for_region("za")}
    assert "courtlistener" not in ids
    encoded = json.dumps(body)
    assert MARKER not in encoded
    assert "Bearer" not in encoded
    popia = next(row for row in body["sources"] if row["source_id"] == "popia")
    assert popia["key_name"] == "LAWS_AFRICA_API_TOKEN"
    assert popia["key_required"] is True
    assert popia["key_set"] is True
    assert popia["documents"] == 0
    assert popia["last_load"] is None
    assert popia["errors"] == []
    saflii = next(row for row in body["sources"] if row["source_id"] == "saflii")
    assert saflii["key_name"] == ""
    assert saflii["key_set"] is True


def test_status_key_set_is_false_until_the_variable_is_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LAWS_AFRICA_API_TOKEN", raising=False)
    client = _client("za")
    body = client.get("/pool/status").json()
    popia = next(row for row in body["sources"] if row["source_id"] == "popia")
    assert popia["key_set"] is False
    assert MARKER not in json.dumps(body)


def test_load_one_za_source_from_a_snapshot():
    client = _client("za", snapshots=packaged_snapshots("za"), live=False)
    response = client.post("/pool/sources/companies-act/load")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["region"] == "za"
    assert body["source"]["source_id"] == "companies-act"
    assert body["source"]["documents"] == 1
    assert body["source"]["last_status"] == "ok"
    assert body["source"]["errors"] == []
    assert body["source"]["key_name"] == "LAWS_AFRICA_API_TOKEN"
    status = client.get("/pool/status").json()
    companies = next(row for row in status["sources"] if row["source_id"] == "companies-act")
    assert companies["documents"] == 1
    popia = next(row for row in status["sources"] if row["source_id"] == "popia")
    assert popia["documents"] == 0


def test_load_refuses_a_source_from_the_other_region():
    seen: list[str] = []

    async def get(url, headers):
        seen.append(url)
        return b"US-TEXT"

    client = _client("za", http_get=get, live=True)
    response = client.post("/pool/sources/courtlistener/load")
    assert response.status_code == 409
    assert "courtlistener" in response.json()["detail"]
    assert seen == []
    status = client.get("/pool/status").json()
    assert all(row["region"] == "za" for row in status["sources"])
    assert "courtlistener" not in {row["source_id"] for row in status["sources"]}


def test_us_box_refuses_a_za_source():
    seen: list[str] = []

    async def get(url, headers):
        seen.append(url)
        return b"ZA-TEXT"

    client = _client("us-east", http_get=get, live=True)
    response = client.post("/pool/sources/saflii/load")
    assert response.status_code == 409
    assert seen == []
    listed = client.get("/pool/status").json()
    assert listed["region"] == "us-east"
    assert "saflii" not in {row["source_id"] for row in listed["sources"]}
    assert "courtlistener" in {row["source_id"] for row in listed["sources"]}


def test_missing_key_does_not_call_the_network(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LAWS_AFRICA_API_TOKEN", raising=False)
    seen: list[str] = []

    async def get(url, headers):
        seen.append(url)
        return b"<xml></xml>"

    client = _client("za", http_get=get, live=True)
    response = client.post("/pool/sources/lra/load")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["source"]["last_status"] == "not_configured"
    assert body["source"]["key_set"] is False
    assert body["source"]["documents"] == 0
    assert seen == []
    assert MARKER not in response.text


def test_unknown_source_is_not_found():
    client = _client("za")
    response = client.post("/pool/sources/not-a-source/load")
    assert response.status_code == 404
