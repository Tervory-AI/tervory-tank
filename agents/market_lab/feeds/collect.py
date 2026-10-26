"""Collect one licensed feed into an in-memory parser store.

The temporary store is never a serving database. The caller commits the checked
observations and an immutable source document to its tenant's Postgres ledger.
"""
from __future__ import annotations

import hashlib
import ipaddress
import urllib.request
from typing import Any
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from feeds.adapters import ADAPTERS
from feeds.db import apply_schema, connect
from feeds.fetch import fetch_source, watch_page
from feeds.keys import bind_key, missing_key, redact
from feeds.live import BlockedSite, PoliteClient, login_boundary
from feeds.reader import FixtureReader
from feeds.store import Store


def public_url(url: str) -> str:
    """Never persist credentials, query strings or fragments from a request."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("a public HTTPS source is required")
    if parts.port not in {None, 443} or parts.hostname in {"localhost", "metadata.google.internal"}:
        raise ValueError("a public HTTPS source is required")
    try:
        address = ipaddress.ip_address(parts.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("a public HTTPS source is required")
    return urlunsplit((parts.scheme, parts.hostname, parts.path, "", ""))


class EvidenceClient:
    """Read public pages, retain provenance, and stop at access boundaries."""

    def __init__(self, client: PoliteClient | None = None, *, allowed_domains: set[str] | None = None) -> None:
        self.allowed_domains = allowed_domains
        self.client = client or PoliteClient()
        if client is None:
            evidence = self
            class CheckedRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, request, fp, code, message, headers, newurl):
                    evidence._destination(newurl)
                    evidence._allowed(newurl)
                    if login_boundary(newurl):
                        raise BlockedSite(urlsplit(newurl).hostname or "")
                    evidence.client._wait(urlsplit(newurl).hostname or "")
                    return super().redirect_request(request, fp, code, message, headers, newurl)
            opener = urllib.request.build_opener(CheckedRedirect())
            self.client.opener = opener.open
        self.documents: list[dict] = []

    def _destination(self, url: str) -> str:
        clean = public_url(url)
        host = urlsplit(clean).hostname or ""
        if self.allowed_domains is not None and not any(host == domain or host.endswith("." + domain) for domain in self.allowed_domains):
            raise ValueError("download is outside the configured publishers")
        return clean

    def _allowed(self, url: str) -> None:
        self._destination(url)
        self.client.ensure_open(url)

    def get_text(self, url: str, headers: dict | None = None) -> str:
        return self.get(url, headers).decode("utf-8-sig", errors="replace")

    def get(self, url: str, headers: dict | None = None) -> bytes:
        self._allowed(url)
        body = self.client.get(url, headers=headers)
        self.documents.append({"url": public_url(url), "sha256": hashlib.sha256(body).hexdigest()})
        return body

    def iter_lines(self, url: str, headers: dict | None = None):
        self._allowed(url)
        digest = hashlib.sha256()
        for line in self.client.iter_lines(url, headers=headers):
            digest.update(line.encode("utf-8"))
            yield line
        self.documents.append({"url": public_url(url), "sha256": digest.hexdigest(), "encoding": "decoded lines"})


def collect(source: Any, *, fixtures: str | None, backfill: bool, client: EvidenceClient) -> dict:
    spec = bind_key(source)
    result = {"source_id": spec.id, "name": spec.name, "cadence": spec.cadence,
              "kind": "copy" if spec.allow_bulk else "linked", "licence": spec.licence,
              "terms_checked_at": spec.terms_checked_at, "url": public_url(spec.url),
              "points": [], "events": [], "downloads": [], "note": "", "fixture": bool(fixtures)}
    if not spec.enabled:
        return {**result, "note": "Off, disabled"}
    if not fixtures and missing_key(spec):
        return {**result, "note": "Off, needs key"}
    if not spec.allow_bulk and (fixtures or not spec.config.get("watch")):
        return {**result, "note": "Linked only; storage is not permitted"}
    conn = connect(":memory:")
    try:
        apply_schema(conn)
        store = Store(conn)
        store.upsert_source(spec)
        conn.commit()
        # Defer the batch decision to the tenant ledger, which has prior values.
        store.begin_batch("collect")
        client.documents = []
        if fixtures:
            ADAPTERS[spec.adapter](spec, FixtureReader([Path(fixtures)]), store, backfill=backfill)
        elif spec.allow_bulk:
            fetch_source(spec, client, store, backfill=backfill)
        else:
            watch_page(spec, client, store)
        meta = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM series")}
        result["points"] = [{**meta[point["series_id"]], **point} for point in store._staged]
        result["events"] = [dict(row) for row in conn.execute("SELECT * FROM events ORDER BY date, id")]
        result["downloads"] = list(client.documents)
    except BlockedSite:
        result.update(points=[], events=[], downloads=[], note="Off, blocked")
    except Exception:
        # Adapter exceptions can contain source data, URLs or credentials.
        result.update(points=[], events=[], downloads=[], note="Off, source could not be read")
    finally:
        conn.close()
    return _clean(result)


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    return value
