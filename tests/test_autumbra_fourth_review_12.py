"""Fourth-review findings on #345: durable shields, queue door, UUID 4xx, email from receipts, advisory match."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from agents.ghost.app import create_app
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings, save_settings
from agents.ghost.durable_shields import (
    load_control,
    persist_control,
    read_shields_table,
    shields_good_path,
    shields_path,
)
from agents.ghost.fixture_edge import FixtureEdgeControl
from agents.ghost.market_lab_intel import load_market_lab_advisories
from agents.ghost.owner_email import FixtureEmailTransport
from agents.ghost.owner_email_jobs import (
    default_receipt_url,
    list_clients_with_owner,
    normalize_severity,
    run_weekly_owner_updates,
    week_stats_from_receipts,
)
from agents.ghost.store import Store
from agents.ghost.threat_payload import ThreatSeverity
from agents.ghost.threat_queue import (
    ThreatPayloadQueue,
    enforce_drain_once,
    watch_enqueue_fixture_attack,
)

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0045"
KEY = "tank-test-key"


def test_finding2_corrupt_shields_keeps_last_good_and_receipt(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "box"
    data_dir.mkdir()
    control = FixtureEdgeControl(tenant_id=TENANT, site="coolify.tervory.com")
    control.blocked["deadbeef"] = {
        "rule_id": "deadbeef",
        "address": "203.0.113.50",
        "site": "coolify.tervory.com",
    }
    persist_control(data_dir, control)
    assert shields_good_path(data_dir).exists()
    # Truncate primary (corrupt) — last good must still restore shields.
    shields_path(data_dir).write_bytes(b'{"blocked":')
    table, source = read_shields_table(data_dir)
    assert source == "good"
    assert table is not None and "deadbeef" in table["blocked"]
    restored = load_control(data_dir, tenant_id=TENANT)
    assert any(r["rule_id"] == "deadbeef" for r in restored.list_blocked())

    # Boot path must emit a corrupt receipt and not wipe shields.
    monkeypatch.setenv("TENANT_ID", TENANT)
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(tmp_path / "q"))
    from agents.ghost.enforce_app import create_enforce_app

    app = create_enforce_app()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["blocked"] == 1
    receipts = ThreatPayloadQueue(tmp_path / "q").list_receipts()
    assert any(
        r.get("kind") == "restart_shield_drop" and r.get("outcome") == "corrupt_shields_file"
        for r in receipts
    )
    # Atomic persist must have rewritten a valid primary.
    table2, source2 = read_shields_table(data_dir)
    assert source2 == "primary"
    assert "deadbeef" in (table2 or {}).get("blocked", {})


def test_finding2_persist_is_atomic(tmp_path: Path):
    data_dir = tmp_path / "box"
    data_dir.mkdir()
    control = FixtureEdgeControl(tenant_id=TENANT)
    control.blocked["aa"] = {"rule_id": "aa", "address": "203.0.113.1"}
    path = persist_control(data_dir, control)
    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "aa" in raw["blocked"]


def test_finding3_4_5_queue_accept_threat_payload_quarantines_with_tenant(tmp_path: Path):
    queue = ThreatPayloadQueue(tmp_path / "q")
    # Malformed propose_shield (no kind) — model_validate would accept; accept_threat_payload burns.
    bad_propose = {
        "schema_version": "ghost.threat.v1",
        "action": "propose_shield",
        "site": "coolify.tervory.com",
        "tenant_id": TENANT,
        "reason": "no kind",
    }
    (queue.root / "inbox" / "badpropose.json").write_text(
        json.dumps(bad_propose), encoding="utf-8"
    )
    bad_undo = {
        "schema_version": "ghost.threat.v1",
        "action": "undo_shield",
        "site": "coolify.tervory.com",
        "tenant_id": TENANT,
        "reason": "no ids",
    }
    (queue.root / "inbox" / "badundo.json").write_text(
        json.dumps(bad_undo), encoding="utf-8"
    )
    settings = ClientAutumbraSettings(
        tenant_id=TENANT, shield_mode=ApplyMode.auto_when_checks_pass
    )
    control = FixtureEdgeControl(tenant_id=TENANT)
    # Drain: both quarantined; then a good item applies.
    watch_enqueue_fixture_attack(
        queue=queue,
        raw_log="src=203.0.113.9 path=/a",
        site="coolify.tervory.com",
        address="203.0.113.9",
        tenant_id=TENANT,
    )
    outcomes = []
    for _ in range(10):
        receipt = enforce_drain_once(queue, settings=settings, control=control)
        if receipt is None:
            break
        outcomes.append(receipt)
    # take() quarantines bad items inside the loop; receipts are on disk.
    quarantined = [r for r in queue.list_receipts() if r.get("outcome") == "quarantined"]
    assert len(quarantined) >= 2, queue.list_receipts()
    assert all(r.get("tenant_id") == TENANT for r in quarantined)
    assert any(r.get("applied") for r in outcomes)
    assert len(queue.list_quarantine()) >= 2


def test_finding4_non_uuid_tenant_is_4xx(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TANK_KEY", KEY)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE_ROOT", str(tmp_path / "queues"))
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            "/ghost/autumbra/queue/fixture-attack",
            headers={"X-Tank-Key": KEY},
            json={
                "tenant_id": "../../etc",
                "raw_log": "src=203.0.113.1 path=/a",
                "site": "coolify.tervory.com",
                "address": "203.0.113.1",
            },
        )
        assert res.status_code == 400, res.text
        assert res.status_code < 500


def test_finding5_7_8_9_owner_email_from_receipts_not_request(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", "test-undo-secret-fourth")
    monkeypatch.setenv("TANK_KEY", KEY)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    root = tmp_path / "queues"
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE_ROOT", str(root))
    app = create_app()
    headers = {"X-Tank-Key": KEY}
    with TestClient(app) as client:
        client.post(
            "/ghost/autumbra/settings",
            headers=headers,
            json={
                "tenant_id": TENANT,
                "site_name": "coolify.tervory.com",
                "owner_email": "owner-real@tervory.com",
                "shield_mode": ApplyMode.auto_when_checks_pass.value,
            },
        )
        # Inflated request numbers must NOT appear in the email.
        res = client.post(
            "/ghost/autumbra/owner-update",
            headers=headers,
            json={
                "tenant_id": TENANT,
                "threats_found": 99999,
                "critical": [{
                    "stack": "PHP",
                    "rating": "critical",
                    "advisory_url": "https://evil.example/cve",
                }],
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()["body"]
        subject = res.json()["subject"]
        assert "99999" not in subject
        assert "99999" not in body
        assert "/autumbra/receipts/weekly/" in body
        assert "/receipts/weekly/" + TENANT not in body.replace("/autumbra/receipts/weekly/", "")


import pytest as _pytest
from datetime import datetime as _dt, timezone as _tz


@_pytest.fixture(autouse=True)
def _fixed_report_week(monkeypatch):
    """These receipts are dated 26 Oct 2026. Pin the report week to that week, so the
    tests don't fail once the real clock moves on (they first failed on 2 Nov 2026)."""
    import agents.ghost.owner_email_jobs as jobs
    fixed = _dt(2026, 10, 30, 12, 0, tzinfo=_tz.utc)
    real = jobs.week_bounds
    monkeypatch.setattr(jobs, "week_bounds", lambda *, now=None: real(now=now or fixed))


