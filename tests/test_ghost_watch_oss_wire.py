"""Autumbra Watch OSS → match → ThreatPayload → Shields.propose (panel practice).

Fixtures only. No live HF. Stacked on #284 (ThreatPayload air-gap). Enforce OFF.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from agents.ghost import shields as sh
from agents.ghost.models import PLATFORM_TENANT
from agents.ghost.store import Store
from agents.ghost.threat_payload import ThreatAction, ThreatBurned, ThreatPayload
from agents.ghost.watch_oss import (
    AnomalyEvent,
    anomaly_to_match,
    fluentbit,
    handoff_propose,
    handoff_threat,
    opencti,
    propose_from_anomaly,
    status,
    steampipe,
    vector,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "watch_oss"
EDGE = [
    {"app": "coolify", "kind": "edge", "name": "cloudflare", "version": "current", "ecosystem": "generic"},
]


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fixtures_on_disk():
    for name in (
        "vector_anomalies.json",
        "fluentbit_anomalies.json",
        "steampipe_inventory.json",
        "opencti_indicators.json",
    ):
        assert (FIXTURES / name).is_file(), name


def test_vector_fixture_forward_and_propose_threat():
    events = _load("vector_anomalies.json")
    # forward_to_threat keeps open_match for all above-threshold (incl. propose-eligible).
    out = vector.forward_to_threat(events)
    assert len(out) == 1
    assert isinstance(out[0], ThreatPayload)
    # Propose path for the high-score waf signal.
    propose = handoff_propose(events[0])
    assert propose.action is ThreatAction.propose_shield
    assert propose.kind == "waf_managed"
    assert propose.site in {"coolify.tervory.com", "coolify"}
    # Noise / below threshold burns.
    with pytest.raises(ThreatBurned):
        handoff_propose(events[1])


def test_fluentbit_fixture_propose_multipart():
    events = _load("fluentbit_anomalies.json")
    out = fluentbit.forward_to_threat(events)
    assert len(out) == 1
    propose = handoff_propose(events[0])
    assert propose.kind == "block_multipart_post"
    assert propose.action is ThreatAction.propose_shield


def test_steampipe_fixture_inventory_and_propose():
    body = _load("steampipe_inventory.json")
    comps = steampipe.rows_to_components(body["rows"], app="coolify")
    assert comps[0].name == "nginx"
    propose = handoff_propose(body["anomaly"])
    assert propose.action is ThreatAction.propose_shield
    assert propose.kind == "waf_managed"


def test_opencti_fixture_handoff_open_match_then_propose_via_signal():
    body = _load("opencti_indicators.json")
    client = opencti.OpenCTIReadClient("http://127.0.0.1:8080")
    events = client.indicators_to_anomalies(body["indicators"], site=body["site"])
    assert len(events) == 1
    # Default opencti signal is not a shield kind — open_match only.
    payload = handoff_threat(events[0])
    assert payload.action is ThreatAction.open_match
    # Operator maps to waf for panel propose (fixture wire).
    propose_event = AnomalyEvent(
        source="opencti",
        site=body["site"],
        signal="waf",
        score=0.92,
        cve_ids=["CVE-2026-109618"],
        reason="opencti kev mapped to waf",
        confidence=0.92,
    )
    propose = handoff_propose(propose_event)
    assert propose.action is ThreatAction.propose_shield


def test_anomaly_to_match_burns_unknown_site_and_low_score():
    with pytest.raises(ThreatBurned):
        anomaly_to_match(
            {"source": "vector", "site": "evil.example", "signal": "waf", "score": 0.99, "reason": "x"}
        )
    with pytest.raises(ThreatBurned):
        anomaly_to_match(
            {
                "source": "vector",
                "site": "coolify.tervory.com",
                "signal": "waf",
                "score": 0.85,
                "reason": "medium only",
            }
        )


@pytest.mark.asyncio
async def test_propose_from_anomaly_lands_practice_shield(tmp_path, monkeypatch):
    monkeypatch.setenv(sh.TOKEN_ENV, "")  # practice / dry_run mode — no live edge
    store = Store(tmp_path / "ghost.sqlite3")
    store.replace_inventory(PLATFORM_TENANT, "headers", EDGE, "2026-10-24T12:00:00Z")
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(599)))
    clock = {"n": 0}

    def tick():
        clock["n"] += 1
        return f"2026-10-24T12:0{clock['n']}:00Z"

    shields = sh.Shields(
        store, http, AsyncMock(), health=AsyncMock(return_value=True), pause=AsyncMock(), clock=tick
    )
    event = _load("vector_anomalies.json")[0]
    try:
        result = await propose_from_anomaly(shields, store, PLATFORM_TENANT, event)
    finally:
        await http.aclose()
    assert result["action"] == "propose_shield"
    shield = result["shield"]
    # Practice mode: proposed or dry_run / brief — never up without founder tap.
    assert shield["state"] in {"proposed", "dry_run", "brief"}
    assert shield["state"] != "up"
    assert result["match_id"]
    # Panel list would show this via /ghost/shields.
    listed = store.shields(PLATFORM_TENANT)
    assert any(s["id"] == shield["id"] for s in listed)
    matches = store.matches(PLATFORM_TENANT, "open")
    assert any(m["id"] == result["match_id"] for m in matches)


def test_status_mentions_wire_and_autumbra_only():
    body = status()
    assert body["product"] == "Autumbra Watch"
    assert "ThreatPayload" in body["wire"]
    assert "panel" in body["wire"]
    blob = str(body)
    assert "Wraith" not in blob
