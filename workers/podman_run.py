"""One fresh rootless podman container per task. Thrown away at the end."""

from __future__ import annotations

import ipaddress
import re
import secrets
from urllib.parse import urlsplit, urlunsplit

from workers.settings import Settings

TASK_IMAGE = "tervory-worker-task:1"
# workers/host/install.sh and the auto-updater put the code here. Owned by tervory-workers;
# task containers never mount it.
DEFAULT_CODE_DIR = "/srv/tervory-workers/app"
_NAME = re.compile(r"^tervory-worker-[0-9]+-[0-9a-f]{8}$")


class RuntimeMissing(RuntimeError):
    pass


def choose_runtime(info: dict[str, object] | None) -> str:
    """Use the runtime podman actually reports. Prefer gVisor (runsc) when podman lists it.

    Never assume runc: Ubuntu's podman uses crun, and runc may not be installed at all.
    """
    if not isinstance(info, dict):
        raise RuntimeMissing("podman info did not describe a runtime")
    host = info.get("host")
    names: list[str] = []
    current_name = ""
    if isinstance(host, dict):
        for key in ("ociRuntimes", "runtimes"):
            runtimes = host.get(key)
            if isinstance(runtimes, dict):
                names.extend(str(name) for name in runtimes)
        current = host.get("ociRuntime")
        if isinstance(current, dict) and isinstance(current.get("name"), str):
            current_name = current["name"].strip()
            names.append(current_name)
    for name in names:
        leaf = name.rsplit("/", 1)[-1]
        if leaf in {"runsc", "gvisor"} or "gvisor" in name:
            return "runsc" if leaf in {"runsc", "gvisor"} else name
    if current_name:
        return current_name.rsplit("/", 1)[-1]
    raise RuntimeMissing("podman info did not name its OCI runtime")


# On the Boston host, slirp4netns maps the host's loopback to this address inside the task.
HOST_LOOPBACK = "10.0.2.2"
TASK_NETWORK = "slirp4netns:allow_host_loopback=true"
TASK_DNS = "10.0.2.3"  # slirp4netns built-in DNS forwarder


def task_tank_url(settings: Settings) -> str:
    """The Tank address as the task container sees it."""
    if settings.link != "loopback":
        return settings.tank_url
    parsed = urlsplit(settings.tank_url)
    return urlunsplit((parsed.scheme, f"{HOST_LOOPBACK}:{settings.tank_port}", "", "", ""))


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
        "TANK_URL": task_tank_url(settings),
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
        # Per-task limits. The systemd user session delegates cpu, memory and pids (cgroups v2).
        "--cpus",
        str(settings.task_cpus),
        "--memory",
        settings.task_memory,
        "--cap-drop",
        "ALL",
        # NET_ADMIN: container root installs the in-task firewall. SETUID/SETGID: the entrypoint's
        # setpriv then drops to the task user (UID 1001). Without them setresuid fails (EPERM).
        # Inside rootless podman these only reach the user namespace's own IDs, and after the drop
        # the task process has no capabilities (no-new-privileges, --inh-caps=-all).
        "--cap-add",
        "NET_ADMIN",
        "--cap-add",
        "SETUID",
        "--cap-add",
        "SETGID",
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
        TASK_NETWORK,
        # Only slirp4netns's own resolver. Podman otherwise also copies the host's upstream public
        # resolvers into the container, and the in-task firewall refuses public resolvers.
        "--dns",
        TASK_DNS,
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
    if not network.startswith("slirp4netns:") or "--privileged" in argv or "--network=host" in joined or "docker.sock" in joined:
        raise RuntimeError("task container is not sealed")
    if not sealed_privileges(argv):
        raise RuntimeError("task container is not sealed")
    return argv


SEALED_CAP_ADDS = frozenset({"NET_ADMIN", "SETUID", "SETGID"})


def _values(argv: list[str], flag: str) -> list[str]:
    """Every value given to a flag, as "--flag value" or "--flag=value"."""
    out: list[str] = []
    for i, arg in enumerate(argv):
        if arg == flag:
            out.append(argv[i + 1] if i + 1 < len(argv) else "")
        elif arg.startswith(flag + "="):
            out.append(arg[len(flag) + 1 :])
    return out


def sealed_privileges(argv: list[str]) -> bool:
    """Exactly --cap-drop ALL, cap-adds equal to {NET_ADMIN, SETUID, SETGID}, no-new-privileges, --read-only."""
    drops = _values(argv, "--cap-drop")
    adds = _values(argv, "--cap-add")
    return (
        drops == ["ALL"]
        and len(adds) == len(SEALED_CAP_ADDS)
        and set(adds) == SEALED_CAP_ADDS
        and "no-new-privileges" in _values(argv, "--security-opt")
        and argv.count("--read-only") == 1
        and not any(a.startswith("--read-only=") for a in argv)
    )


def kill_argv(name: str) -> list[str]:
    if not _NAME.fullmatch(name):
        raise RuntimeError("container name was rejected")
    return ["podman", "kill", name]


def build_argv(code_dir: str = DEFAULT_CODE_DIR) -> list[str]:
    root = code_dir.rstrip("/") or "/"
    argv = [
        "podman",
        "build",
        "-t",
        TASK_IMAGE,
        "-f",
        f"{root}/workers/task/Dockerfile",
        root,
    ]
    joined = " ".join(argv)
    if "--privileged" in joined or "docker.sock" in joined or "--network=host" in joined:
        raise RuntimeError("task build is not sealed")
    return argv
