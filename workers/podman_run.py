"""One fresh rootless podman container per task. Thrown away at the end."""

from __future__ import annotations

import ipaddress
import re
import secrets

from workers.settings import Settings

TASK_IMAGE = "tervory-worker-task:1"
_NAME = re.compile(r"^tervory-worker-[0-9]+-[0-9a-f]{8}$")


def choose_runtime(info: dict[str, object] | None) -> str:
    """Use gVisor (runsc) when podman lists it. Otherwise the ordinary runtime."""
    if not isinstance(info, dict):
        return "runc"
    host = info.get("host")
    names: list[str] = []
    if isinstance(host, dict):
        for key in ("ociRuntimes", "runtimes"):
            runtimes = host.get(key)
            if isinstance(runtimes, dict):
                names.extend(str(name) for name in runtimes)
        current = host.get("ociRuntime")
        if isinstance(current, dict) and isinstance(current.get("name"), str):
            names.append(current["name"])
    for name in names:
        leaf = name.rsplit("/", 1)[-1]
        if leaf in {"runsc", "gvisor"} or "gvisor" in name:
            return "runsc" if leaf in {"runsc", "gvisor"} else name
    return "runc"


def container_name(issue: int) -> str:
    name = f"tervory-worker-{issue}-{secrets.token_hex(4)}"
    if not _NAME.fullmatch(name):
        raise RuntimeError("container name was rejected")
    return name


def task_argv(
    settings: Settings,
    *,
    name: str,
    runtime: str,
    secret_dir: str,
    brief: str,
    issue: int,
    branch: str,
    title: str,
    hosts: list[tuple[str, str]] | None = None,
) -> list[str]:
    if not _NAME.fullmatch(name):
        raise RuntimeError("container name was rejected")
    if runtime not in {"runc", "runsc", "crun"} and "runsc" not in runtime and "gvisor" not in runtime:
        raise RuntimeError("runtime was rejected")
    for forbidden in (secret_dir, brief, branch, title):
        if "\n" in forbidden or "\r" in forbidden or "\x00" in forbidden:
            raise RuntimeError("refusing a path with a newline")
    env = {
        "TANK_URL": settings.tank_url,
        "TANK_KEY_FILE": "/run/secrets/tank_key",
        "GITHUB_TOKEN_FILE": "/run/secrets/token",
        "WORKER_TENANT_ID": settings.tenant_id,
        "WORKER_TASK_TYPE": settings.task_type,
        "WORKER_LINK": settings.link,
        "WORKER_REPO": settings.repo,
        "WORKER_BRIEF": brief,
        "WORKER_ISSUE": str(issue),
        "WORKER_BRANCH": branch,
        "WORKER_TITLE": title[:200],
        "WORKER_PROXY_PORT": str(settings.proxy_port),
        "HOME": "/home/worker",
        "PYTHONPATH": "/opt/tervory",
        "PATH": "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin",
        "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENAI_API_BASE": f"http://127.0.0.1:{settings.proxy_port}/v1",
    }
    argv = [
        "podman",
        "run",
        "--rm",
        "--name",
        name,
        "--cpus",
        str(settings.task_cpus),
        "--memory",
        settings.task_memory,
        "--cap-drop",
        "ALL",
        "--cap-add",
        "NET_ADMIN",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "512",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=1g",
        "--tmpfs",
        "/work:rw,nosuid,nodev,size=3g",
        "--tmpfs",
        "/home/worker:rw,nosuid,nodev,size=256m",
        "--network",
        "slirp4netns:port_handler=slirp4netns",
        "--runtime",
        runtime,
    ]
    for host_name, address in hosts or []:
        ipaddress.ip_address(address)
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host_name):
            raise RuntimeError("host alias was rejected")
        argv.extend(["--add-host", f"{host_name}:{address}"])
    argv.extend(
        [
            "--mount",
            f"type=bind,src={secret_dir},dst=/run/secrets,ro",
            "--workdir",
            "/work",
        ]
    )
    for key, value in env.items():
        argv.extend(["--env", f"{key}={value}"])
    argv.extend([TASK_IMAGE])
    joined = " ".join(argv)
    network = argv[argv.index("--network") + 1]
    if network == "host" or "--privileged" in argv or "--network=host" in joined or "docker.sock" in joined:
        raise RuntimeError("task container is not sealed")
    return argv


def kill_argv(name: str) -> list[str]:
    if not _NAME.fullmatch(name):
        raise RuntimeError("container name was rejected")
    return ["podman", "kill", name]


def build_argv() -> list[str]:
    return [
        "podman",
        "build",
        "-t",
        TASK_IMAGE,
        "-f",
        "/opt/tervory/workers/task/Dockerfile",
        "/opt/tervory",
    ]
