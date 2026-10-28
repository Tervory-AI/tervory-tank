"""WORKERS-2: check in with Tank every minute and read the founder's workers pause.

Uses TANK_KEY_WORKERS. The pause fails closed: if Tank cannot say "not paused", the worker
takes no new task. Nothing secret is sent: the last error line is redacted first.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx

from workers.redact import redact
from workers.settings import Settings

log = logging.getLogger("workers")
HEARTBEAT_S = 60
MAX_ERROR = 300


def tank_key() -> str:
    path = os.environ.get("TANK_KEY_FILE")
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return os.environ.get("TANK_KEY_WORKERS", "").strip()


def deployed_commit(settings: Settings) -> str:
    """Written by workers/host/install.sh and the auto-updater next to the code."""
    try:
        value = (Path(settings.code_dir) / "COMMIT").read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "unknown"
    if 7 <= len(value) <= 40 and all(ch in "0123456789abcdef" for ch in value):
        return value
    return "unknown"


class LastError(logging.Handler):
    """Keeps the most recent warning or error line from the workers logger, redacted."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.line: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = " ".join(redact(record.getMessage()).split())
        except Exception:  # noqa: BLE001 - a log handler must never raise
            return
        self.line = text[:MAX_ERROR] or None


class TankControl:
    def __init__(self, settings: Settings, client: httpx.AsyncClient, *, worker: str = "boston") -> None:
        self.base = settings.tank_url.rstrip("/")
        self.settings = settings
        self.client = client
        self.worker = worker
        self.last_paused = True

    def _headers(self) -> dict[str, str]:
        return {"x-tank-key": tank_key()}

    async def _command(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self.client.request(
                method, f"{self.base}/v1/command/{path}", headers=self._headers(), timeout=30, **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError, OSError) as exc:
            # Do not include response bodies, headers, or private conversation text.
            raise RuntimeError(f"Tank build {method} failed ({type(exc).__name__})") from None

    async def next_build(self) -> dict[str, Any] | None:
        value = await self._command("GET", "builds/next")
        if value is not None and not isinstance(value, dict):
            raise RuntimeError("Tank build claim was not an object")
        return value

    async def build_progress(self, build_id: str, body: dict[str, Any]) -> None:
        await self._command("POST", f"builds/{build_id}/progress", json=body)

    async def build_followups(self, build_id: str, after: int) -> list[dict[str, Any]]:
        value = await self._command("GET", f"builds/{build_id}/followups", params={"after": after})
        if not isinstance(value, list):
            raise RuntimeError("Tank build follow-ups were not a list")
        return value

    async def paused(self) -> bool:
        """True unless Tank answers 200 with paused=false. Fails closed."""
        try:
            resp = await self.client.get(f"{self.base}/v1/workers/paused", headers=self._headers(), timeout=10)
            body: Any = resp.json() if resp.status_code == 200 else None
            paused = not (isinstance(body, dict) and body.get("paused") is False)
        except (httpx.HTTPError, ValueError, OSError):
            paused = True
        if paused and not self.last_paused:
            log.info("workers paused (or pause state unavailable): taking no new task")
        self.last_paused = paused
        return paused

    async def heartbeat(self, *, issue: int | None, last_error: str | None) -> bool:
        body = {
            "worker": self.worker,
            "state": "paused" if self.last_paused else "running",
            "issue": issue,
            "commit": deployed_commit(self.settings),
            "last_error": redact(last_error)[:MAX_ERROR] if last_error else None,
        }
        try:
            resp = await self.client.post(f"{self.base}/v1/workers/heartbeat", json=body, headers=self._headers(), timeout=10)
        except (httpx.HTTPError, OSError):
            return False
        return resp.status_code == 200
