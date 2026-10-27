"""Fifth FAIL return on #345: receipts auth, undo token-only, act email, IOC rating, weekly links."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from agents.ghost.app import create_app
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.enforce_app import _default_on_act_email
from agents.ghost.market_lab_intel import (
    accept_ioc_bundle,
    load_market_lab_advisories,
    match_advisory_from_market_lab,
    register_advisories_from_ioc_bundle,
)
from agents.ghost.owner_email import DEFAULT_FIXTURE_TRANSPORT, build_owner_update
from agents.ghost.owner_email_jobs import (
    build_owner_update_from_receipts,
    default_receipt_url,
    default_undo_url,
    week_stats_from_receipts,
)
from agents.ghost.threat_queue import ThreatPayloadQueue
from agents.ghost.undo_token import (
    sign_receipts_token,
    sign_undo_token,
    verify_receipts_token,
    verify_undo_token,
)

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa00a5"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb00b5"
KEY = "tank-test-key-fifth"
SECRET = "test-undo-secret-fifth-review"


@pytest.fixture(autouse=True)
def _undo_secret(monkeypatch):
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", SECRET)
    # Never allow webhook secret fallback — leave it set to prove we ignore it.
    monkeypatch.setenv("AUTUMBRA_EDGE_WEBHOOK_SECRET", "must-not-be-used-as-undo-secret")
    monkeypatch.setenv("TANK_KEY", KEY)


def test_1_receipts_require_token_or_tank_signed_out_attacks(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE_ROOT", str(tmp_path / "queues"))
    q = ThreatPayloadQueue(tmp_path / "queues" / TENANT_A)
    q.write_receipt({
        "id": "r-a1",
        "tenant_id": TENANT_A,
        "role": "Enforce",
        "outcome": "applied",
        "applied": True,
        "severity": "critical",
        "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2026-1",
        "undo": {"rule_id": "rule-a"},
        "site": "coolify.tervory.com",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "address": "203.0.113.9",
    })
    app = create_app()
    with TestClient(app) as client:
        # No token, no tank key → 401, nothing returned.
        bare = client.get(f"/ghost/autumbra/receipts/weekly/{TENANT_A}")
        assert bare.status_code == 401
        assert bare.json().get("receipts") in (None, [])

        forged = client.get(
            f"/ghost/autumbra/receipts/weekly/{TENANT_A}",
            params={"token": "forged.notreal"},
        )
        assert forged.status_code == 401

        # Expired token for A.
        expired = sign_receipts_token(tenant_id=TENANT_A, ttl_sec=60, now=time.time() - 3600)
        exp_res = client.get(
            f"/ghost/autumbra/receipts/weekly/{TENANT_A}",
            params={"token": expired},
        )
        assert exp_res.status_code == 401

        # Other-tenant token (B) on A's path → 401.
        token_b = sign_receipts_token(tenant_id=TENANT_B)
        other = client.get(
            f"/ghost/autumbra/receipts/weekly/{TENANT_A}",
            params={"token": token_b},
        )
        assert other.status_code == 401

        # Valid A token → 200 with A's receipts; undo links carry token.
        token_a = sign_receipts_token(tenant_id=TENANT_A)
        ok = client.get(
            f"/ghost/autumbra/receipts/weekly/{TENANT_A}",
            params={"token": token_a},
        )
        assert ok.status_code == 200, ok.text
        rows = ok.json()["receipts"]
        assert len(rows) == 1
        assert rows[0]["id"] == "r-a1"
        assert "token=" in (rows[0].get("url") or "")

        # Tank key also authorizes (server-side proxy after Next verified).
        via_tank = client.get(
            f"/ghost/autumbra/receipts/weekly/{TENANT_A}",
            headers={"x-tank-key": KEY},
        )
        assert via_tank.status_code == 200
        assert via_tank.json()["count"] == 1


def test_2_undo_token_only_fail_closed_no_webhook_fallback(monkeypatch):
    # Secret unset → sign/verify fail closed (no webhook secret fallback).
    monkeypatch.delenv("AUTUMBRA_UNDO_TOKEN_SECRET", raising=False)
    monkeypatch.setenv("AUTUMBRA_EDGE_WEBHOOK_SECRET", "webhook-only")
    with pytest.raises(RuntimeError, match="AUTUMBRA_UNDO_TOKEN_SECRET"):
        sign_undo_token(tenant_id=TENANT_A, receipt_id="r1", rule_id="x")

    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", SECRET)
    good = sign_undo_token(
        tenant_id=TENANT_A, receipt_id="r1", rule_id="rule-a", site="coolify.tervory.com"
    )
    payload = verify_undo_token(good)
    assert payload["tenant_id"] == TENANT_A
    assert payload["receipt_id"] == "r1"
    assert payload["rule_id"] == "rule-a"

    with pytest.raises(ValueError):
        verify_undo_token("forged.token")
    expired = sign_undo_token(
        tenant_id=TENANT_A, receipt_id="r1", rule_id="x", ttl_sec=60, now=time.time() - 7200
    )
    with pytest.raises(ValueError, match="expired"):
        verify_undo_token(expired)

    # Source: API route must not accept legacy body fields.
    api = Path("workspace/app/api/autumbra/undo/route.ts").read_text(encoding="utf-8")
    assert "Legacy body fields" not in api
    assert "body.tenant_id" not in api
    assert "body.receipt_id" not in api
    assert "verifyUndoToken" in api
    # TS secret: no webhook fallback.
    ts = Path("workspace/lib/autumbra-undo-token.ts").read_text(encoding="utf-8")
    assert "AUTUMBRA_EDGE_WEBHOOK_SECRET" not in ts
    py = Path("agents/ghost/undo_token.py").read_text(encoding="utf-8")
    assert "AUTUMBRA_EDGE_WEBHOOK_SECRET" not in py


def test_3_act_email_undo_link_carries_signed_token(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(tmp_path / "q"))
    DEFAULT_FIXTURE_TRANSPORT.sent.clear()
    settings = ClientAutumbraSettings(
        tenant_id=TENANT_A,
        site_name="coolify.tervory.com",
        owner_email="owner-a@example.test",
        shield_mode=ApplyMode.auto_when_checks_pass,
        fix_mode=ApplyMode.approve_each,
    )
    receipt = {
        "id": "act-r1",
        "tenant_id": TENANT_A,
        "role": "Enforce",
        "outcome": "applied",
        "applied": True,
        "severity": "unknown",
        "undo": {"rule_id": "shield-1"},
        "site": "coolify.tervory.com",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "address": "203.0.113.44",
    }
    q = ThreatPayloadQueue(tmp_path / "q")
    q.write_receipt(receipt)
    _default_on_act_email(receipt, settings)
    assert DEFAULT_FIXTURE_TRANSPORT.sent, "act email should send"
    body = DEFAULT_FIXTURE_TRANSPORT.sent[-1]["body"]
    assert "/autumbra/undo/act-r1" in body
    assert "token=" in body
    # Extract token and verify it names this tenant + shield.
    for part in body.split():
        if "token=" in part and "/autumbra/undo/" in part:
            url = part.strip("().")
            qs = parse_qs(urlparse(url).query)
            tok = qs["token"][0]
            got = verify_undo_token(tok)
            assert got["tenant_id"] == TENANT_A
            assert got["receipt_id"] == "act-r1"
            assert got["rule_id"] == "shield-1"
            break
    else:
        raise AssertionError("no signed undo URL in act email")


def test_4_act_email_counts_from_week_receipts(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(tmp_path / "q"))
    DEFAULT_FIXTURE_TRANSPORT.sent.clear()
    settings = ClientAutumbraSettings(
        tenant_id=TENANT_A,
        site_name="coolify.tervory.com",
        owner_email="owner-a@example.test",
        fix_mode=ApplyMode.approve_each,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = ThreatPayloadQueue(tmp_path / "q")
    earlier = {
        "id": "week-r0",
        "tenant_id": TENANT_A,
        "role": "Enforce",
        "outcome": "applied",
        "applied": True,
        "severity": "critical",
        "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2026-109618",
        "cve_ids": ["CVE-2026-109618"],
        "undo": {"rule_id": "old"},
        "site": "coolify.tervory.com",
        "timestamp": now,
    }
    current = {
        "id": "week-r1",
        "tenant_id": TENANT_A,
        "role": "Enforce",
        "outcome": "applied",
        "applied": True,
        "severity": "unknown",
        "undo": {"rule_id": "new"},
        "site": "coolify.tervory.com",
        "timestamp": now,
        "source_url": "https://feodotracker.abuse.ch/",
        "source_name": "abuse.ch Feodo",
    }
    q.write_receipt(earlier)
    q.write_receipt(current)
    _default_on_act_email(current, settings)
    sent = DEFAULT_FIXTURE_TRANSPORT.sent[-1]
    # Two threats this week, one critical — not "1 threats found, 0 critical".
    assert "2 threats found, 1 critical" in sent["subject"]


def test_5_auto_fix_paragraph_only_with_real_pr():
    settings = ClientAutumbraSettings(
        tenant_id=TENANT_A,
        site_name="coolify.tervory.com",
        fix_mode=ApplyMode.auto_when_checks_pass,
        owner_email="o@example.test",
    )
    # IP block only — shield undo must NOT trigger "patched versions".
    mail = build_owner_update(
        settings=settings,
        site_name="coolify.tervory.com",
        threats_found=1,
        critical=[],
        receipt_url="https://protect.tervory.com/autumbra/receipts/weekly/" + TENANT_A,
        undo_shield_url="https://protect.tervory.com/autumbra/undo/r1?token=x",
        undo_fix_url="https://protect.tervory.com/autumbra/undo/r1?token=x",  # shield reused
        shield={"blocked_addresses": 1, "source_name": "", "source_url": ""},
    )
    assert "patched versions" not in mail["body"]
    assert "let us fix this kind of problem automatically" not in mail["body"]
    assert "blocked 1" in mail["body"] or "blocked" in mail["body"]

    # Real code fix + PR → auto paragraph with PR link.
    mail2 = build_owner_update(
        settings=settings,
        site_name="coolify.tervory.com",
        threats_found=1,
        critical=[],
        receipt_url="https://protect.tervory.com/autumbra/receipts/weekly/" + TENANT_A,
        pr_url="https://github.com/example/repo/pull/9",
        undo_fix_url="https://protect.tervory.com/autumbra/undo/r2?token=y",
    )
    assert "let us fix this kind of problem automatically" in mail2["body"]
    assert "patched versions" in mail2["body"]
    assert "https://github.com/example/repo/pull/9" in mail2["body"]

    # week_stats must not set undo_fix_url for an IP-block-only receipt.
    stats = week_stats_from_receipts(
        [{
            "id": "ip1",
            "tenant_id": TENANT_A,
            "role": "Enforce",
            "outcome": "applied",
            "applied": True,
            "severity": "unknown",
            "undo": {"rule_id": "ip"},
            "site": "coolify.tervory.com",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }],
        tenant_id=TENANT_A,
    )
    assert stats["undo_fix_url"] == ""
    assert stats["pr_url"] == ""
    assert stats["undo_shield_url"] and "token=" in stats["undo_shield_url"]


def test_6_accept_ioc_bundle_keeps_rating_for_critical_receipt():
    load_market_lab_advisories([])
    bundle = accept_ioc_bundle({
        "schema_version": "market_lab.ioc.v1",
        "bundle_id": "ml-crit-1",
        "paid": False,
        "sources": [{
            "id": "nvd",
            "name": "NVD",
            "url": "https://nvd.nist.gov/",
        }],
        "indicators": [{
            "kind": "cve",
            "value": "CVE-2026-109618",
            "rating": "critical",
            "component": "php",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-109618",
            "source_ids": ["nvd"],
        }],
    })
    assert bundle["indicators"][0]["rating"] == "critical"
    n = register_advisories_from_ioc_bundle(bundle)
    assert n == 1
    matched = match_advisory_from_market_lab({
        "advisory_id": "CVE-2026-109618",
        "advisory_url": "https://nvd.nist.gov/vuln/detail/CVE-2026-109618",
    })
    assert matched is not None
    assert matched["rating"] == "critical"
    load_market_lab_advisories([])


def test_7_weekly_page_no_workspace_menu_and_links_use_token():
    page = Path("workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx").read_text(
        encoding="utf-8"
    )
    nav = Path("workspace/app/product-nav.ts").read_text(encoding="utf-8")
    assert "mayReadWeeklyReceipts" in page
    assert "token=" in page
    assert '"/autumbra"' in nav
    assert '"/autumbra"' in nav.split("OWN_SHELL_NESTED")[1].split("]")[0] or \
        "/autumbra" in nav.split("OWN_SHELL_NESTED")[1].split("];")[0]
    assert "Dashboard" not in page
    assert "Projects" not in page
    # Receipt URL from jobs carries token when secret set.
    url = default_receipt_url(TENANT_A)
    assert f"/autumbra/receipts/weekly/{TENANT_A}" in url
    assert "token=" in url
    tok = parse_qs(urlparse(url).query)["token"][0]
    assert verify_receipts_token(tok)["tenant_id"] == TENANT_A
    undo = default_undo_url(
        "r-link", tenant_id=TENANT_A, rule_id="rr", site="coolify.tervory.com"
    )
    assert "token=" in undo
    assert verify_undo_token(parse_qs(urlparse(undo).query)["token"][0])["tenant_id"] == TENANT_A


def test_build_owner_update_from_receipts_act_path_signs_undo():
    settings = ClientAutumbraSettings(
        tenant_id=TENANT_A,
        site_name="coolify.tervory.com",
        owner_email="o@example.test",
        fix_mode=ApplyMode.approve_each,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mail = build_owner_update_from_receipts(
        settings=settings,
        receipts=[{
            "id": "from-stats",
            "tenant_id": TENANT_A,
            "role": "Enforce",
            "outcome": "applied",
            "applied": True,
            "severity": "unknown",
            "undo": {"rule_id": "s1"},
            "site": "coolify.tervory.com",
            "timestamp": now,
            "source_url": "https://feodotracker.abuse.ch/",
            "source_name": "abuse.ch",
        }],
    )
    assert "token=" in mail["body"]