def test_finding8_weekly_covers_every_owner_from_receipts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", "test-undo-secret-fourth")
    store = Store(tmp_path / "g.sqlite3")
    a = ClientAutumbraSettings(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa00a1",
        site_name="a.example",
        owner_email="a@example.test",
        shield_mode=ApplyMode.auto_when_checks_pass,
    )
    b = ClientAutumbraSettings(
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb00b2",
        site_name="b.example",
        owner_email="b@example.test",
    )
    save_settings(store, a)
    save_settings(store, b)
    clients = list_clients_with_owner(store)
    assert {c.tenant_id for c in clients} == {a.tenant_id, b.tenant_id}
    # Plant one applied receipt for A only.
    receipts_a = [{
        "id": "r1",
        "tenant_id": a.tenant_id,
        "role": "Enforce",
        "outcome": "applied",
        "applied": True,
        "severity": "unknown",
        "undo": {"rule_id": "abcd"},
        "address": "203.0.113.1",
        "timestamp": "2026-10-26T12:00:00Z",
        "site": "coolify.tervory.com",
        "source_url": "https://feodotracker.abuse.ch/",
        "source_name": "abuse.ch Feodo",
    }]
    transport = FixtureEmailTransport()
    results = run_weekly_owner_updates(
        clients,
        receipts_by_tenant={a.tenant_id: receipts_a, b.tenant_id: []},
        transport=transport,
    )
    assert len(results) == 2
    assert all(r["sent"] for r in results)
    by_to = {r["to"]: r for r in results}
    assert "Quiet week." in by_to["b@example.test"]["body"]
    assert "Quiet week." not in by_to["a@example.test"]["body"]
    assert default_receipt_url(a.tenant_id) in by_to["a@example.test"]["body"]
    assert "/autumbra/receipts/weekly/" in by_to["a@example.test"]["body"]


