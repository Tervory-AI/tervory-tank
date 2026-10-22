"""Install the task firewall. If this fails, the task does not clone or call a model."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from workers.egress import HTTPS_HOSTS, EgressError, nft_script
from workers.redact import redact
from workers.settings import validate_tank_url

NFT = "/usr/sbin/nft"


def resolve(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    found: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in found:
            found.append(address)
    return found


def dns_servers() -> list[str]:
    raw = os.environ.get("WORKER_DNS", "").strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    servers: list[str] = []
    try:
        text = Path("/etc/resolv.conf").read_text(encoding="utf-8")
    except OSError:
        return ["10.0.2.3"]
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "nameserver" and len(parts) > 1:
            servers.append(parts[1])
    return servers or ["10.0.2.3"]


def build_from_env() -> str:
    link = os.environ.get("WORKER_LINK", "internal").strip() or "internal"
    tank_url = validate_tank_url(os.environ.get("TANK_URL", "").strip(), link)
    parsed = urlsplit(tank_url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    resolved = {name: resolve(name) for name in HTTPS_HOSTS}
    try:
        tank_ip = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][4][0]
    except socket.gaierror as exc:
        raise EgressError("Tank did not resolve on the private link") from exc
    return nft_script(resolved, tank_host=tank_ip, tank_port=port, dns_servers=dns_servers())


def apply(script: str, runner: list[str] | None = None) -> None:
    # Absolute path: the task env PATH has no sbin (nftables installs to /usr/sbin/nft).
    command = runner or [NFT, "-f", "-"]
    completed = subprocess.run(command, input=script.encode(), check=False)
    if completed.returncode != 0:
        raise EgressError("firewall install failed; the task will not run")


def main() -> int:
    try:
        apply(build_from_env())
    except (EgressError, OSError, ValueError) as exc:
        # Say why on stderr. Without this the task container exits 1 with no output at all.
        print(f"worker task: firewall not installed: {type(exc).__name__}: {redact(str(exc))[:300]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
