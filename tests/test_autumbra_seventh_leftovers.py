"""Seventh leftovers on #345: per-tenant client hosts, second Undo tap, owner time zones."""
from __future__ import annotations

from pathlib import Path

import pytest

from agents.ghost.client_settings import (
    ClientAutumbraSettings,
    format_owner_when,
    load_settings,
    owner_time_zone,
    save_settings,
)
from agents.ghost.store import Store
from agents.ghost.threat_payload import (
    BURN_DETAIL,
    HOST_TAKEN_MSG,
    SCHEMA_VERSION,
    ThreatBurned,
    accept_threat_payload,
    bind_settings_store,
    clear_settings_store,
)
from agents.ghost.threat_queue import (
    ThreatPayloadQueue,
    already_undone_message,
    watch_enqueue_undo,
)

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa00a7"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb00b7"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_store_bind():
    clear_settings_store()
    yield
    clear_settings_store()


def test_1_two_tenant_host_registry_no_shared_set(tmp_path):
    """B can't register A's host; B's payload naming A's host is burned.

    Registry reads saved settings at check time (survives rebind / 'restart').
    """
    store = Store(tmp_path / "ghost.sqlite3")
    bind_settings_store(store)

    save_settings(
        store,
        ClientAutumbraSettings(
            tenant_id=TENANT_A,
            site_name="Acme Shop",
            watched_hosts=["shop-a.example.com"],
            owner_email="a@acme.test",
        ),
    )

    with pytest.raises(ValueError) as taken:
        save_settings(
            store,
            ClientAutumbraSettings(
                tenant_id=TENANT_B,
                site_name="Beta Shop",
                watched_hosts=["shop-a.example.com"],
                owner_email="b@beta.test",
            ),
        )
    assert str(taken.value) == HOST_TAKEN_MSG
    assert "already registered" in str(taken.value).lower()

    with pytest.raises(ThreatBurned) as burned:
        accept_threat_payload({
            "schema_version": SCHEMA_VERSION,
            "action": "propose_shield",
            "site": "shop-a.example.com",
            "kind": "block_ip",
            "address": "203.0.113.9",
            "severity": "high",
            "reason": "attacking checkout",
            "confidence": 0.9,
            "tenant_id": TENANT_B,
        })
    assert str(burned.value) == BURN_DETAIL

    ok = accept_threat_payload({
        "schema_version": SCHEMA_VERSION,
        "action": "propose_shield",
        "site": "shop-a.example.com",
        "kind": "block_ip",
        "address": "203.0.113.9",
        "severity": "high",
        "reason": "attacking checkout",
        "confidence": 0.9,
        "tenant_id": TENANT_A,
    })
    assert ok.site == "shop-a.example.com"

    # Simulate process restart: drop in-memory bind, rebind same sqlite — no sync call.
    clear_settings_store()
    bind_settings_store(store)
    again = accept_threat_payload({
        "schema_version": SCHEMA_VERSION,
        "action": "propose_shield",
        "site": "shop-a.example.com",
        "kind": "block_ip",
        "address": "203.0.113.10",
        "severity": "unknown",
        "reason": "probe",
        "confidence": 0.5,
        "tenant_id": TENANT_A,
    })
    assert again.site == "shop-a.example.com"

    # Shared in-memory set must be gone from the module.
    tp = (ROOT / "agents/ghost/threat_payload.py").read_text(encoding="utf-8")
    assert "_REGISTERED_CLIENT_HOSTS" not in tp


def test_2_second_undo_tap_already_undone_no_second_queue(tmp_path):
    q = ThreatPayloadQueue(tmp_path / "queue")
    first = watch_enqueue_undo(
        queue=q,
        prior_receipt_id="receipt-used-1",
        site="coolify.tervory.com",
        tenant_id=TENANT_A,
        rule_id="abcd",
        time_zone="UTC",
    )
    assert first["outcome"] == "queued_undo"
    assert first["queued"] is True
    inbox_after_first = list((q.root / "inbox").glob("*.json"))
    assert len(inbox_after_first) == 1

    second = watch_enqueue_undo(
        queue=q,
        prior_receipt_id="receipt-used-1",
        site="coolify.tervory.com",
        tenant_id=TENANT_A,
        rule_id="abcd",
        time_zone="UTC",
    )
    assert second["outcome"] == "already_undone"
    assert second["queued"] is False
    assert second.get("already_undone") is True
    assert second["detail"].startswith("This block was already undone on ")
    assert second["detail"].endswith(".")
    assert "UTC" in second["detail"]
    # No second inbox item.
    assert len(list((q.root / "inbox").glob("*.json"))) == 1

    # Page copy helper.
    msg = already_undone_message("2026-10-27T09:45:00Z", time_zone="UTC")
    assert msg == "This block was already undone on Oct 27, 2026, 9:45 AM UTC."

    # Undo page surfaces the sentence.
    undo_page = (ROOT / "workspace/app/autumbra/undo/[id]/page.tsx").read_text(encoding="utf-8")
    assert "alreadyUndone" in undo_page or "already_undone" in undo_page
    assert "This block was already undone" in undo_page or "loadUndoStatus" in undo_page
    button = (ROOT / "workspace/app/autumbra/undo/UndoButton.tsx").read_text(encoding="utf-8")
    assert "already_undone" in button
    api = (ROOT / "workspace/app/api/autumbra/undo/route.ts").read_text(encoding="utf-8")
    assert "already_undone" in api


def test_3_owner_pages_use_owner_time_zone(tmp_path):
    store = Store(tmp_path / "ghost.sqlite3")
    empty = ClientAutumbraSettings(tenant_id=TENANT_A)
    assert owner_time_zone(empty) == "UTC"
    assert format_owner_when("2026-10-27T09:45:00Z", empty).endswith(" UTC")

    save_settings(
        store,
        ClientAutumbraSettings(
            tenant_id=TENANT_A,
            time_zone="Africa/Johannesburg",
            owner_email="a@acme.test",
        ),
    )
    loaded = load_settings(store, TENANT_A)
    assert owner_time_zone(loaded) == "Africa/Johannesburg"
    stamped = format_owner_when("2026-10-27T09:45:00Z", loaded)
    assert "Africa/Johannesburg" in stamped
    assert not stamped.endswith(" UTC")
    store.close()

    copy = (ROOT / "workspace/lib/autumbra-copy.ts").read_text(encoding="utf-8")
    assert "timeZone" in copy
    assert "timeZone: tz" in copy
    weekly = (ROOT / "workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "timeZone" in weekly
    assert "describeReceipt(row, timeZone)" in weekly
    weekly_lib = (ROOT / "workspace/lib/autumbra-weekly.ts").read_text(encoding="utf-8")
    assert "time_zone" in weekly_lib

    # Weekly API wires time_zone from owner settings (source contract).
    app_src = (ROOT / "agents/ghost/app.py").read_text(encoding="utf-8")
    assert '"time_zone": owner_time_zone(owner_settings)' in app_src
    assert "owner_time_zone" in app_src
