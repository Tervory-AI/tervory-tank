"""Task 211: the task entrypoint exited 1 with no output, and the service retried it forever.

Covers the root cause (a secret file without a trailing newline made `read` fail under set -e),
stderr collection from the task container, and stopping after 3 failures in a row.
No network, no real tokens.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from workers import egress_apply
from workers.github_api import GitHub
from workers.issues import FAILED_LABEL, issue_from_api
from workers.secrets_io import stage
from workers.service import MAX_FAILURES, Launcher, Runner, Service, TaskFailed
from workers.settings import PLATFORM_TENANT, Settings

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "workers/task/entrypoint.sh"
TOKEN = "ghs_" + "B" * 36
TANK_KEY = "tank-key-example-value"


def _settings(**kwargs: object) -> Settings:
    base: dict[str, object] = dict(
        max_tasks=1,
        task_cpus=2,
        task_memory="4g",
        task_timeout_s=90 * 60,
        link="loopback",
        tank_url="http://127.0.0.1:8100",
        tenant_id=PLATFORM_TENANT,
        task_type="reason.brief",
        repo="Tervory-AI/tervory-tank",
        app_id="12345",
        installation_id="99",
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


# ---------- root cause: the entrypoint and a secret file with no trailing newline ----------


def _entrypoint_copy(tmp_path: Path, *, firewall_ok: bool = True) -> Path:
    """The real entrypoint, with the firewall step and the final exec swapped for test doubles."""
    text = ENTRYPOINT.read_text(encoding="utf-8")
    text = text.replace("/run/secrets/tank_key", str(tmp_path / "secrets/tank_key"))
    text = text.replace("python3 -m workers.egress_apply", "true" if firewall_ok else "false")
    text = text.replace(
        "exec setpriv --reuid=worker --regid=worker --init-groups --inh-caps=-all \\\n  python3 -m workers.task",
        'echo "started key_len=${#OPENAI_API_KEY}"',
    )
    assert "setpriv" not in text and "workers.egress_apply" not in text
    script = tmp_path / "entrypoint.sh"
    script.write_text(text, encoding="utf-8")
    return script


def test_entrypoint_starts_with_secret_files_as_the_service_writes_them(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets"
    stage(secrets, token=TOKEN, tank_key=TANK_KEY)
    assert not (secrets / "tank_key").read_bytes().endswith(b"\n")  # how secrets_io writes it
    done = subprocess.run(["sh", str(_entrypoint_copy(tmp_path))], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert f"started key_len={len(TANK_KEY)}" in done.stdout


def test_entrypoint_explains_an_empty_key_on_stderr(tmp_path: Path) -> None:
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets/tank_key").write_text("", encoding="utf-8")
    done = subprocess.run(["sh", str(_entrypoint_copy(tmp_path))], capture_output=True, text=True)
    assert done.returncode == 1
    assert "tank_key is empty or unreadable" in done.stderr


def test_entrypoint_explains_a_firewall_failure_on_stderr(tmp_path: Path) -> None:
    done = subprocess.run(["sh", str(_entrypoint_copy(tmp_path, firewall_ok=False))], capture_output=True, text=True)
    assert done.returncode == 1
    assert "firewall install failed" in done.stderr


def test_firewall_failure_says_why_on_stderr(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def broken() -> str:
        raise OSError("nft: Operation not permitted")

    monkeypatch.setattr(egress_apply, "build_from_env", broken)
    assert egress_apply.main() == 1
    assert "Operation not permitted" in capsys.readouterr().err


# ---------- stderr is collected ----------


def test_runner_keeps_stderr_apart_from_stdout() -> None:
    code, out, err = asyncio.run(
        Runner()([sys.executable, "-c", "import sys; print('out'); print('boom', file=sys.stderr); sys.exit(3)"], timeout_s=30)
    )
    assert (code, out.strip(), err.strip()) == (3, "out", "boom")


class _Task:
    number = 211
    brief = "docs/cursor/WORKER-0-first-run.md"
    branch = "worker/WORKER-0-first-run-211"
    title = "WORKER-0: first worker run"


def test_container_failure_logs_stderr_and_never_the_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def runner(argv: list[str], *, timeout_s: int, kill: list[str] | None = None) -> tuple[int, str, str]:
        if argv[1] == "info":
            return 0, '{"host": {"ociRuntime": {"name": "crun"}}}', ""
        return 1, "", f"worker task: something broke near {TANK_KEY} and {TOKEN}\n"

    monkeypatch.setenv("TANK_KEY_WORKERS", TANK_KEY)
    monkeypatch.delenv("TANK_KEY_FILE", raising=False)
    launcher = Launcher(runner)  # type: ignore[arg-type]
    launcher._built = True
    with caplog.at_level(logging.WARNING, logger="workers"):
        with pytest.raises(TaskFailed) as raised:
            asyncio.run(launcher.run(_settings(state_dir=str(tmp_path)), _Task(), TOKEN))  # type: ignore[arg-type]
    assert "something broke" in caplog.text and "(no output)" not in caplog.text.split("stderr lines:")[1].split("stdout")[0]
    assert "something broke" in raised.value.detail
    for text in (caplog.text, raised.value.detail):
        assert TANK_KEY not in text and TOKEN not in text
    assert list(tmp_path.iterdir()) == []


# ---------- three failures in a row stop the task ----------


class _Open:
    async def paused(self) -> bool:
        return False


class _FailingLauncher:
    def __init__(self, fail: bool = True) -> None:
        self.calls = 0
        self.fail = fail

    async def run(self, settings: Settings, task: object, token: str) -> object:
        self.calls += 1
        if self.fail:
            raise TaskFailed("the container failed", f"exit 1. stderr: run {self.calls} broke")
        from workers.task_run import Outcome

        return Outcome(status="draft", pr_url=None, minutes=1.0)


def _github(labels_status: int = 200) -> tuple[GitHub, list[tuple[str, str, dict]]]:
    seen: list[tuple[str, str, dict]] = []
    labelled: set[int] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        body = json.loads(request.read() or b"{}")
        seen.append((request.method, url, body))
        if "/issues?" in url and request.method == "GET":
            labels = [{"name": "worker"}] + ([{"name": FAILED_LABEL}] if 211 in labelled else [])
            return httpx.Response(
                200, json=[{"number": 211, "title": "WORKER-0", "body": "docs/cursor/WORKER-0-first-run.md", "labels": labels}]
            )
        if "/pulls?" in url:
            return httpx.Response(200, json=[])
        if url.endswith("/comments"):
            return httpx.Response(201, json={"id": 1})
        if url.endswith("/issues/211/labels") and request.method == "POST":
            if labels_status < 400:
                labelled.add(211)
            return httpx.Response(labels_status, json=[{"name": FAILED_LABEL}])
        return httpx.Response(404)

    return GitHub("Tervory-AI/tervory-tank", httpx.AsyncClient(transport=httpx.MockTransport(handler))), seen


def _service(github: GitHub, launcher: object) -> Service:
    service = Service(_settings(), github, launcher, _Open())  # type: ignore[arg-type]

    async def token() -> str:
        return TOKEN

    service._token = token  # type: ignore[method-assign]
    return service


async def _poll(service: Service) -> None:
    await service.poll_once(TOKEN)
    await asyncio.gather(*service.jobs)
    service.jobs.clear()


@pytest.mark.asyncio
async def test_three_failures_in_a_row_stop_retrying_and_mark_the_issue_failed() -> None:
    github, seen = _github()
    launcher = _FailingLauncher()
    service = _service(github, launcher)
    for _ in range(MAX_FAILURES + 2):
        await _poll(service)
    assert MAX_FAILURES == 3
    assert launcher.calls == 3
    record = service.records[0]
    assert record["status"] == "stopped" and record["failures"] == 3
    assert "run 3 broke" in record["error"]
    comments = [body["body"] for method, url, body in seen if method == "POST" and url.endswith("/comments")]
    assert len(comments) == 1
    assert "failed 3 times in a row" in comments[0] and "run 3 broke" in comments[0]
    assert TOKEN not in comments[0]
    labels = [body for method, url, body in seen if url.endswith("/issues/211/labels")]
    assert labels == [{"labels": [FAILED_LABEL]}]
    await github.client.aclose()


@pytest.mark.asyncio
async def test_two_failures_then_a_result_resets_the_count() -> None:
    github, seen = _github()
    launcher = _FailingLauncher()
    service = _service(github, launcher)
    await _poll(service)
    await _poll(service)
    assert service.records[0]["status"] == "failed" and service.records[0]["failures"] == 2
    launcher.fail = False
    await _poll(service)
    assert 211 not in service.failures
    launcher.fail = True
    await _poll(service)
    await _poll(service)
    assert service.records[0]["status"] == "failed"
    assert not any(url.endswith("/labels") for _, url, _ in seen)
    await github.client.aclose()


@pytest.mark.asyncio
async def test_a_task_reported_failure_counts_too() -> None:
    from workers.task_run import Outcome

    class _Reports:
        calls = 0

        async def run(self, settings: Settings, task: object, token: str) -> Outcome:
            self.calls += 1
            return Outcome(status="failed", detail="aider could not reach Tank")

    github, seen = _github()
    launcher = _Reports()
    service = _service(github, launcher)
    for _ in range(5):
        await _poll(service)
    assert launcher.calls == 3
    assert "aider could not reach Tank" in service.records[0]["error"]
    await github.client.aclose()


@pytest.mark.asyncio
async def test_stopped_in_process_even_when_github_refuses_the_label() -> None:
    github, _ = _github(labels_status=403)
    launcher = _FailingLauncher()
    service = _service(github, launcher)
    for _ in range(5):
        await _poll(service)
    assert launcher.calls == 3
    assert 211 in service.stopped
    await github.client.aclose()


def test_failed_label_takes_the_issue_off_the_queue() -> None:
    payload = {"number": 211, "title": "T", "body": "docs/cursor/WORKER-0-first-run.md", "labels": [{"name": "worker"}]}
    assert issue_from_api(payload) is not None
    payload["labels"] = [{"name": "worker"}, {"name": FAILED_LABEL}]
    assert issue_from_api(payload) is None
