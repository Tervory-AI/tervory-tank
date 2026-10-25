"""Autumbra Watch OSS intake: anomaly-only, telemetry off, ThreatPayload burn."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.ghost.threat_payload import ThreatBurned, ThreatPayload
from agents.ghost.watch_oss import (
    AnomalyEvent,
    anomaly_only,
    enabled,
    fluentbit,
    handoff_threat,
    opencti,
    status,
    steampipe,
    vector,
)


SITE = "coolify.tervory.com"


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("WATCH_OSS_ENABLED", raising=False)
    monkeypatch.delenv("GHOST_WATCH_OSS_ENABLED", raising=False)
    assert enabled() is False
    monkeypatch.setenv("WATCH_OSS_ENABLED", "1")
    assert enabled() is True


def test_anomaly_only_drops_below_threshold():
    events = [
        {"source": "vector", "site": SITE, "signal": "waf", "score": 0.5, "reason": "noise"},
        {"source": "vector", "site": SITE, "signal": "waf", "score": 0.91, "reason": "spike"},
    ]
    kept = anomaly_only(events)
    assert len(kept) == 1
    assert kept[0].score == 0.91


def test_vector_forward_burns_dirty_site():
    payloads = vector.forward_to_threat(
        [{"source": "vector", "site": "evil.example", "signal": "waf", "score": 0.99, "reason": "x"}]
    )
    assert payloads == []


def test_vector_and_fluentbit_handoff_threatpayload():
    events = [
        {
            "source": "vector",
            "site": SITE,
            "signal": "waf",
            "score": 0.93,
            "reason": "managed rule spike on Coolify",
            "confidence": 0.93,
            "cve_ids": ["CVE-2026-109618"],
        }
    ]
    out = vector.forward_to_threat(events)
    assert len(out) == 1
    assert isinstance(out[0], ThreatPayload)
    assert out[0].site in {SITE, "coolify"}

    fb = fluentbit.forward_to_threat([{**events[0], "source": "fluent_bit"}])
    assert len(fb) == 1
    assert fb[0].match_id.startswith("watch-oss:fluent_bit:")


def test_presets_on_disk_and_telemetry_off():
    for adapter in (vector, fluentbit):
        path = adapter.preset_path()
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        adapter.assert_telemetry_off(text)
        assert "autumbra" in text.lower() or "Autumbra" in text


def test_vector_preset_bans_phone_home():
    with pytest.raises(ValueError, match="telemetry"):
        vector.assert_telemetry_off(vector.render_preset() + "\nuri: https://api.vector.dev/usage\n")


def test_steampipe_readonly_gates():
    steampipe.assert_plugin_allowed("aws")
    with pytest.raises(ValueError, match="write-capable|allowlist"):
        steampipe.assert_plugin_allowed("exec")
    with pytest.raises(ValueError, match="not on Autumbra"):
        steampipe.assert_plugin_allowed("random-mutator")

    steampipe.assert_query_readonly("select name, version from aws_ec2_instance")
    with pytest.raises(ValueError, match="mutating|SELECT"):
        steampipe.assert_query_readonly("delete from aws_ec2_instance")
    with pytest.raises(ValueError, match="mutating|SELECT"):
        steampipe.assert_query_readonly("insert into x values (1)")

    env = steampipe.env_for_autumbra()
    assert env["STEAMPIPE_UPDATE_CHECK"] == "false"
    assert env["STEAMPIPE_TELEMETRY"] == "none"

    spc = steampipe.render_preset()
    assert "update_check = false" in spc
    assert 'telemetry    = "none"' in spc


def test_steampipe_rows_to_components_and_anomaly():
    comps = steampipe.rows_to_components(
        [{"name": "nginx", "version": "1.27.0", "kind": "software"}],
        app="coolify",
    )
    assert len(comps) == 1
    assert comps[0].name == "nginx"
    event = steampipe.inventory_anomaly(
        site=SITE, finding="outdated nginx on Coolify edge", score=0.85, cve_ids=["CVE-2026-109618"]
    )
    payload = handoff_threat(event)
    assert payload.severity.value in {"medium", "high", "critical", "unknown"}


def test_opencti_allowlist_and_ce_only():
    client = opencti.OpenCTIReadClient("http://127.0.0.1:8080")
    assert "cisa-kev" in client.list_allowed_feeds()
    assert client.fetch_indicators("cisa-kev") == []
    with pytest.raises(ValueError, match="allowlist"):
        client.fetch_indicators("random-darkweb-feed")
    with pytest.raises(ValueError, match="phone-home|Filigran"):
        opencti.OpenCTIReadClient("https://telemetry.filigran.io")
    with pytest.raises(ValueError, match="CE-only"):
        opencti.OpenCTIReadClient("http://127.0.0.1:8080", ce_only=False)

    # Indicators above threshold become ThreatPayloads.
    events = client.indicators_to_anomalies(
        [{"name": "KEV match", "score": 0.92, "cve_ids": ["CVE-2026-109618"]}],
        site=SITE,
    )
    assert len(events) == 1
    assert len(client.handoff(events)) == 1


def test_handoff_burns_low_score():
    with pytest.raises(ThreatBurned):
        handoff_threat(
            AnomalyEvent(source="vector", site=SITE, signal="waf", score=0.2, reason="noise")
        )


def test_status_autumbra_copy_not_live():
    body = status()
    assert body["product"] == "Autumbra Watch"
    assert body["enabled"] is False or isinstance(body["enabled"], bool)
    for name, meta in body["adapters"].items():
        assert meta["live_in_product"] is False
        assert "vault_sha" in meta
    # Naming law: no Ghost/Wraith product claims in this status blob.
    blob = str(body)
    assert "Wraith" not in blob
