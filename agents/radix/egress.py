"""Egress proxy for the Radix room.

The only approved destination is lokd.co.za on port 443. The proxy resolves
that name, refuses any answer that is not a public address, and connects to
the one address from that lookup. It does not resolve again. TLS stays between
the caller and the site: this process tunnels bytes and does not change SNI.

A missing, invalid, or revoked policy refuses every tunnel. The process does
not read a proxy address or a resolver from the request.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

APPROVED_HOST = "lokd.co.za"
APPROVED_PORT = 443
ROOM_PROXY = "http://egress-proxy:8080"
BOUNDS = {
    "max_concurrent": 2,
    "max_requests_per_minute": 6,
    "max_response_bytes": 1_000_000,
    "max_duration_seconds": 20,
}
_POLICY_KEYS = {
    "version",
    "ownership",
    "destinations",
    "max_concurrent",
    "max_requests_per_minute",
    "max_response_bytes",
    "max_duration_seconds",
}
_BLOCKED_V4 = (
    "0.0.0.0/8",
    "100.64.0.0/10",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "240.0.0.0/4",
)
_BLOCKED_V6 = (ipaddress.ip_network("2001:db8::/32"),)


class PolicyError(Exception):
    """The egress policy is missing, invalid, or revoked."""


class ProxyError(Exception):
    """A tunnel was refused or the room proxy is unavailable."""


def routable(raw: str) -> bool:
    """True only for a public unicast address. Private and special ranges fail."""
    try:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if any((
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    )):
        return False
    if ip.version == 4:
        if any(ip in ipaddress.ip_network(item) for item in _BLOCKED_V4):
            return False
    elif any(ip in network for network in _BLOCKED_V6) or not getattr(ip, "is_global", False):
        return False
    return True


def load_policy(path: str | Path) -> None:
    """Accept only the baked policy. Anything else fails closed."""
    file = Path(path)
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError("egress policy refused") from exc
    if not isinstance(data, dict) or set(data) != _POLICY_KEYS:
        raise PolicyError("egress policy refused")
    if data["version"] != 1 or data["ownership"] != "approved":
        raise PolicyError("egress policy refused")
    if data["destinations"] != [{"host": APPROVED_HOST, "port": APPROVED_PORT}]:
        raise PolicyError("egress policy refused")
    for key, value in BOUNDS.items():
        if data[key] != value:
            raise PolicyError("egress policy refused")


def env_revoked() -> bool:
    return os.environ.get("RADIX_EGRESS_REVOKED", "").strip().lower() in {"1", "true", "yes"}


def system_resolve(host: str) -> str:
    """One lookup. Mixed or non-public answers are refused. The result is pinned."""
    if host != APPROVED_HOST:
        raise ProxyError("destination not approved")
    try:
        answers = socket.getaddrinfo(host, APPROVED_PORT, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ProxyError("dns failed") from exc
    found: list[str] = []
    for answer in answers:
        address = str(answer[4][0])
        if address not in found:
            found.append(address)
    if not found or any(not routable(address) for address in found):
        raise ProxyError("dns refused")
    return found[0]


def connect_pinned(address: str, port: int) -> socket.socket:
    if port != APPROVED_PORT or not routable(address):
        raise ProxyError("refusing address")
    return socket.create_connection((address, port), timeout=10)


def parse_connect_target(target: str) -> tuple[str, int] | None:
    if not target or not target.isascii() or "@" in target or "\\" in target or " " in target:
        return None
    if target.startswith("["):
        return None
    if target.count(":") != 1:
        return None
    host, port_text = target.split(":", 1)
    host = host.lower().removesuffix(".")
    if port_text != "443" or host != APPROVED_HOST:
        return None
    return host, APPROVED_PORT


class Proxy:
    """Decision and tunnel limits. DNS and connect are injected in tests."""

    def __init__(
        self,
        *,
        resolve: Callable[[str], str] = system_resolve,
        connect: Callable[[str, int], socket.socket] = connect_pinned,
        revoked: bool = False,
        now: Callable[[], float] | None = None,
        max_concurrent: int = BOUNDS["max_concurrent"],
        max_requests_per_minute: int = BOUNDS["max_requests_per_minute"],
        max_response_bytes: int = BOUNDS["max_response_bytes"],
        max_duration_seconds: float = BOUNDS["max_duration_seconds"],
    ) -> None:
        self._resolve = resolve
        self._connect = connect
        self._revoked = revoked
        self._now = time.monotonic if now is None else now
        self._max_concurrent = max_concurrent
        self._max_per_minute = max_requests_per_minute
        self._max_bytes = max_response_bytes
        self._max_duration = max_duration_seconds
        self._lock = threading.Lock()
        self._times: list[float] = []
        self._active = 0

    def handle(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(5)
            data = self._read_headers(conn)
            if data is None:
                return
            head, _, rest = data.partition(b"\r\n\r\n")
            line = head.split(b"\r\n", 1)[0].decode("ascii", "replace")
            parts = line.split(" ")
            if len(parts) >= 2 and parts[0] == "GET" and parts[1] == "/health":
                body = b"ok"
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n" + body
                )
                return
            if len(parts) < 2 or parts[0] != "CONNECT" or parse_connect_target(parts[1]) is None:
                self._refuse(conn)
                return
            if self._revoked or not self._admit():
                self._refuse(conn)
                return
            upstream: socket.socket | None = None
            try:
                pinned = self._resolve(APPROVED_HOST)
                if not routable(pinned):
                    self._refuse(conn)
                    return
                upstream = self._connect(pinned, APPROVED_PORT)
                conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                if rest:
                    upstream.sendall(rest[: self._max_bytes])
                self._relay(conn, upstream)
            except ProxyError:
                self._refuse(conn)
            finally:
                self._release()
                if upstream is not None:
                    upstream.close()
        except OSError:
            return
        finally:
            conn.close()

    def _admit(self) -> bool:
        now = self._now()
        with self._lock:
            self._times = [stamp for stamp in self._times if now - stamp < 60]
            if len(self._times) >= self._max_per_minute or self._active >= self._max_concurrent:
                return False
            self._times.append(now)
            self._active += 1
            return True

    def _release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    def _read_headers(self, conn: socket.socket) -> bytes | None:
        data = b""
        while b"\r\n\r\n" not in data:
            if len(data) > 8192:
                self._refuse(conn)
                return None
            try:
                chunk = conn.recv(4096)
            except OSError:
                return None
            if not chunk:
                return None
            data += chunk
        return data

    def _refuse(self, conn: socket.socket) -> None:
        body = b"refused"
        try:
            conn.sendall(
                b"HTTP/1.1 403 Forbidden\r\nContent-Length: 7\r\nConnection: close\r\n\r\n" + body
            )
        except OSError:
            return

    def _recv(self, sock: socket.socket) -> bytes | None:
        try:
            return sock.recv(16384)
        except TimeoutError:
            return None
        except OSError:
            return b""

    def _relay(self, client: socket.socket, upstream: socket.socket) -> None:
        deadline = time.monotonic() + self._max_duration
        sent = 0
        client.settimeout(0.2)
        upstream.settimeout(0.2)
        while time.monotonic() < deadline and sent < self._max_bytes:
            inbound = self._recv(client)
            if inbound is None:
                inbound = b""
            elif inbound == b"":
                return
            if inbound:
                try:
                    upstream.sendall(inbound[: self._max_bytes])
                except OSError:
                    return
            outbound = self._recv(upstream)
            if outbound is None:
                continue
            if outbound == b"":
                return
            room = self._max_bytes - sent
            outbound = outbound[:room]
            try:
                client.sendall(outbound)
            except OSError:
                return
            sent += len(outbound)


class Server:
    def __init__(self, proxy: Proxy, host: str = "127.0.0.1", port: int = 0) -> None:
        self.proxy = proxy
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self._sock.listen(16)
        self.port = int(self._sock.getsockname()[1])
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)

    def start(self) -> Server:
        self._thread.start()
        self._ready.wait(2)
        return self

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            return

    def serve_forever(self) -> None:
        self._accept()

    def _accept(self) -> None:
        self._ready.set()
        while not self._stop.is_set():
            try:
                self._sock.settimeout(0.5)
                conn, _addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(target=self.proxy.handle, args=(conn,), daemon=True).start()


def room_proxy_address() -> tuple[str, int]:
    """The app may dial only the room proxy. Any other value fails closed."""
    raw = os.environ.get("RADIX_EGRESS_PROXY", "").strip()
    if raw != ROOM_PROXY:
        raise ProxyError("room proxy is not configured")
    return "egress-proxy", 8080


def open_tunnel() -> socket.socket:
    """TCP to the room proxy, then CONNECT lokd.co.za:443. No direct dial."""
    host, port = room_proxy_address()
    try:
        sock = socket.create_connection((host, port), timeout=10)
    except OSError as exc:
        raise ProxyError("room proxy is unavailable") from exc
    try:
        sock.sendall(b"CONNECT lokd.co.za:443 HTTP/1.1\r\nHost: lokd.co.za:443\r\n\r\n")
        data = b""
        sock.settimeout(10)
        while b"\r\n\r\n" not in data and len(data) < 8192:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        if not data.startswith(b"HTTP/1.1 200"):
            sock.close()
            raise ProxyError("tunnel refused")
    except ProxyError:
        raise
    except OSError as exc:
        sock.close()
        raise ProxyError("room proxy is unavailable") from exc
    return sock


def read_certificate() -> tuple[dict[str, Any] | None, str | None]:
    """TLS through the tunnel. The certificate is checked against lokd.co.za."""
    raw = open_tunnel()
    context = ssl.create_default_context()
    try:
        with context.wrap_socket(raw, server_hostname=APPROVED_HOST) as wrapped:
            cert = wrapped.getpeercert()
            return cert, wrapped.version()
    except ssl.SSLCertVerificationError:
        return None, None
    except OSError as exc:
        raise ProxyError("tls failed") from exc


def main() -> int:
    path = os.environ.get("RADIX_EGRESS_POLICY", "/app/egress-policy.json")
    try:
        load_policy(path)
    except PolicyError:
        print("egress policy refused", file=sys.stderr)
        return 1
    proxy = Proxy(revoked=env_revoked())
    Server(proxy, host="0.0.0.0", port=8080).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
