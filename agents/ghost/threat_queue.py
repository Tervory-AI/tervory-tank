"""ThreatPayload queue between Autumbra Watch and Enforce.

Watch writes validated ThreatPayload objects only. Enforce validates each item
before acting; a bad item is quarantined with a receipt and the queue keeps
flowing. No raw logs cross this door. No fixed CVE or severity is stamped —
severity comes only from a matched public advisory.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .client_settings import ClientAutumbraSettings
from .enforce_apply import apply_from_payload, approve_pending, undo_from_payload
from .fixture_edge import DEFAULT_CONTROL, FixtureEdgeControl
from .never_block import ActionCap, may_block_ip
from .speed_budgets import stamp_budget, utc_now
from .tenant_queue import push_receipt_to_founder_console
from .threat_payload import ThreatAction, ThreatPayload, ThreatSeverity, accept_threat_payload


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
        (self.root / "quarantine").mkdir(exist_ok=True)

    def put(self, payload: ThreatPayload) -> str:
        if not isinstance(payload, ThreatPayload):
            raise TypeError("Queue accepts ThreatPayload only.")
        item_id = uuid.uuid4().hex
        path = self.root / "inbox" / f"{item_id}.json"
        data = payload.model_dump(mode="json")
        if not data.get("queued_at"):
            data["queued_at"] = utc_now()
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        return item_id

    def take(self) -> tuple[str, ThreatPayload] | None:
        """Validate before acting. Bad items are quarantined with a receipt; keep flowing."""
        inbox = self.root / "inbox"
        while True:
            files = sorted(inbox.glob("*.json"))
            if not files:
                return None
            path = files[0]
            item_id = path.stem
            try:
                raw_text = path.read_text(encoding="utf-8")
                data = json.loads(raw_text)
                payload = ThreatPayload.model_validate(data)
            except Exception as exc:
                self._quarantine(path, item_id, reason=type(exc).__name__)
                continue
            path.unlink(missing_ok=True)
            return item_id, payload

    def _quarantine(self, path: Path, item_id: str, *, reason: str) -> None:
        dest = self.root / "quarantine" / f"{item_id}.json"
        try:
            shutil.move(str(path), str(dest))
        except OSError:
            path.unlink(missing_ok=True)
            dest = self.root / "quarantine" / f"{item_id}.missing.json"
            dest.write_text("{}", encoding="utf-8")
        receipt = {
            "id": str(uuid.uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "kind": "queue_quarantine",
            "outcome": "quarantined",
            "timestamp": utc_now(),
            "queue_item_id": item_id,
            "note": f"Invalid queue item quarantined ({reason}); queue kept flowing.",
            "applied": False,
            "raw_log_seen": False,
        }
        self.write_receipt(receipt)
        try:
            push_receipt_to_founder_console(self.root, receipt)
        except Exception:
            pass

    def write_receipt(self, receipt: dict[str, Any]) -> Path:
        if "timestamp" not in receipt:
            receipt["timestamp"] = utc_now()
        rid = str(receipt.get("id") or uuid.uuid4())
        path = self.root / "receipts" / f"{rid}.json"
        path.write_text(json.dumps(receipt, sort_keys=True, default=str), encoding="utf-8")
        try:
            push_receipt_to_founder_console(self.root, receipt)
        except Exception:
            pass
        return path

    def list_receipts(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted((self.root / "receipts").glob("*.json")):
            out.append(json.loads(path.read_text(encoding="utf-8")))
        return out

    def list_quarantine(self) -> list[str]:
        return sorted(p.name for p in (self.root / "quarantine").glob("*.json"))


def _advisory_fields(
    *,
    advisory: dict[str, Any] | None,
) -> dict[str, Any]:
    """Severity / CVE only from a matched public advisory. Never stamp fixed values."""
    if not advisory or not isinstance(advisory, dict):
        return {
            "severity": ThreatSeverity.unknown.value,
            "cve_ids": [],
            "confidence": 0.0,
            "advisory_url": None,
        }
    url = str(advisory.get("advisory_url") or advisory.get("url") or "").strip()
    rating = str(advisory.get("rating") or advisory.get("severity") or "").strip().lower()
    cve = str(advisory.get("advisory_id") or advisory.get("cve_id") or "").strip()
    cves: list[str] = []
    if cve.startswith("CVE-"):
        cves.append(cve)
    for extra in advisory.get("cve_ids") or []:
        if isinstance(extra, str) and extra.startswith("CVE-") and extra not in cves:
            cves.append(extra)
    if not url or not rating:
        # No matched public advisory → no severity stamp.
        return {
            "severity": ThreatSeverity.unknown.value,
            "cve_ids": [],
            "confidence": 0.0,
            "advisory_url": None,
        }
    try:
        sev = ThreatSeverity(rating).value
    except ValueError:
        sev = ThreatSeverity.unknown.value
    return {
        "severity": sev,
        "cve_ids": cves[:20],
        "confidence": float(advisory.get("confidence") or 0.85),
        "advisory_url": url,
    }


def watch_enqueue_fixture_attack(
    *,
    queue: ThreatPayloadQueue,
    raw_log: str,
    site: str,
    address: str,
    reason: str = "fixture attacking address",
    tenant_id: str | None = None,
    advisory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Watch side: rules-first check on dirty log, then enqueue ThreatPayload only.

    Does not call Enforce. Returns a Watch receipt with measured decision budget.
    Never stamps a fixed CVE or severity without a matched public advisory.
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
            "timestamp": utc_now(),
            "tenant_id": tenant_id,
        }
        stamp_budget(receipt, stage="event_to_decision", seconds=time.perf_counter() - t0)
        return receipt
    adv = _advisory_fields(advisory=advisory)
    payload_raw: dict[str, Any] = {
        "schema_version": "ghost.threat.v1",
        "action": "propose_shield",
        "site": site,
        "kind": "block_ip",
        "address": address,
        "severity": adv["severity"],
        "reason": reason[:300],
        "confidence": adv["confidence"],
        "cve_ids": adv["cve_ids"],
        "queued_at": utc_now(),
    }
    if tenant_id:
        payload_raw["tenant_id"] = tenant_id
    if adv.get("advisory_url"):
        payload_raw["advisory_url"] = adv["advisory_url"]
    payload = accept_threat_payload(payload_raw)
    item_id = queue.put(payload)
    receipt = {
        "product": "Autumbra",
        "role": "Watch",
        "outcome": "queued",
        "queued": True,
        "queue_item_id": item_id,
        "threat_fields": sorted(payload.model_dump().keys()),
        "raw_log_kept": False,
        "timestamp": utc_now(),
        "tenant_id": tenant_id,
        "severity": payload.severity.value,
        "cve_ids": list(payload.cve_ids),
        "advisory_url": payload.advisory_url,
    }
    stamp_budget(receipt, stage="event_to_decision", seconds=time.perf_counter() - t0)
    return receipt


def watch_enqueue_undo(
    *,
    queue: ThreatPayloadQueue,
    rule_id: str | None = None,
    prior_receipt_id: str | None = None,
    site: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Outside Enforce: undo travels as a validated ThreatPayload through the queue door."""
    payload = accept_threat_payload({
        "schema_version": "ghost.threat.v1",
        "action": ThreatAction.undo_shield.value,
        "site": site,
        "rule_id": rule_id or "",
        "prior_receipt_id": prior_receipt_id,
        "tenant_id": tenant_id,
        "reason": "client undo",
        "queued_at": utc_now(),
    })
    item_id = queue.put(payload)
    return {
        "product": "Autumbra",
        "role": "Watch",
        "outcome": "queued_undo",
        "queued": True,
        "queue_item_id": item_id,
        "timestamp": utc_now(),
        "tenant_id": tenant_id,
    }


