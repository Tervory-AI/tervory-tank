"""The task container builds with chroot isolation and runs without cgroups, still sealed."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from workers.podman_run import build_argv, task_argv
from workers.service import Launcher, podman_tail
from workers.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        max_tasks=1,
        task_cpus=2,
        task_memory="4g",
        task_timeout_s=90 * 60,
        link="internal",
        tank_url="http://tank:8000",
        tenant_id="00000000-0000-0000-0000-000000000001",
        task_type="reason.brief",
        repo="Tervory-AI/tervory-tank",
        app_id="12345",
        installation_id="99",
    )


def _argv() -> list[str]:
    settings = _settings()
    return task_argv(
        settings,
        name="tervory-worker-7-abcd1234",
        runtime="runc",
        secret_dir="/var/lib/workers/tervory-worker-7-abcd1234",
        brief="docs/cursor/EXAMPLE.md",
        issue=7,
        branch="worker/EXAMPLE-7",
        title="Fix the line",
        hosts=[("tank", "10.0.1.8")],
    )


def _never_unsealed(argv: list[str]) -> None:
    blob = " ".join(argv)
    assert "--privileged" not in blob
    assert "--network=host" not in blob
    assert "docker.sock" not in blob
    if "--network" in argv:
        assert argv[argv.index("--network") + 1] != "host"


def test_build_uses_chroot_isolation() -> None:
    argv = build_argv()
    assert argv[:2] == ["podman", "build"]
    assert "--isolation=chroot" in argv
    _never_unsealed(argv)


def test_run_disables_cgroups_and_stays_sealed() -> None:
    argv = _argv()
    assert argv[:2] == ["podman", "run"]
    assert "--cgroups=disabled" in argv
    for flag in ("--cpus", "--memory", "--pids-limit"):
        assert flag not in argv
    _never_unsealed(argv)
    i = argv.index("--cap-drop")
    assert argv[i + 1] == "ALL"
    assert [argv[j + 1] for j, a in enumerate(argv) if a == "--cap-add"] == ["NET_ADMIN"]
    assert "no-new-privileges" in argv
    assert "--read-only" in argv
    assert argv[argv.index("--network") + 1] == "slirp4netns:port_handler=slirp4netns"
    assert argv.count("--tmpfs") == 3


def test_outer_container_carries_the_limits() -> None:
    text = (ROOT / "docker-compose.workers.yml").read_text(encoding="utf-8")
    assert "mem_limit: ${WORKER_SERVICE_MEMORY:-" in text
    assert "cpus: ${WORKER_SERVICE_CPUS:-" in text
    assert "pids_limit: 1024" in text
    assert "WORKER_TASK_TIMEOUT_MINUTES: ${WORKER_TASK_TIMEOUT_MINUTES:-90}" in text
    assert "privileged" not in text
    assert "docker.sock" not in text


def test_task_user_is_not_uid_1000() -> None:
    text = (ROOT / "workers/task/Dockerfile").read_text(encoding="utf-8")
    assert "useradd --create-home --uid 1001" in text
    assert "--uid 1000" not in text


def test_podman_tail_is_redacted_and_short() -> None:
    fake = "ghs_" + "A" * 30
    lines = [f"line {n}" for n in range(40)] + [f"token {fake}"]
    tail = podman_tail("\n".join(lines))
    assert len(tail.splitlines()) == 20
    assert fake not in tail and "[redacted]" in tail
    assert podman_tail("") == "(no output)"


def test_build_failure_logs_podman_tail(caplog: pytest.LogCaptureFixture) -> None:
    async def runner(argv: list[str], *, timeout_s: int, kill: list[str] | None = None) -> tuple[int, str]:
        return 125, "STEP 3/9\nError: building at STEP \"RUN useradd\": exit status 4"

    launcher = Launcher(runner)  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING, logger="workers"):
        with pytest.raises(RuntimeError, match="task image build failed"):
            asyncio.run(launcher.run(_settings(), object(), "t"))  # type: ignore[arg-type]
    assert "exit status 4" in caplog.text
