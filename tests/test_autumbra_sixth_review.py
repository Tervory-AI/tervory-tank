"""Sixth FAIL return on #345: CI lint, compose secret, honest email, plain pages, client sites."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings, save_settings
from agents.ghost.owner_email_jobs import (
    build_owner_update_from_receipts,
    default_receipt_url,
    default_undo_url,
)
from agents.ghost.store import Store
from agents.ghost.threat_payload import (
    BURN_DETAIL,
    SCHEMA_VERSION,
    ThreatBurned,
    accept_threat_payload,
    bind_settings_store,
    clear_settings_store,
    register_client_watched_hosts,
)

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa00a6"
SECRET = "test-undo-secret-sixth-review"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_hosts(tmp_path_factory):
    clear_settings_store()
    yield
    clear_settings_store()


def test_1_lint_clean_and_compose_wires_undo_secret():
    fifth = (ROOT / "tests/test_autumbra_fifth_review_security.py").read_text(encoding="utf-8")
    head = "\n".join(fifth.splitlines()[:20])
    assert "import os" not in head

    app = (ROOT / "agents/ghost/app.py").read_text(encoding="utf-8")
    assert "PROTECT_HOST, default_undo_url" not in app
    assert "from .owner_email_jobs import default_undo_url, week_bounds" in app

    workspace = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    ws_block = workspace.split("  workspace:")[1].split("  site:")[0]
    assert "AUTUMBRA_UNDO_TOKEN_SECRET: ${AUTUMBRA_UNDO_TOKEN_SECRET:-}" in ws_block

    watch = (ROOT / "agents/ghost/docker-compose.yml").read_text(encoding="utf-8")
    assert "AUTUMBRA_UNDO_TOKEN_SECRET: ${AUTUMBRA_UNDO_TOKEN_SECRET:-}" in watch

    enforce = (ROOT / "agents/ghost/docker-compose.enforce.yml").read_text(encoding="utf-8")
    assert "AUTUMBRA_UNDO_TOKEN_SECRET: ${AUTUMBRA_UNDO_TOKEN_SECRET:-}" in enforce

    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AUTUMBRA_UNDO_TOKEN_SECRET=" in env
    assert "Workspace, Watch" in env or "Workspace" in env


def test_2_secret_missing_no_one_tap_promise_no_dead_links(monkeypatch):
    monkeypatch.delenv("AUTUMBRA_UNDO_TOKEN_SECRET", raising=False)
    assert default_undo_url("r1", tenant_id=TENANT, rule_id="x", site="coolify.tervory.com") == ""
    assert default_receipt_url(TENANT) == ""

    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        site_name="coolify.tervory.com",
        owner_email="owner@example.test",
        fix_mode=ApplyMode.approve_each,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mail = build_owner_update_from_receipts(
        settings=settings,
        receipts=[{
            "id": "r-dead",
            "tenant_id": TENANT,
            "role": "Enforce",
            "outcome": "applied",
            "applied": True,
            "severity": "unknown",
            "undo": {"rule_id": "s1"},
            "site": "coolify.tervory.com",
            "timestamp": now,
            "source_url": "https://feodotracker.abuse.ch/",
            "source_name": "abuse.ch Feodo",
        }],
    )
    body = mail["body"]
    assert "undo it here with one tap" not in body.lower()
    assert "/autumbra/undo/" not in body
    assert "token=" not in body
    assert "autumbra/receipts/weekly/" not in body
    assert "sign in" in body.lower() or "dashboard" in body.lower()
    assert "reply to this email" in body.lower()


def test_3_secret_present_still_promises_one_tap(monkeypatch):
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", SECRET)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        site_name="coolify.tervory.com",
        owner_email="owner@example.test",
        fix_mode=ApplyMode.approve_each,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mail = build_owner_update_from_receipts(
        settings=settings,
        receipts=[{
            "id": "r-ok",
            "tenant_id": TENANT,
            "role": "Enforce",
            "outcome": "applied",
            "applied": True,
            "severity": "unknown",
            "undo": {"rule_id": "s1"},
            "site": "coolify.tervory.com",
            "timestamp": now,
        }],
    )
    assert "undo it here with one tap" in mail["body"]
    assert "token=" in mail["body"]
    assert "/autumbra/undo/r-ok" in mail["body"]


def test_4_owner_pages_plain_english_no_raw_codes_or_uuids():
    weekly = (ROOT / "workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx").read_text(
        encoding="utf-8"
    )
    undo = (ROOT / "workspace/app/autumbra/undo/[id]/page.tsx").read_text(encoding="utf-8")
    copy = (ROOT / "workspace/lib/autumbra-copy.ts").read_text(encoding="utf-8")

    assert "Client reference" not in weekly
    assert "Reference:" not in undo
    assert "describeReceipt" in weekly
    assert "Undo this block" in weekly
    assert "outcomeLabel" in copy
    assert "We blocked an attacking address" in copy
    assert "formatWhen" in copy
    # Must not join raw outcome · severity as the link label.
    assert 'row.outcome, row.severity, row.site' not in weekly
    assert "<code>{tenant}</code>" not in weekly
    assert "<code>{resolved.id}</code>" not in undo


def test_5_registered_client_site_accepted_unregistered_burned(tmp_path):
    store = Store(tmp_path / "ghost.sqlite3")
    bind_settings_store(store)
    try:
        # Garbage / unregistered still burns (standing).
        with pytest.raises(ThreatBurned) as burned:
            accept_threat_payload({
                "schema_version": SCHEMA_VERSION,
                "action": "propose_shield",
                "site": "evil.example",
                "kind": "block_ip",
                "address": "203.0.113.9",
                "severity": "unknown",
                "reason": "probe",
                "confidence": 0.5,
            })
        assert str(burned.value) == BURN_DETAIL

        # Unregistered shop still burns.
        with pytest.raises(ThreatBurned):
            accept_threat_payload({
                "schema_version": SCHEMA_VERSION,
                "action": "propose_shield",
                "site": "shop-a.example.com",
                "kind": "block_ip",
                "address": "203.0.113.9",
                "severity": "unknown",
                "reason": "probe",
                "confidence": 0.5,
                "tenant_id": TENANT,
            })

        # Tenant registers the shop in saved settings → accept succeeds.
        save_settings(
            store,
            ClientAutumbraSettings(
                tenant_id=TENANT,
                site_name="Acme Shop",
                watched_hosts=["shop-a.example.com"],
                owner_email="owner@acme.test",
            ),
        )
        payload = accept_threat_payload({
            "schema_version": SCHEMA_VERSION,
            "action": "propose_shield",
            "site": "shop-a.example.com",
            "kind": "block_ip",
            "address": "203.0.113.9",
            "severity": "high",
            "reason": "attacking checkout",
            "confidence": 0.9,
            "tenant_id": TENANT,
        })
        assert payload.site == "shop-a.example.com"

        # Hostname-shaped site_name also registers (saved).
        save_settings(
            store,
            ClientAutumbraSettings(
                tenant_id=TENANT,
                site_name="shop-b.example.com",
                watched_hosts=[],
            ),
        )
        payload2 = accept_threat_payload({
            "schema_version": SCHEMA_VERSION,
            "action": "propose_shield",
            "site": "shop-b.example.com",
            "kind": "block_ip",
            "address": "203.0.113.10",
            "severity": "unknown",
            "reason": "probe",
            "confidence": 0.5,
            "tenant_id": TENANT,
        })
        assert payload2.site == "shop-b.example.com"

        # Dogfood still works without registration.
        dog = accept_threat_payload({
            "schema_version": SCHEMA_VERSION,
            "action": "propose_shield",
            "site": "coolify.tervory.com",
            "kind": "block_ip",
            "address": "203.0.113.11",
            "severity": "unknown",
            "reason": "probe",
            "confidence": 0.5,
        })
        assert dog.site == "coolify.tervory.com"
    finally:
        clear_settings_store()
        store.close()


def test_5b_register_helper_and_invalid_watched_host():
    added = register_client_watched_hosts(["Shop-A.Example.COM", "not a host", "http://evil.com"])
    assert added == ["shop-a.example.com"]
    with pytest.raises(Exception):
        ClientAutumbraSettings(
            tenant_id=TENANT,
            watched_hosts=["http://evil.com/path"],
        )
