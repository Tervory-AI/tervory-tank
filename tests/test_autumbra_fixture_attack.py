"""Fixture attack on Watch dry-run path: measured budgets, one-tap undo, receipt stamped."""
from __future__ import annotations

import asyncio
import time
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
        owner_email="owner-fixture@example.test",
    ))
    raw_log = "2026-10-26T12:00:01Z src=203.0.113.200 path=/admin scanner=nuclei"
    ok, why = may_block_ip("203.0.113.200", raw_log=raw_log)
    assert ok and why == "ok"

    async def run():
        room = sh.Shields(store, AsyncMock(), AsyncMock(record=AsyncMock()),
                          health=AsyncMock(return_value=True), pause=AsyncMock())
        receipt = {"product": "Autumbra", "role": "Watch"}
        t0 = time.perf_counter()
        proposed = await room.propose(sh.ShieldRequest(
            site="coolify.tervory.com",
            kind="block_ip",
            address="203.0.113.200",
            reason="fixture attacking address",
            match_id="fixture-attack-1",
        ))
        stamp_budget(receipt, stage="event_to_decision", seconds=time.perf_counter() - t0)
        proposed.update(settings.receipt_stamp())
        store.save_shield(PLATFORM_TENANT, proposed)
        t1 = time.perf_counter()
        raised = await room.raise_shield(proposed["id"])
        stamp_budget(receipt, stage="decision_to_shield", seconds=time.perf_counter() - t1)
        assert raised["state"] == "dry_run"
        t2 = time.perf_counter()
        # Watch dry-run health is the shield health callback.
        assert await room.health() is True
        stamp_budget(receipt, stage="health_check", seconds=time.perf_counter() - t2)
        t3 = time.perf_counter()
        undone = await room.undo(proposed["id"])
        stamp_budget(receipt, stage="auto_undo_e2e", seconds=time.perf_counter() - t3)
        assert undone["state"] == "withdrawn"
        undone.update(settings.receipt_stamp())
        store.save_shield(PLATFORM_TENANT, undone)
        ok_b, fails = budgets_ok(receipt)
        assert ok_b, fails
        # Measured from perf_counter — not caller-supplied constants.
        for stage in ("event_to_decision", "decision_to_shield", "health_check", "auto_undo_e2e"):
            assert receipt["budgets"][stage]["seconds"] >= 0.0
            assert receipt["budgets"][stage]["seconds"] != 0.05
        view = sh.public_view(undone)
        assert view["kind"] == "block_ip"
        assert view["address"] == "203.0.113.200"
        assert view["shield_mode"] == "I approve each one"
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
        assert "It was part of a widely reported campaign" in mail["body"]
        assert "(Each linked to its public advisory.)" in mail["body"]
        assert "[" not in mail["body"]
        assert "Nothing from your logs was kept" in mail["body"]
        return receipt

    asyncio.run(run())
