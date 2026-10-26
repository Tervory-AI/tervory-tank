"""ThreatPayload queue between Autumbra Watch and Enforce.

Watch writes validated ThreatPayload objects only. Enforce reads the queue,
applies under the action cap, runs the health check, auto-undoes on a failed
health check, and writes the receipt. No raw logs cross this door.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .client_settings import ClientAutumbraSettings
from .enforce_apply import apply_from_payload
from .fixture_edge import DEFAULT_CONTROL, FixtureEdgeControl
from .never_block import ActionCap, may_block_ip
from .speed_budgets import stamp_budget
from .threat_payload import ThreatPayload, accept_threat_payload


def queue_root_from_env() -> Path:
    raw = (os.environ.get("THREAT_PAYLOAD_QUEUE") or "").strip()
    if not raw:
        raise RuntimeError("THREAT_PAYLOAD_QUEUE is not configured.")
    return Path(raw)


class ThreatPayloadQueue:
    """Directory queue: one JSON file per ThreatPayload (fields only)."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "inbox").mkdir(exist_ok=True)
        (self.root / "receipts").mkdir(exist_ok=True)

    def put(self, payload: ThreatPayload) -> str:
        if not isinstance(payload, ThreatPayload):
            raise TypeError("Queue accepts ThreatPayload only.")
        item_id = uuid.uuid4().hex
        path = self.root / "inbox" / f"{item_id}.json"
        # Persist fields only — never raw logs.
        path.write_text(json.dumps(payload.model_dump(mode="json"), sort_keys=True), encoding="utf-8")
        return item_id

    def take(self) -> tuple[str, ThreatPayload] | None:
        inbox = self.root / "inbox"
        files = sorted(inbox.glob("*.json"))
        if not files:
            return None
        path = files[0]
        item_id = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = ThreatPayload.model_validate(data)
        path.unlink(missing_ok=True)
        return item_id, payload

    def write_receipt(self, receipt: dict[str, Any]) -> Path:
        rid = str(receipt.get("id") or uuid.uuid4())
        path = self.root / "receipts" / f"{rid}.json"
        path.write_text(json.dumps(receipt, sort_keys=True, default=str), encoding="utf-8")
        return path

    def list_receipts(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted((self.root / "receipts").glob("*.json")):
            out.append(json.loads(path.read_text(encoding="utf-8")))
        return out


def watch_enqueue_fixture_attack(
    *,
    queue: ThreatPayloadQueue,
    raw_log: str,
    site: str,
    address: str,
    reason: str = "fixture attacking address",
) -> dict[str, Any]:
    """Watch side: rules-first check on dirty log, then enqueue ThreatPayload only.

    Does not call Enforce. Returns a Watch receipt with measured decision budget.
    """
    t0 = time.perf_counter()
    ok, why = may_block_ip(address, raw_log=raw_log)
    if not ok:
        receipt = {
            "product": "Autumbra",
            "role": "Watch",
            "outcome": "refused",
            "note": why,
            "queued": False,
        }
        stamp_budget(receipt, stage="event_to_decision", seconds=time.perf_counter() - t0)
        return receipt
    payload = accept_threat_payload({
        "schema_version": "ghost.threat.v1",
        "action": "propose_shield",
        "site": site,
        "kind": "block_ip",
        "address": address,
        "severity": "critical",
        "reason": reason[:300],
        "confidence": 0.95,
        "cve_ids": ["CVE-2026-109618"],
    })
    item_id = queue.put(payload)
    receipt = {
        "product": "Autumbra",
        "role": "Watch",
        "outcome": "queued",
        "queued": True,
        "queue_item_id": item_id,
        "threat_fields": sorted(payload.model_dump().keys()),
        "raw_log_kept": False,
    }
    stamp_budget(receipt, stage="event_to_decision", seconds=time.perf_counter() - t0)
    return receipt


def enforce_drain_once(
    queue: ThreatPayloadQueue,
    *,
    settings: ClientAutumbraSettings,
    control: FixtureEdgeControl | None = None,
    action_cap: ActionCap | None = None,
    source_credits: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Enforce worker: read one ThreatPayload, apply under cap, health, auto-undo on fail."""
    taken = queue.take()
    if taken is None:
        return None
    _item_id, payload = taken
    edge = control or DEFAULT_CONTROL
    cap = action_cap or ActionCap()
    allowed, cap_why = cap.allow(settings.tenant_id)
    if not allowed:
        receipt = {
            "product": "Autumbra",
            "role": "Enforce",
            "outcome": "refused_action_cap",
            "note": cap_why,
            "applied": False,
            "raw_log_seen": False,
            **settings.receipt_stamp(),
        }
        queue.write_receipt(receipt)
        return receipt

    receipt = apply_from_payload(
        payload, settings=settings, control=edge, source_credits=source_credits
    )
    queue.write_receipt(receipt)
    return receipt


def run_pipe_fixture_attack(
    *,
    queue: ThreatPayloadQueue,
    settings: ClientAutumbraSettings,
    raw_log: str,
    site: str,
    address: str,
    control: FixtureEdgeControl | None = None,
    action_cap: ActionCap | None = None,
) -> dict[str, Any]:
    """One fixture attack: Watch → queue → Enforce → shield → health → receipt.

    Callers must not invoke apply_from_payload directly; this is the product path.
    """
    watch = watch_enqueue_fixture_attack(
        queue=queue, raw_log=raw_log, site=site, address=address
    )
    if not watch.get("queued"):
        return {"watch": watch, "enforce": None}
    enforce = enforce_drain_once(
        queue, settings=settings, control=control, action_cap=action_cap
    )
    return {"watch": watch, "enforce": enforce}