def watch_enqueue_approve(
    *,
    queue: ThreatPayloadQueue,
    prior_receipt_id: str,
    site: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    payload = accept_threat_payload({
        "schema_version": "ghost.threat.v1",
        "action": ThreatAction.approve_shield.value,
        "site": site,
        "prior_receipt_id": prior_receipt_id,
        "tenant_id": tenant_id,
        "reason": "client approve",
        "queued_at": utc_now(),
    })
    item_id = queue.put(payload)
    return {
        "product": "Autumbra",
        "role": "Watch",
        "outcome": "queued_approve",
        "queued": True,
        "queue_item_id": item_id,
        "timestamp": utc_now(),
        "tenant_id": tenant_id,
    }


def _queue_transit_seconds(payload: ThreatPayload) -> float | None:
    if not payload.queued_at:
        return None
    try:
        # Support both ...Z and ...%fZ
        text = payload.queued_at.replace("Z", "+00:00")
        from datetime import datetime

        queued = datetime.fromisoformat(text)
        now = datetime.now(queued.tzinfo)
        return max(0.0, (now - queued).total_seconds())
    except Exception:
        return None


def enforce_drain_once(
    queue: ThreatPayloadQueue,
    *,
    settings: ClientAutumbraSettings,
    control: FixtureEdgeControl | None = None,
    action_cap: ActionCap | None = None,
    source_credits: list[dict[str, str]] | None = None,
    data_dir: Path | str | None = None,
    on_act_email: Any | None = None,
) -> dict[str, Any] | None:
    """Enforce worker: validate → act (apply/undo/approve) → receipt. Bad items already quarantined in take()."""
    t_drain = time.perf_counter()
    taken = queue.take()
    if taken is None:
        return None
    _item_id, payload = taken
    edge = control or DEFAULT_CONTROL
    cap = action_cap or ActionCap()

    transit = _queue_transit_seconds(payload)

    # Undo / approve doors — ThreatPayload only.
    if payload.action is ThreatAction.undo_shield:
        receipt = undo_from_payload(payload, control=edge, settings=settings, data_dir=data_dir)
        if transit is not None:
            stamp_budget(receipt, stage="queue_transit", seconds=transit)
        stamp_budget(receipt, stage="event_to_shield_e2e", seconds=time.perf_counter() - t_drain + (transit or 0))
        queue.write_receipt(receipt)
        return receipt

    if payload.action is ThreatAction.approve_shield:
        receipt = approve_pending(payload, control=edge, settings=settings, data_dir=data_dir)
        if transit is not None:
            stamp_budget(receipt, stage="queue_transit", seconds=transit)
        stamp_budget(receipt, stage="event_to_shield_e2e", seconds=time.perf_counter() - t_drain + (transit or 0))
        queue.write_receipt(receipt)
        if on_act_email and receipt.get("applied"):
            try:
                on_act_email(receipt, settings)
            except Exception:
                pass
        return receipt

    allowed, cap_why = cap.allow(settings.tenant_id)
    if not allowed:
        receipt = {
            "id": str(uuid.uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "outcome": "refused_action_cap",
            "note": cap_why,
            "applied": False,
            "raw_log_seen": False,
            "timestamp": utc_now(),
            "tenant_id": settings.tenant_id,
            **settings.receipt_stamp(),
        }
        if transit is not None:
            stamp_budget(receipt, stage="queue_transit", seconds=transit)
        queue.write_receipt(receipt)
        return receipt

    receipt = apply_from_payload(
        payload,
        settings=settings,
        control=edge,
        source_credits=source_credits,
        data_dir=data_dir,
    )
    if transit is not None:
        stamp_budget(receipt, stage="queue_transit", seconds=transit)
    # E2E: queue transit + drain work (event→shield across the pipe).
    e2e = time.perf_counter() - t_drain + (transit or 0.0)
    stamp_budget(receipt, stage="event_to_shield_e2e", seconds=e2e)
    queue.write_receipt(receipt)
    if on_act_email and receipt.get("applied"):
        try:
            on_act_email(receipt, settings)
        except Exception:
            pass
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
    advisory: dict[str, Any] | None = None,
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    """One fixture attack: Watch → queue → Enforce → shield → health → receipt.

    Callers must not invoke apply_from_payload directly; this is the product path.
    """
    watch = watch_enqueue_fixture_attack(
        queue=queue,
        raw_log=raw_log,
        site=site,
        address=address,
        tenant_id=settings.tenant_id,
        advisory=advisory,
    )
    if not watch.get("queued"):
        return {"watch": watch, "enforce": None}
    enforce = enforce_drain_once(
        queue,
        settings=settings,
        control=control,
        action_cap=action_cap,
        data_dir=data_dir,
    )
    return {"watch": watch, "enforce": enforce}
