"""CI-only network proof using production Compose attachments and Radix Proxy.

All test networks, including the fake upstream networks, are internal. The
injected connector replaces public DNS/TLS upstreams with local echo endpoints;
production host admission, limits, NIC binding and network topology are reused.
No credential, production volume or outside endpoint is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time



def endpoint():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((os.environ["TEST_BIND"], 443))
        listener.listen()
        while True:
            conn, _ = listener.accept()
            with conn:
                conn.settimeout(2)
                try:
                    conn.recv(4096)
                    conn.sendall(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n")
                except OSError:
                    pass


def proxy():
    sys.path.insert(0, "/source/agents/radix")
    import egress
    original = egress.Proxy
    allowed = os.environ["TEST_ALLOWED"]
    def configured(**kwargs):
        kwargs["resolve"] = lambda host: "1.1.1.1"
        kwargs["connect"] = lambda ip, port: socket.create_connection((os.environ["TEST_UPSTREAM"], port), 2)
        return original(**kwargs)
    egress.Proxy = configured
    # Execute the production command, including private NIC bind and exact host.
    command = json.loads(os.environ["TEST_COMMAND"])
    assert allowed in command[-1]
    exec(command[-1], {})


def connected(host, port):
    try:
        with socket.create_connection((host, port), 0.4):
            return True
    except OSError:
        return False


def client_hello(host):
    outgoing = ssl.MemoryBIO()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    client = context.wrap_bio(ssl.MemoryBIO(), outgoing, server_hostname=host)
    try:
        client.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.read()


def probe():
    proxy_host, allowed = sys.argv[2:4]
    for _ in range(60):
        if connected(proxy_host, 8080):
            break
        time.sleep(0.2)
    else:
        raise AssertionError("proxy did not start")
    targets = [allowed+":443", "example.com:443", "tank:443", "other-client:443",
               "api.cloudflare.com:443" if allowed == "tervory.com" else "tervory.com:443",
               "127.0.0.1:443", "169.254.169.254:443", allowed+":80"]
    for target in targets:
        with socket.create_connection((proxy_host, 8080), 2) as conn:
            conn.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
            reply = conn.recv(4096)
            assert (b"200 Connection Established" in reply) == (target == allowed+":443"), (target, reply)
            if target == allowed+":443":
                conn.sendall(client_hello(allowed))
                assert b"204 No Content" in conn.recv(4096)
    for hello in (client_hello("example.com"), client_hello(None), b"GET / HTTP/1.1\r\n\r\n"):
        with socket.create_connection((proxy_host, 8080), 2) as conn:
            conn.sendall(f"CONNECT {allowed}:443 HTTP/1.1\r\n\r\n".encode())
            assert b"200 Connection Established" in conn.recv(4096)
            conn.sendall(hello)
            assert b"204 No Content" not in conn.recv(4096), "SNI admission bypass"
    for host in ("fake-api", "fake-health", "tank", "other-client", "health-observer"
                 if proxy_host == "egress-proxy" else "enforce", "1.1.1.1",
                 "172.30.242.10", "172.30.243.10", "172.30.244.10", "172.30.245.10"):
        assert not connected(host, 443), f"direct escape: {host}"
    other_proxy = "health-egress-proxy" if proxy_host == "egress-proxy" else "egress-proxy"
    assert not connected(other_proxy, 8080)
    print(f"PASS {proxy_host}: allowed tunnel works; other hosts, direct egress, Tank and other client refused")


def run():
    import yaml
    root = Path.cwd()
    source = yaml.safe_load((root / "agents/ghost/docker-compose.enforce.yml").read_text())
    services = {}
    for name, production in source["services"].items():
        svc = {k: production[k] for k in ("networks", "read_only", "cap_drop", "security_opt", "tmpfs")}
        svc.update(image="python:3.12-slim", volumes=[f"{root}:/source:ro"],
                   command=["python", "-c", "import time; time.sleep(600)"],
                   environment={"PYTHONDONTWRITEBYTECODE": "1"},
                   labels={"coolify.applicationUuid": "autumbra-a3-ci"})
        if name.endswith("proxy"):
            svc["command"] = ["python", "/source/tests/autumbra_cloudflare_hand/compose_probe.py", "proxy"]
            svc["environment"].update(
                TEST_ALLOWED="api.cloudflare.com" if name == "egress-proxy" else "tervory.com",
                TEST_UPSTREAM="fake-api" if name == "egress-proxy" else "fake-health",
                TEST_COMMAND=json.dumps(production["command"]))
        services[name] = svc
    for name, network, ip in [("fake-api", "egress", "172.30.242.10"),
                              ("fake-health", "health_egress", "172.30.243.10"),
                              ("tank", "tank", "172.30.244.10"),
                              ("other-client", "other_client", "172.30.245.10")]:
        services[name] = dict(image="python:3.12-slim", volumes=[f"{root}:/source:ro"],
                              command=["python", "/source/tests/autumbra_cloudflare_hand/compose_probe.py", "endpoint"],
                              environment={"TEST_BIND": ip},
                              networks={network: {"ipv4_address": ip}})
    networks = {name: {"internal": True} for name in source["networks"]}
    for name, subnet in [("egress", "172.30.242.0/24"), ("health_egress", "172.30.243.0/24"),
                         ("tank", "172.30.244.0/24"), ("other_client", "172.30.245.0/24")]:
        networks[name] = dict(internal=True, ipam={"config": [{"subnet": subnet}]})
    output = root / ".proof/a3-compose.yml"
    output.parent.mkdir(exist_ok=True)
    output.write_text(yaml.safe_dump(dict(services=services, networks=networks)))
    compose = ["docker", "compose", "-p", "autumbra-a3-ci", "-f", str(output)]
    try:
        subprocess.run([*compose, "up", "-d", "--wait"], check=True)
        for service, proxy_host, allowed in [("enforce", "egress-proxy", "api.cloudflare.com"),
                                             ("health-observer", "health-egress-proxy", "tervory.com")]:
            subprocess.run([*compose, "exec", "-T", service, "python",
                            "/source/tests/autumbra_cloudflare_hand/compose_probe.py", "probe", proxy_host, allowed], check=True)
    finally:
        subprocess.run([*compose, "logs", "--no-color"], check=False)
        subprocess.run([*compose, "down", "--volumes", "--remove-orphans"], check=True)


if __name__ == "__main__":
    {"endpoint": endpoint, "proxy": proxy, "probe": probe, "run": run}[sys.argv[1]]()
