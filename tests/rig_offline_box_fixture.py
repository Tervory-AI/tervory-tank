"""Rig offline box (gates 7+8): local model rung, local data, sync queue.

When the network is off the whole shopper journey still runs against local
catalogue data and a local model stub (Tank local rung stand-in). Mutations
queue locally and sync when online again.
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable


LOCAL_RUNG = "local"
LOCAL_MODEL = "offline-local"
FIXED_LOCAL_COST = {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "rung": LOCAL_RUNG, "model": LOCAL_MODEL}


@dataclass
class SyncQueue:
    """Local queue of mutations; flush when the network returns."""

    pending: list[dict[str, Any]] = field(default_factory=list)
    synced: list[dict[str, Any]] = field(default_factory=list)

    def enqueue(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = {"id": f"q-{len(self.pending) + len(self.synced) + 1}", "kind": kind, "payload": deepcopy(payload), "ts": time.time()}
        self.pending.append(item)
        return item

    def flush(self, sender: Callable[[dict[str, Any]], Any] | None = None) -> list[dict[str, Any]]:
        moved: list[dict[str, Any]] = []
        while self.pending:
            item = self.pending.pop(0)
            if sender is not None:
                sender(item)
            self.synced.append(item)
            moved.append(item)
        return moved

    def __len__(self) -> int:
        return len(self.pending)


@dataclass
class OfflineBox:
    """In-process offline shop: local catalogue, local model, sync queue."""

    catalogue: dict[str, dict[str, Any]]
    queue: SyncQueue = field(default_factory=SyncQueue)
    online: bool = False
    model_calls: int = 0

    def set_online(self, value: bool) -> None:
        self.online = bool(value)
        if self.online and self.queue.pending:
            self.queue.flush()

    def search(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").lower()
        hits = []
        for row in self.catalogue.values():
            hay = " ".join(str(row.get(k, "")) for k in ("name", "brand", "sku", "id")).lower()
            if not q or q in hay:
                hits.append(deepcopy(row))
        return hits

    def product(self, product_id: str) -> dict[str, Any] | None:
        row = self.catalogue.get(str(product_id))
        return deepcopy(row) if row else None

    def ask(self, product_id: str, question: str) -> dict[str, Any]:
        product = self.product(product_id)
        if product is None:
            return {"answer": "I don't know", "cites": [], **FIXED_LOCAL_COST}
        self.model_calls += 1
        # Local rung: no network; grounded from local catalogue only.
        answer = f"{product.get('name', product_id)} — local: {question.strip() or 'ok'}"
        return {
            "answer": answer,
            "cites": [str(product.get("id") or product_id)],
            "content": answer,
            **FIXED_LOCAL_COST,
            "local_rung": True,
            "network": "off" if not self.online else "on",
        }

    def quote(self, product_id: str, note: str) -> dict[str, Any]:
        product = self.product(product_id)
        if product is None:
            raise KeyError(product_id)
        payload = {"product_id": product_id, "note": note, "sku": product.get("sku")}
        if self.online:
            return {"status": "sent", "payload": payload, "queued": False}
        item = self.queue.enqueue("quote", payload)
        return {"status": "queued", "queue_id": item["id"], "payload": payload, "queued": True}

    def journey(self, *, query: str, product_id: str, question: str, note: str) -> dict[str, Any]:
        """Whole shopper journey offline: search → product → ask → quote."""
        hits = self.search(query)
        product = self.product(product_id)
        asked = self.ask(product_id, question)
        quoted = self.quote(product_id, note)
        return {
            "search_count": len(hits),
            "product": product,
            "ask": asked,
            "quote": quoted,
            "online": self.online,
            "pending_sync": len(self.queue),
            "model_calls": self.model_calls,
        }


def demo_catalogue() -> dict[str, dict[str, Any]]:
    return {
        "STI-P-9": {
            "id": "STI-P-9",
            "sku": "STI-P-9",
            "name": "LumaWorks Pistol",
            "brand": "LumaWorks",
            "price": "899.00",
            "currency": "USD",
        },
        "LW-OPTIC": {
            "id": "LW-OPTIC",
            "sku": "LW-OPTIC",
            "name": "LumaWorks Optic",
            "brand": "LumaWorks",
            "price": "249.00",
            "currency": "USD",
        },
    }
