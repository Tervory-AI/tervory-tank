"""Workers on the Boston host: a dedicated user, rootless podman, Tank on host loopback only."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from workers.egress import nft_script
from workers.podman_run import (
    TASK_NETWORK,
    RuntimeMissing,
    build_argv,
    choose_runtime,
    task_argv,
    task_tank_url,
)
from workers.service import Launcher, podman_tail
from workers.settings import PLATFORM_TENANT, Settings, SettingsError, from_mapping, validate_tank_url

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "workers/host"


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


def _argv(**kwargs: object) -> list[str]:
    return task_argv(
        _settings(**kwargs),
        name="tervory-worker-7-abcd1234",
        runtime="crun",
        secret_dir="/run/user/1001/tervory-workers/tervory-worker-7-abcd1234",
        brief="docs/cursor/EXAMPLE.md",
        issue=7,
        branch="worker/EXAMPLE-7",
        title="Fix the line",
        hosts=[],
    )


def _never_unsealed(argv: list[str]) -> None:
    blob = " ".join(argv)
    assert "--privileged" not in blob
    assert "--network=host" not in blob
    assert "docker.sock" not in blob
    if "--network" in argv:
        assert argv[argv.index("--network") + 1] != "host"


# ---------- the task container ----------


def test_build_is_plain_rootless_podman_from_the_host_code_dir() -> None:
    argv = build_argv("/srv/tervory-workers/app")
    assert argv[:2] == ["podman", "build"]
    assert argv[-1] == "/srv/tervory-workers/app"
    assert "/srv/tervory-workers/app/workers/task/Dockerfile" in argv
    assert "--isolation=chroot" not in argv
    _never_unsealed(argv)


def test_run_is_sealed_with_per_task_limits_and_slirp4netns() -> None:
    argv = _argv()
    assert argv[:3] == ["podman", "run", "--rm"]
    _never_unsealed(argv)
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    # NET_ADMIN for the firewall; SETUID/SETGID so setpriv can drop to the task user.
    assert [argv[j + 1] for j, a in enumerate(argv) if a == "--cap-add"] == ["NET_ADMIN", "SETUID", "SETGID"]
    assert "no-new-privileges" in argv
    assert "--read-only" in argv
    assert argv.count("--tmpfs") == 3
    assert argv[argv.index("--network") + 1] == TASK_NETWORK == "slirp4netns:allow_host_loopback=true"
    assert "--cgroups=disabled" not in argv
    assert argv[argv.index("--cpus") + 1] == "2"
    assert argv[argv.index("--memory") + 1] == "4g"
    assert argv[argv.index("--pids-limit") + 1] == "512"
    assert argv[argv.index("--runtime") + 1] == "crun"
    assert "--add-host" not in argv


def test_task_sees_tank_on_the_slirp_host_loopback() -> None:
    argv = _argv()
    assert "TANK_URL=http://10.0.2.2:8100" in argv
    assert "WORKER_LINK=loopback" in argv
    assert task_tank_url(_settings(link="internal", tank_url="http://tank:8000")) == "http://tank:8000"


def test_runtime_is_what_podman_reports_never_assumed_runc() -> None:
    assert choose_runtime({"host": {"ociRuntime": {"name": "crun", "path": "/usr/bin/crun"}}}) == "crun"
    assert choose_runtime({"host": {"ociRuntime": {"name": "/usr/bin/crun"}}}) == "crun"
    assert choose_runtime({"host": {"ociRuntimes": {"runsc": {}}, "ociRuntime": {"name": "crun"}}}) == "runsc"
    for info in (None, {}, {"host": {}}):
        with pytest.raises(RuntimeMissing):
            choose_runtime(info)  # type: ignore[arg-type]
    source = (ROOT / "workers/podman_run.py").read_text(encoding="utf-8")
    assert 'return "runc"' not in source


def test_loopback_link_accepts_only_loopback_tank() -> None:
    assert validate_tank_url("http://127.0.0.1:8100", "loopback")
    assert validate_tank_url("http://10.0.2.2:8100", "loopback")
    for bad in ("http://tank:8000", "http://8.8.8.8:8100", "https://127.0.0.1:8100", "http://127.0.0.1", "http://0.0.0.0:8100"):
        with pytest.raises(SettingsError):
            validate_tank_url(bad, "loopback")
    with pytest.raises(SettingsError):
        validate_tank_url("http://127.0.0.1:8100", "internal")
    settings = from_mapping({"WORKER_LINK": "loopback", "TANK_URL": "http://127.0.0.1:8100", "WORKER_PORT": "8110"})
    assert settings.tank_port == 8100 and settings.service_port == 8110
    assert settings.code_dir == "/srv/tervory-workers/app"
    with pytest.raises(SettingsError):
        from_mapping({"WORKER_CODE_DIR": "../etc"})


def test_task_firewall_opens_only_the_tank_port_on_host_loopback() -> None:
    script = nft_script(
        {"github.com": ["140.82.112.3"]},
        tank_host="10.0.2.2",
        tank_port=8100,
        dns_servers=["10.0.2.3"],
    )
    assert "tcp dport 8100 ip daddr 10.0.2.2 accept" in script
    assert "policy drop" in script
    assert script.count("10.0.2.2") == 1


def test_status_page_binds_loopback_only() -> None:
    source = (ROOT / "workers/service.py").read_text(encoding="utf-8")
    assert 'start_server(handle, "127.0.0.1"' in source
    assert '"0.0.0.0"' not in source


def test_task_user_is_not_uid_1000() -> None:
    text = (ROOT / "workers/task/Dockerfile").read_text(encoding="utf-8")
    assert "useradd --create-home --uid 1001" in text
    assert "--uid 1000" not in text


# ---------- error tail ----------


def test_podman_tail_is_redacted_and_short() -> None:
    fake = "ghs_" + "A" * 30
    lines = [f"line {n}" for n in range(40)] + [f"token {fake}"]
    tail = podman_tail("\n".join(lines))
    assert len(tail.splitlines()) == 20
    assert fake not in tail and "[redacted]" in tail
    assert podman_tail("") == "(no output)"


def test_build_failure_logs_podman_tail(caplog: pytest.LogCaptureFixture) -> None:
    async def runner(argv: list[str], *, timeout_s: int, kill: list[str] | None = None) -> tuple[int, str]:
        return 125, 'STEP 3/9\nError: building at STEP "RUN useradd": exit status 4'

    launcher = Launcher(runner)  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING, logger="workers"):
        with pytest.raises(RuntimeError, match="task image build failed"):
            asyncio.run(launcher.run(_settings(), object(), "t"))  # type: ignore[arg-type]
    assert "exit status 4" in caplog.text


def test_podman_info_failure_stops_the_task(caplog: pytest.LogCaptureFixture) -> None:
    async def runner(argv: list[str], *, timeout_s: int, kill: list[str] | None = None) -> tuple[int, str]:
        if argv[1] == "build":
            return 0, ""
        return 125, "Error: cannot set up namespace"

    launcher = Launcher(runner)  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING, logger="workers"):
        with pytest.raises(RuntimeError, match="podman info failed"):
            asyncio.run(launcher.run(_settings(), object(), "t"))  # type: ignore[arg-type]
    assert "cannot set up namespace" in caplog.text


# ---------- compose: Tank on host loopback only ----------


def test_compose_binds_tank_only_on_host_loopback() -> None:
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert data["services"]["tank"]["ports"] == ["127.0.0.1:8100:8000"]
    for name, service in data["services"].items():
        for port in service.get("ports") or []:
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port}"
    assert "workers" not in data["services"]
    assert not (ROOT / "docker-compose.workers.yml").exists()


# ---------- the host install ----------

SECRET_LOOKING = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{10,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b[0-9a-f]{32,}\b"),
    re.compile(r"(?i)\b[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD)[A-Z_]*=(?!$|/etc/tervory-workers/)[^\s$\"'(]+", re.M),
]


@pytest.mark.parametrize("name", ["install.sh", "tervory-workers.service", "worker.env.example"])
def test_host_files_hold_no_secret(name: str) -> None:
    text = (HOST / name).read_text(encoding="utf-8")
    for pattern in SECRET_LOOKING:
        assert not pattern.search(text), f"{name} matches {pattern.pattern}"


def test_env_template_leaves_every_secret_empty() -> None:
    lines = dict(
        line.split("=", 1)
        for line in (HOST / "worker.env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    for name in ("GITHUB_APP_ID", "GITHUB_APP_INSTALLATION_ID", "TANK_KEY_WORKERS"):
        assert lines[name] == ""
    assert "GITHUB_APP_PRIVATE_KEY" not in lines
    assert lines["GITHUB_APP_PRIVATE_KEY_FILE"] == "/etc/tervory-workers/github-app.pem"
    assert lines["TANK_URL"] == "http://127.0.0.1:8100"
    assert lines["WORKER_LINK"] == "loopback"
    from_mapping(lines)


def test_user_unit_matches_the_tngo_preview_pattern() -> None:
    unit = (HOST / "tervory-workers.service").read_text(encoding="utf-8")
    for line in (
        "WantedBy=default.target",
        "Restart=on-failure",
        "NoNewPrivileges=yes",
        "UMask=0077",
        "EnvironmentFile=/etc/tervory-workers/worker.env",
        "ExecStart=/srv/tervory-workers/venv/bin/python -m workers.service",
        "Environment=WORKER_STATE_DIR=%t/tervory-workers",
        "ExecStartPre=+/usr/bin/podman unshare /bin/true",
    ):
        assert line in unit.splitlines()
    assert "User=" not in unit


def test_install_script_shape() -> None:
    text = (HOST / "install.sh").read_text(encoding="utf-8")
    subprocess.run(["bash", "-n", str(HOST / "install.sh")], check=True)
    assert "loginctl enable-linger" in text
    assert "usermod --add-subuids" in text
    assert "apt-get install -s" in text
    assert "podman-docker" in text and "containerd" in text
    assert "NEEDRESTART_MODE=l" in text
    assert "-m 0640" in text and 'root:"$WORKER_USER"' in text
    assert "-m 0750" in text
    for forbidden in ("usermod -aG", "usermod -a -G", "gpasswd", "adduser tervory-workers sudo", "systemctl restart docker"):
        assert forbidden not in text
    assert "apt-get install -y -q --no-install-recommends" in text


def test_next_free_subid_follows_existing_ranges(tmp_path: Path) -> None:
    subuid = tmp_path / "subuid"
    subgid = tmp_path / "subgid"
    subuid.write_text("ammosync:100000:65536\ntngo:165536:65536\n")
    subgid.write_text("ammosync:100000:65536\ntngo:165536:65536\n")
    script = f'source "{HOST / "install.sh"}"; next_free_subid "{subuid}" "{subgid}"'
    out = subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True).stdout.strip()
    assert out == "231072"
    clash = f'source "{HOST / "install.sh"}"; subid_overlaps 200000 65536 tervory-workers "{subuid}" "{subgid}" && echo overlap'
    assert subprocess.run(["bash", "-c", clash], capture_output=True, text=True).stdout.strip() == "overlap"
    free = f'source "{HOST / "install.sh"}"; subid_overlaps 231072 65536 tervory-workers "{subuid}" "{subgid}" || echo free'
    assert subprocess.run(["bash", "-c", free], capture_output=True, text=True).stdout.strip() == "free"


def test_unit_has_the_review_limits_and_nothing_that_breaks_rootless_podman() -> None:
    lines = (HOST / "tervory-workers.service").read_text(encoding="utf-8").splitlines()
    for line in ("MemoryMax=6G", "CPUQuota=300%", "TasksMax=2048", "LockPersonality=yes", "RestrictRealtime=yes", "SystemCallArchitectures=native"):
        assert line in lines
    for option in ("ProtectSystem=", "ProtectHome=", "PrivateTmp=", "PrivateUsers="):
        assert not any(line.startswith(option) for line in lines)


def test_install_never_runs_or_writes_as_root_inside_the_user_tree() -> None:
    text = (HOST / "install.sh").read_text(encoding="utf-8")
    body = text.split("deploy_code() {", 1)[1].split("\n}\n", 1)[0]
    # venv and pip run as the user; the code is unpacked by tar running as the user.
    assert 'as_user python3 -m venv "$VENV_DIR"' in body
    assert 'as_user "$VENV_DIR/bin/pip" install' in body
    assert "| as_user tar -C \"$stage\"" in body
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if "$VENV_DIR/bin/pip" in line or "python3 -m venv" in line:
            assert "as_user" in line, line
        assert not line.startswith(("chown", "chmod", "cp ", "rm ", "mv ", "mkdir")), line
    assert "chown -R" not in body
    units = text.split("install_unit() {", 1)[1].split("\n}\n", 1)[0]
    assert 'as_user tee "$unit_dir/' in units and "install -o" not in units
    assert "python3 -I -" in text and "python3 - " not in text


def test_task_secrets_are_readable_by_the_task_user_only_through_a_0700_parent(tmp_path: Path) -> None:
    from workers.secrets_io import replace_token, stage

    parent = tmp_path / "state"
    parent.mkdir(mode=0o700)
    directory = parent / "task-1"
    stage(directory, token="ghs_" + "A" * 36, tank_key="tank-key-example")
    assert oct(directory.stat().st_mode & 0o777) == oct(0o711)
    for name in ("token",):
        assert oct((directory / name).stat().st_mode & 0o777) == oct(0o444)
    replace_token(directory, "ghs_" + "B" * 36)
    assert (directory / "token").read_text(encoding="utf-8") == "ghs_" + "B" * 36
    assert oct((directory / "token").stat().st_mode & 0o777) == oct(0o444)
    assert oct(parent.stat().st_mode & 0o777) == oct(0o700)
    assert not (ROOT / "workers/Dockerfile").exists()
