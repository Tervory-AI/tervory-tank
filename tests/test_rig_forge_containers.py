"""Required forge-image CI check, using only disposable cloud Docker networks."""
import os
import subprocess
import time
import uuid

import pytest

IMAGE = os.environ.get("RIG_FORGE_CONTAINER_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Runs in required forge-image CI job")


def test_real_container_isolation_and_private_health():
    prefix = "rig5f-" + uuid.uuid4().hex[:10]
    networks, containers = [], []
    def docker(*args, input=None):
        result = subprocess.run(["docker", *args], input=input, text=True, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr[-1000:]
        return result.stdout.strip()
    def create(name, nets, command):
        target = prefix + "-" + name
        containers.append(target)
        docker("create", "--name", target, "--network", nets[0], "--network-alias", name,
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m,uid=1000,gid=1000",
            "--tmpfs", "/data:rw,nosuid,nodev,size=64m,uid=1000,gid=1000",
            "--memory", "1g", "--pids-limit", "128", IMAGE, *command)
        for network in nets[1:]:
            docker("network", "connect", "--alias", name, network, target)
        docker("start", target)
        return target
    try:
        for suffix, internal in (("control", True), ("link", True), ("outbound", False)):
            network = prefix + "_" + suffix
            docker("network", "create", *(["--internal"] if internal else []), network)
            networks.append(network)
        brain = create("rig-brain", [networks[0]], ["python", "-c", "import time; time.sleep(300)"])
        forge = create("rig-forge", networks[:2], ["uvicorn", "forge.service:app", "--host", "0.0.0.0",
            "--port", "8010", "--no-access-log", "--no-proxy-headers"])
        proxy = create("rig-forge-egress", networks[1:], ["python", "-m", "forge.egress"])
        ready = "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8010/health',timeout=2).status==200"
        for _ in range(30):
            result = subprocess.run(["docker", "exec", forge, "python", "-c", ready], capture_output=True)
            if result.returncode == 0: break
            time.sleep(.5)
        assert result.returncode == 0, "Forge health did not become ready"
        for _ in range(20):
            result = subprocess.run(["docker", "exec", proxy, "python", "-m", "forge.egress", "health"], capture_output=True)
            if result.returncode == 0: break
            time.sleep(.5)
        assert result.returncode == 0, "Proxy health did not become ready"
        docker("exec", "-i", brain, "python", "-", input="""import httpx
with httpx.Client(trust_env=False,timeout=3) as c:
 assert c.get('http://rig-forge:8010/health').json()['ok']
""")
        docker("exec", "-i", proxy, "python", "-", input="""import httpx
with httpx.Client(trust_env=False,timeout=3) as c:
 assert c.get('http://rig-forge:8010/health').status_code == 401
""")
        docker("exec", "-i", forge, "python", "-", input="""import os,socket
assert not any(os.environ.get(k) for k in ('TANK_KEY','TANK_KEY_RIG','TANK_API_KEY'))
try: socket.create_connection(('1.1.1.1',443),timeout=1)
except OSError: pass
else: raise AssertionError('Forge has direct egress')
for destination in ('example.com:443','huggingface.co:80','127.0.0.1:443','tank:8000'):
 with socket.create_connection(('rig-forge-egress',8080),timeout=3) as s:
  s.sendall(('CONNECT '+destination+' HTTP/1.1\\r\\nHost: '+destination+'\\r\\n\\r\\n').encode())
  assert b'403 Forbidden' in s.recv(256)
""")
        assert docker("inspect", "-f", "{{.HostConfig.Privileged}}", forge) == "false"
        assert docker("inspect", "-f", "{{len .HostConfig.PortBindings}}", forge) == "0"
    finally:
        for container in reversed(containers):
            subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        for network in reversed(networks):
            subprocess.run(["docker", "network", "rm", network], capture_output=True)
