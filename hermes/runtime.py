"""Production wiring. Imported by the server process, not by the unit tests."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("hermes")

_MODEL = "BAAI/bge-small-en-v1.5"


def connect_production() -> tuple[Any, Any]:
    """Open Qdrant and load the local embedding model.

    Retries Qdrant for a few seconds so a cold start can wait for it.
    The exception text is not logged: driver errors can echo a URL.
    """
    from qdrant_client import QdrantClient

    from hermes.embeddings import FastEmbedder
    from hermes.qdrant_store import QdrantStore

    embedder = FastEmbedder(os.environ.get("HERMES_EMBED_MODEL", _MODEL))
    embedder.load()
    api_key = os.environ.get("QDRANT_API_KEY", "").strip() or None
    # Same Docker network only. Never forward either region's vectors to an
    # alternate host, proxy or public service.
    url = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    if url != "http://qdrant:6333":
        raise RuntimeError("Qdrant must be on this box")
    client = QdrantClient(
        url=url,
        api_key=api_key,
        timeout=10,
        trust_env=False,
        follow_redirects=False,
    )
    last: type[BaseException] | None = None
    for attempt in range(10):
        try:
            client.get_collections()
        except Exception as exc:  # noqa: BLE001 — class name only, never the message
            last = type(exc)
            time.sleep(1)
            if attempt == 9:
                log.warning("qdrant not ready (%s)", last.__name__ if last else "error")
                raise RuntimeError("qdrant unreachable") from None
        else:
            from hermes.law_store import LawIndex
            store = QdrantStore(client, embedder.dim)
            store.law = LawIndex(client, embedder.dim, region=os.environ.get("TANK_REGION", ""))
            return store, embedder
    raise RuntimeError("qdrant unreachable")
