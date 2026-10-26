"""WORKERS-1b: the worker key on Tank, the GitHub App key from settings, the Workers panel.

No database, no network, no real key. The PEM here is generated for the test.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import stat
import subprocess
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from starlette.requests import Request

import main
from workers import settings as worker_settings
from workers.github_app import (
    PrivateKeyRejected,
    private_key_from_setting,
    read_private_key,
    sign_app_jwt,
    write_private_key,
)
from workers.podman_run import container_name
from workers.settings import KEY_DIR, LEGACY_KEY_FILE, SettingsError, from_env, from_mapping

ROOT = Path(__file__).resolve().parents[1]
TANK_KEY_REF = re.compile(r"\$\{(TANK_KEY_[A-Z0-9_]+)")
# Built in two parts, like tests/test_secrets.py does, so the secrets scan does not read a fixture as a key.
RSA_BEGIN = "-----BEGIN RSA " + "PRIVATE KEY-----"
RSA_END = "-----END RSA " + "PRIVATE KEY-----"


# ---------- 1. Tank accepts the worker key ----------

def _compose_files() -> list[Path]:
    return sorted(ROOT.glob("docker-compose*.yml")) + sorted(ROOT.glob("agents/*/docker-compose*.yml"))


def _tank_env(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    env = data["services"]["tank"]["environment"]
    assert isinstance(env, dict)
    return {str(k): str(v) for k, v in env.items()}


def test_every_tank_key_in_any_compose_file_is_passed_to_tank() -> None:
    boston = _tank_env(ROOT / "docker-compose.yml")
    za = _tank_env(ROOT / "docker-compose.za.yml")
    seen: set[str] = set()
    for path in _compose_files():
        names = set(TANK_KEY_REF.findall(path.read_text(encoding="utf-8")))
        seen |= names
        tank_env = za if path.name.endswith(".za.yml") else boston
        for name in names:
            assert tank_env.get(name) == "${" + name + ":-}", f"{name} from {path.relative_to(ROOT)} is not passed to Tank"
    assert "TANK_KEY_WORKERS" in seen
    assert boston["TANK_KEY_WORKERS"] == "${TANK_KEY_WORKERS:-}"


def test_the_worker_key_is_one_line_next_to_the_other_agent_keys() -> None:
    lines = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if line.strip() == "TANK_KEY_WORKERS: ${TANK_KEY_WORKERS:-}"]
    assert len(hits) == 1
    assert lines[hits[0] - 1].strip().startswith("TANK_KEY_")


def _request(path: str, method: str = "POST") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [], "client": ("127.0.0.1", 1), "server": ("test", 80),
    }
    return Request(scope, receive)


def test_a_worker_key_set_on_tank_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    worker_key = "worker-key-for-tests-only"
    monkeypatch.setattr(main, "_pool", None)
    monkeypatch.setenv("TANK_KEY_WORKERS", worker_key)
    agent = asyncio.run(main.require_key(_request("/v1/route"), x_tank_key=worker_key))
    assert agent == "workers"
    with pytest.raises(HTTPException) as refused:
        asyncio.run(main.require_key(_request("/v1/workers", "GET"), x_tank_key=worker_key))
    assert refused.value.status_code == 403
    with pytest.raises(HTTPException) as wrong:
        asyncio.run(main.require_key(_request("/v1/route"), x_tank_key="not-the-worker-key"))
    assert wrong.value.status_code == 401
    monkeypatch.setenv("TANK_KEY_WORKERS", "")
    with pytest.raises(HTTPException):
        asyncio.run(main.require_key(_request("/v1/route"), x_tank_key=worker_key))


# ---------- 2. GitHub App key from the GITHUB_APP_PRIVATE_KEY setting ----------

def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _body(pem: str) -> str:
    return "".join(line for line in pem.splitlines() if "-----" not in line)


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {
        "GITHUB_APP_ID": "5378545",
        "GITHUB_APP_INSTALLATION_ID": "99",
        "WORKER_STATE_DIR": str(tmp_path / "state"),
    }
    env.update(extra)
    return env


def test_the_key_is_read_from_the_setting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pem = _pem()
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY_FILE", raising=False)
    for name, value in _env(tmp_path, GITHUB_APP_PRIVATE_KEY=pem).items():
        monkeypatch.setenv(name, value)
    caplog.set_level(logging.DEBUG)
    settings = from_env()
    assert settings.private_key_source == "setting"
    assert settings.github_ready
    key_file = Path(settings.private_key_file)
    assert key_file == tmp_path / "state" / KEY_DIR / "app-key.pem"
    assert key_file.is_file()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700
    assert read_private_key(str(key_file)) == private_key_from_setting(pem)
    assert sign_app_jwt("5378545", read_private_key(str(key_file))).count(".") == 2
    # Child processes do not inherit it, and it is in no log, no repr, no Settings field.
    assert "GITHUB_APP_PRIVATE_KEY" not in os.environ
    body = _body(pem)
    assert body[:40] not in caplog.text
    assert body[:40] not in repr(settings)
    assert all(body[:40] not in str(value) for value in vars(settings).values())


def test_coolify_value_forms_all_read_the_same(tmp_path: Path) -> None:
    pem = _pem()
    want = private_key_from_setting(pem)
    for form in (
        pem,
        pem.replace("\n", "\\n"),
        pem.replace("\n", "\r\n"),
        '"' + pem.strip() + '"',
        pem.replace("\n", " "),
        "\n  " + pem + "  \n",
    ):
        assert private_key_from_setting(form) == want
    assert want.startswith(RSA_BEGIN.encode() + b"\n")
    assert all(len(line) <= 64 for line in want.decode().splitlines())


def test_a_bad_setting_is_refused_without_echoing_it(tmp_path: Path) -> None:
    for bad in ("not a key", "-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----", "ghs_example"):
        with pytest.raises(SettingsError) as refused:
            from_mapping(_env(tmp_path, GITHUB_APP_PRIVATE_KEY=bad))
        assert bad not in str(refused.value)
        assert "GITHUB_APP_PRIVATE_KEY" in str(refused.value)
    with pytest.raises(PrivateKeyRejected):
        private_key_from_setting(f"{RSA_BEGIN}\n!!!!\n{RSA_END}")


def test_a_named_key_file_still_wins_and_no_setting_means_not_configured(tmp_path: Path) -> None:
    named = from_mapping(_env(tmp_path, GITHUB_APP_PRIVATE_KEY_FILE="/run/secrets/other", GITHUB_APP_PRIVATE_KEY="ignored"))
    assert (named.private_key_file, named.private_key_source) == ("/run/secrets/other", "file")
    unset = from_mapping(_env(tmp_path))
    assert (unset.private_key_file, unset.private_key_source) == (LEGACY_KEY_FILE, "file")
    assert not Path(unset.private_key_file).is_file()  # the service logs "not configured" and takes no task
    blank = from_mapping(_env(tmp_path, GITHUB_APP_PRIVATE_KEY_FILE="", GITHUB_APP_PRIVATE_KEY="  "))
    assert blank.private_key_source == "file"


def test_the_key_file_is_never_a_task_directory(tmp_path: Path) -> None:
    settings = from_mapping(_env(tmp_path, GITHUB_APP_PRIVATE_KEY=_pem()))
    key_dir = Path(settings.private_key_file).parent
    assert key_dir.name == KEY_DIR
    for issue in (1, 42, 99999):
        assert container_name(issue) != KEY_DIR
        assert not container_name(issue).startswith(".")


def test_write_refuses_a_symlinked_directory(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(PrivateKeyRejected):
        write_private_key(private_key_from_setting(_pem()), str(link / "app-key.pem"))
    assert not any(real.iterdir())


def test_workers_host_install_uses_a_key_file_outside_git() -> None:
    # The Docker workers app is retired. On the host the key is a root:tervory-workers 0640 file.
    assert not (ROOT / "docker-compose.workers.yml").exists()
    template = (ROOT / "workers/host/worker.env.example").read_text(encoding="utf-8")
    assert re.search(r"^GITHUB_APP_PRIVATE_KEY_FILE=/etc/tervory-workers/github-app.pem$", template, re.M)
    assert not re.search(r"^GITHUB_APP_PRIVATE_KEY=", template, re.M)
    assert "PRIVATE KEY-----" not in template
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PRIVATE KEY-----" not in example
    assert worker_settings.__doc__ and "GITHUB_APP_PRIVATE_KEY" in worker_settings.__doc__


# ---------- 3. The read-only Workers panel ----------

def test_tank_panel_reads_the_heartbeat_not_the_old_workers_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # WORKERS-2: GET /v1/workers no longer calls http://workers:8000; it reads tank.workers_heartbeat.
    import datetime as _dt

    import workers_status

    class Conn:
        def __init__(self, row):
            self.row = row

        def acquire(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def fetchrow(self, sql, *args):
            assert "tank.workers_heartbeat" in sql
            return self.row

    now = _dt.datetime.now(_dt.timezone.utc)
    live = {"worker": "boston", "state": "running", "issue": 211, "commit": "abc1234", "last_error": None, "seen_at": now}
    monkeypatch.setattr(workers_status, "db", lambda: Conn(live))
    assert asyncio.run(main.workers_panel()) == {
        "available": True,
        "tasks": [{"issue": 211, "brief": "", "status": "running", "pr_url": None, "minutes": None, "cost_usd": None}],
    }
    monkeypatch.setattr(workers_status, "db", lambda: Conn({**live, "issue": None}))
    assert asyncio.run(main.workers_panel()) == {"available": True, "tasks": []}
    stale = {**live, "seen_at": now - _dt.timedelta(minutes=4)}
    for row in (None, stale):
        monkeypatch.setattr(workers_status, "db", lambda row=row: Conn(row))
        assert asyncio.run(main.workers_panel()) == {"available": False, "tasks": []}

    def broken():
        raise RuntimeError("pool not ready")

    monkeypatch.setattr(workers_status, "db", broken)
    assert asyncio.run(main.workers_panel()) == {"available": False, "tasks": []}
    source = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    assert "WORKERS_URL" not in source and "workers:8000" not in source
    assert "WORKERS_URL" not in (ROOT / ".env.example").read_text(encoding="utf-8")


def test_the_workers_route_is_get_only_and_keyed() -> None:
    from http_routes import iter_http_routes

    routes = [r for r in iter_http_routes(main.app.routes) if r.path == "/v1/workers"]
    assert len(routes) == 1
    assert routes[0].methods == {"GET"}
    assert any(dep.call is main.require_key for dep in routes[0].dependant.dependencies)
    source = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    block = source.split('@app.get("/v1/workers"', 1)[1].split("\n\n\n", 1)[0]
    assert "pool()" not in block and "ledger" not in block.split('"""', 2)[2]


def test_the_tank_page_shows_the_panel_from_fixture_tasks() -> None:
    page_dir = ROOT / "workspace" / "app" / "tank"
    result = subprocess.run(
        [
            "node", "--experimental-strip-types", "--import", str(ROOT / "tests" / "market_lab_register.mjs"),
            "--test", str(page_dir / "workers.test.ts"),
        ],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    view = (page_dir / "view.tsx").read_text(encoding="utf-8")
    page = (page_dir / "page.tsx").read_text(encoding="utf-8")
    panel = (page_dir / "workers-panel.tsx").read_text(encoding="utf-8")
    server = (page_dir / "workers-server.ts").read_text(encoding="utf-8")
    assert "<WorkersPanel feed={workers} />" in view
    assert "listWorkers" in page and "process.env" not in page and "process.env" not in view
    assert server.startswith('import "server-only";')
    assert "/v1/workers" in server
    for label in ("Status", "Pull request", "Minutes", "Model cost"):
        assert label in panel
    for word in ("<button", "<form", "onClick", "method:"):
        assert word not in panel
