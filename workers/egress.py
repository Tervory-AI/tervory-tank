"""What a task container is allowed to reach. Everything else is refused.

The same rules build the firewall the container installs before it clones or calls a model.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

GITHUB_HOSTS = (
    "github.com",
    "api.github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "uploads.github.com",
)
PYPI_HOSTS = ("pypi.org", "files.pythonhosted.org", "pypi.python.org")
NPM_HOSTS = ("registry.npmjs.org",)
HTTPS_HOSTS = frozenset({*GITHUB_HOSTS, *PYPI_HOSTS, *NPM_HOSTS})
PROXY_PORT = 8765


class EgressError(RuntimeError):
    pass


class HostRefused(EgressError):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(f"refusing {host}:{port}")
        self.host = host
        self.port = port


@dataclass(frozen=True)
class Policy:
    tank_host: str
    tank_port: int
    proxy_port: int = PROXY_PORT
    dns_servers: tuple[str, ...] = ("10.0.2.3",)

    def allows(self, host: str, port: int) -> bool:
        name = host.strip().lower().rstrip(".")
        if not name or port <= 0 or port > 65535:
            return False
        if name in {"127.0.0.1", "::1", "localhost"}:
            return port == self.proxy_port
        if name == self.tank_host.lower().rstrip("."):
            return port == self.tank_port
        if name in HTTPS_HOSTS:
            return port == 443
        try:
            address = ipaddress.ip_address(name)
        except ValueError:
            return False
        if address.is_loopback:
            return port == self.proxy_port
        if str(address) == self.tank_host:
            return port == self.tank_port
        return False

    def check(self, host: str, port: int) -> None:
        if not self.allows(host, port):
            raise HostRefused(host, port)


def nft_script(
    resolved: dict[str, list[str]],
    *,
    tank_host: str,
    tank_port: int,
    dns_servers: list[str],
) -> str:
    """Drop-by-default firewall. Only resolved allow-list addresses are accepted."""
    https_ips: list[str] = []
    https_ip6: list[str] = []
    for host, addresses in resolved.items():
        if host not in HTTPS_HOSTS:
            raise EgressError(f"refusing to open {host}")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_unspecified:
                raise EgressError("a public host resolved to a private address")
            bucket = https_ip6 if ip.version == 6 else https_ips
            rendered = str(ip)
            if rendered not in bucket:
                bucket.append(rendered)
    if not https_ips and not https_ip6:
        raise EgressError("no allow-list addresses; refusing to open the network")
    tank_ip = ipaddress.ip_address(tank_host)
    if tank_ip.is_global or tank_ip.is_multicast or tank_ip.is_unspecified:
        raise EgressError("Tank address must stay private")
    dns: list[str] = []
    for server in dns_servers:
        ip = ipaddress.ip_address(server)
        if ip.is_global:
            raise EgressError("DNS resolver must be the container resolver, not a public resolver")
        dns.append(str(ip))
    if not dns:
        raise EgressError("DNS resolver is required")
    lines = [
        "table inet tervory_worker {",
        "  chain output {",
        "    type filter hook output priority 0; policy drop;",
        "    ct state established,related accept",
        "    oif lo accept",
        f"    udp dport 53 ip daddr {{ {', '.join(dns)} }} accept",
    ]
    if https_ips:
        lines.append(f"    tcp dport 443 ip daddr {{ {', '.join(https_ips)} }} accept")
    if https_ip6:
        lines.append(f"    tcp dport 443 ip6 daddr {{ {', '.join(https_ip6)} }} accept")
    tank_match = "ip6" if tank_ip.version == 6 else "ip"
    lines.append(f"    tcp dport {int(tank_port)} {tank_match} daddr {tank_ip} accept")
    lines.append("  }")
    lines.append("}")
    script = "\n".join(lines) + "\n"
    if "0.0.0.0/0" in script or "accept" not in script or "policy drop" not in script:
        raise EgressError("firewall script is not fail-closed")
    return script
