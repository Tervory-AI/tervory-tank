"""Start the real Tank, exactly as production does, against a real empty Postgres.

Several defects this week passed the whole suite because tests replaced Tank with a
stand-in: a route calling a Tank function that does not exist, and a skill package
whose eval cases made Tank crash on startup. This test runs `uvicorn main:app` from
tank/, waits for startup to finish, calls /health, then starts Tank a second time on
the same database (schema.sql must stay idempotent). Any startup exception fails CI.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
TANK = ROOT / "tank"


def _admin_url() -> str:
    for name in ("TANK_BOOT_DATABASE_URL", "POOL_SCHEMA_DATABASE_URL"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    if os.environ.get("GITHUB_ACTIONS"):
        pytest.fail("POOL_SCHEMA_DATABASE_URL is not set")
    pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    return ""


def _database_url(admin: str, name: str) -> str:
    parts = urlsplit(admin)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, "", ""))


async def _sql(admin: str, statement: str) -> None:
    conn = await asyncpg.connect(admin)
    try:
        await conn.execute(statement)
    finally:
        await conn.close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _boot(database_url: str) -> str:
    port = _free_port()
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "TANK_API_KEY": "ci-boot-check",
        "LITELLM_MASTER_KEY": "ci-boot-check",
        "LITELLM_URL": "http://127.0.0.1:9",
        "REDIS_URL": "redis://127.0.0.1:9/0",
        "PYTHONUNBUFFERED": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=TANK,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log: list[str] = []
    try:
        deadline = time.time() + 120
        healthy = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    healthy = response.status == 200
                if healthy:
                    break
            except Exception:  # noqa: BLE001 — still starting
                time.sleep(0.5)
        if not healthy:
            if proc.poll() is None:
                proc.terminate()
            out = proc.communicate(timeout=20)[0]
            pytest.fail("Tank did not start and answer /health:\n" + out[-6000:])
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                log.append(proc.communicate(timeout=20)[0])
            except subprocess.TimeoutExpired:
                proc.kill()
                log.append(proc.communicate()[0])
    output = "".join(log)
    assert "Application startup complete" in output, output[-6000:]
    assert "Traceback" not in output.split("Application startup complete")[0], output[-6000:]
    return output


def test_real_tank_starts_twice_on_an_empty_database() -> None:
    admin = _admin_url()
    name = "tank_boot_" + uuid4().hex[:12]
    asyncio.run(_sql(admin, f'CREATE DATABASE "{name}"'))
    try:
        url = _database_url(admin, name)
        _boot(url)  # first start: applies schema.sql to an empty database and loads every skill package
        _boot(url)  # second start: schema.sql must be idempotent
    finally:
        asyncio.run(_sql(admin, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