def test_finding11_invented_advisory_never_stamps_severity(tmp_path: Path):
    queue = ThreatPayloadQueue(tmp_path / "q")
    load_market_lab_advisories([])  # empty Market Lab catalog
    watch = watch_enqueue_fixture_attack(
        queue=queue,
        raw_log="src=203.0.113.9 path=/a",
        site="coolify.tervory.com",
        address="203.0.113.9",
        advisory={
            "url": "nonsense",
            "rating": "critical",
            "advisory_id": "CVE-2026-9999",
        },
    )
    assert watch["severity"] == ThreatSeverity.unknown.value
    assert watch["cve_ids"] == []
    assert watch.get("advisory_url") in (None, "")
    # Caller matched:true + invented CVE on public host MUST be ignored.
    watch_asserted = watch_enqueue_fixture_attack(
        queue=queue,
        raw_log="src=203.0.113.11 path=/a",
        site="coolify.tervory.com",
        address="203.0.113.11",
        advisory={
            "rating": "critical",
            "advisory_id": "CVE-2026-9999",
            "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2026-9999",
            "matched": True,
            "match_id": "m1",
            "from_match": True,
        },
    )
    assert watch_asserted["severity"] == ThreatSeverity.unknown.value
    assert watch_asserted["cve_ids"] == []
    # Only Autumbra's own Market Lab match stamps severity.
    load_market_lab_advisories([{
        "advisory_id": "CVE-2026-109618",
        "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-109618",
        "rating": "critical",
        "component": "php",
        "source_name": "NVD",
        "source_url": "https://nvd.nist.gov/vuln/detail/CVE-2026-109618",
    }])
    watch2 = watch_enqueue_fixture_attack(
        queue=queue,
        raw_log="src=203.0.113.10 path=/a",
        site="coolify.tervory.com",
        address="203.0.113.10",
        advisory={
            "rating": "critical",
            "advisory_id": "CVE-2026-109618",
            "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2026-109618",
            # caller flags ignored even when present
            "matched": True,
        },
    )
    assert watch2["severity"] == "critical"
    assert "CVE-2026-109618" in watch2["cve_ids"]
    load_market_lab_advisories([])


def test_finding6_undo_weekly_pages_owner_facing():
    undo = Path("workspace/app/autumbra/undo/[id]/page.tsx").read_text(encoding="utf-8")
    weekly = Path("workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx").read_text(
        encoding="utf-8"
    )
    button = Path("workspace/app/autumbra/undo/UndoButton.tsx").read_text(encoding="utf-8")
    api = Path("workspace/app/api/autumbra/undo/route.ts").read_text(encoding="utf-8")
    mw = Path("workspace/middleware.ts").read_text(encoding="utf-8")
    assert "ThreatPayload" not in undo
    assert "/ghost/autumbra" not in undo
    assert "UndoButton" in undo
    assert "Undo this shield" in button
    assert "token" in button
    assert "verifyUndoToken" in api
    assert '"/api/autumbra/undo"' in mw
    assert "founder console" not in weekly.lower()
    assert "/ghost/autumbra" not in weekly
    assert "receipts.map" in weekly or "receipts.length" in weekly
    assert "Promise<" in undo and "Promise<" in weekly


def test_finding5_on_act_email_wired():
    src = Path("agents/ghost/enforce_app.py").read_text(encoding="utf-8")
    assert "on_act_email" in src
    assert "_default_on_act_email" in src
    assert "build_owner_update_from_receipts" in src


def test_week_stats_from_receipts_ignores_request_shaped_noise(monkeypatch):
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", "test-undo-secret-for-stats")
    now = "2026-10-26T12:00:00Z"
    old = "2026-09-01T12:00:00Z"
    stats = week_stats_from_receipts(
        [{
            "tenant_id": TENANT,
            "role": "Enforce",
            "outcome": "applied",
            "applied": True,
            "severity": ThreatSeverity.critical,  # enum must count as critical
            "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2024-1234",
            "cve_ids": ["CVE-2024-1234"],
            "undo": {"rule_id": "ab"},
            "id": "rid-1",
            "timestamp": now,
            "site": "coolify.tervory.com",
        }, {
            # Outside the reported week — must not count.
            "tenant_id": TENANT,
            "role": "Enforce",
            "outcome": "applied",
            "applied": True,
            "severity": "critical",
            "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2024-9999",
            "cve_ids": ["CVE-2024-9999"],
            "undo": {"rule_id": "cd"},
            "id": "rid-old",
            "timestamp": old,
        }],
        tenant_id=TENANT,
    )
    assert stats["threats_found"] == 1
    assert len(stats["critical"]) == 1
    assert stats["critical"][0]["rating"] == "critical"
    assert stats["shield"]["blocked_addresses"] == 1
    assert "/autumbra/undo/rid-1" in stats["undo_shield_url"]
    assert "token=" in stats["undo_shield_url"]
    assert normalize_severity(ThreatSeverity.critical) == "critical"
    assert normalize_severity("ThreatSeverity.critical") == "critical"
