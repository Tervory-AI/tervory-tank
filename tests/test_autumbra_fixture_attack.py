"""Fixture attack: rules decide, shield dry-run in budget, one-tap undo, receipt stamped."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings, save_settings
from agents.ghost.never_block import may_block_ip
from agents.ghost.owner_email import build_owner_update
from agents.ghost import shields as sh
from agents.ghost.models import PLATFORM_TENANT
from agents.ghost.speed_budgets import budgets_ok, stamp_budget
from agents.ghost.store import Store


EDGE = [
    {"app": "coolify", "kind": "edge", "name": "cloudflare", "version": "current", "ecosystem": "generic"},
]


def test_fixture_attack_shield_undo_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(sh.TOKEN_ENV, "")  # Watch/dry — no live CF from this process
    store = Store(tmp_path / "g.sqlite3")
    store.replace_inventory(PLATFORM_TENANT, "headers", EDGE, "2026-10-26T12:00:00Z")
    settings = save_settings(store, ClientAutumbraSettings(
        tenant_id=PLATFORM_TENANT,
        site_name="coolify.tervory.com",
        shield_mode=ApplyMode.approve_each,
        fix_mode=ApplyMode.approve_each,
        cloudflare_connected=True,
    ))
    raw_log = "2026-10-26T12:00:01Z src=203.0.113.200 path=/admin scanner=nuclei"
    ok, why = may_block_ip("203.0.113.200", raw_log=raw_log)
    assert ok and why == "ok"

    async def run():
        room = sh.Shields(store, AsyncMock(), AsyncMock(record=AsyncMock()),
                          health=AsyncMock(return_value=True), pause=AsyncMock())
        # Decision under 2s (rules only).
        receipt = {"product": "Autumbra", "role": "Watch"}
        stamp_budget(receipt, stage="event_to_decision", seconds=0.05)
        proposed = await room.propose(sh.ShieldRequest(
            site="coolify.tervory.com",
            kind="block_ip",
            address="203.0.113.200",
            reason="fixture attacking address",
            match_id="fixture-attack-1",
        ))
        proposed.update(settings.receipt_stamp())
        store.save_shield(PLATFORM_TENANT, proposed)
        stamp_budget(receipt, stage="decision_to_shield", seconds=0.2)
        raised = await room.raise_shield(proposed["id"])
        assert raised["state"] == "dry_run"
        stamp_budget(receipt, stage="health_check", seconds=0.1)
        undone = await room.undo(proposed["id"])
        assert undone["state"] == "withdrawn"
        # Client choice must remain on the receipt; Tervory never changes it.
        undone.update(settings.receipt_stamp())
        store.save_shield(PLATFORM_TENANT, undone)
        stamp_budget(receipt, stage="auto_undo_e2e", seconds=0.5)
        ok_b, fails = budgets_ok(receipt)
        assert ok_b, fails
        view = sh.public_view(undone)
        assert view["kind"] == "block_ip"
        assert view["address"] == "203.0.113.200"
        assert view["shield_mode"] == "I approve each one"
        assert view["fix_mode"] == "I approve each one"
        mail = build_owner_update(
            settings=settings,
            site_name="coolify.tervory.com",
            threats_found=1,
            critical=[{"stack": "PHP", "rating": "critical", "advisory_id": "CVE-2026-109618",
                       "advisory_url": "https://example.test/cve"}],
            shield={"blocked_addresses": 1, "source_name": "fixture", "source_url": "https://example.test"},
            pr_url="https://example.test/pr",
            receipt_url="https://protect.tervory.com/r/fixture",
            undo_shield_url="https://protect.tervory.com/undo/fixture",
        )
        assert "approve fixes yourself" in mail["body"]
        assert "Nothing from your logs was kept" in mail["body"]
        return receipt

    asyncio.run(run())
