"""Opt-in checks of all five real Rig containers on disposable cloud networks.

Build tervory-rig-{api,brain,browser,gateway,sandbox}:cloud, then set
RIG2_CONTAINER_IMAGES=1. No host ports, host namespaces or production credentials.
"""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("RIG2_CONTAINER_IMAGES"), reason="Explicit cloud Docker checks")
ROOT = Path(__file__).resolve().parents[1]


def test_rig_real_box_public_api_and_sealed_execution(tmp_path):
    executable = os.environ.get("RIG2_DOCKER", "docker")
    project = "rig2-box-" + uuid.uuid4().hex[:10]
    # The live checker requires the literal corridor. Use an isolated fixture
    # network with a Docker command adapter that reports only its logical name.
    corridor, sandbox_net, browser_net = project + "_gw", project + "_sandbox", project + "_browser"
    containers, volumes, networks = [], [], []
    key, executor_key = uuid.uuid4().hex, uuid.uuid4().hex
    env = dict(os.environ, TANK_KEY=key, SANDBOX_KEY=executor_key)
    def docker(*args, input=None, timeout=90):
        result = subprocess.run([executable, *args], env=env, input=input, text=True, capture_output=True, timeout=timeout)
        assert result.returncode == 0, result.stderr[-2000:].replace(key, "[room key]").replace(executor_key, "[executor key]")
        return result.stdout.strip()
    def ready(name, port):
        command = "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:" + str(port) + "/health',timeout=3); assert r.status==200 and json.load(r)['ok']"
        for _ in range(45):
            result = subprocess.run([executable, "exec", name, "python", "-c", command], capture_output=True, timeout=5)
            if result.returncode == 0:
                return
            if docker("inspect", "-f", "{{.State.Running}}", name) != "true":
                break
            time.sleep(.5)
        pytest.fail("Cloud fixture did not become healthy: " + name)
    def create(service, image, nets, *args):
        name = project + "-" + service
        containers.append(name)
        command = ["create", "--name", name, "--network", nets[0], "--network-alias", service,
            "--label", "coolify.applicationUuid=" + project, "--label", "com.docker.compose.project=" + project,
            "--label", "com.docker.compose.service=" + service, "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--memory", "2g", "--cpus", "1",
            "-e", "NO_PROXY=localhost,127.0.0.1,postgres,tank,hermes,rig-sandbox,rig-browser,rig-browser-gateway,rig-brain",
            *args, "tervory-rig-" + image + ":cloud"]
        docker(*command)
        for network in nets[1:]:
            docker("network", "connect", "--alias", service, network, name)
        docker("start", name)
        return name
    try:
        for network, internal in ((corridor, False), (sandbox_net, True), (browser_net, True)):
            docker("network", "create", *(["--internal"] if internal else []), network)
            networks.append(network)
        for suffix in ("api", "brain", "browser"):
            volume = project + "-" + suffix
            docker("volume", "create", volume)
            volumes.append(volume)
        postgres = project + "-postgres"
        containers.append(postgres)
        docker("run", "-d", "--name", postgres, "--network", corridor, "--network-alias", "postgres",
               "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16")
        for _ in range(40):
            probe = subprocess.run([executable, "exec", postgres, "pg_isready", "-U", "postgres"], capture_output=True)
            if probe.returncode == 0: break
            time.sleep(.5)
        assert probe.returncode == 0
        sandbox = create("rig-sandbox", "sandbox", [sandbox_net], "--read-only", "--pids-limit", "64",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m", "--tmpfs", "/work:rw,nosuid,nodev,size=128m,uid=1000,gid=1000,mode=0700",
            "-e", "SANDBOX_KEY", "-e", "BRAIN_ROOM=rig")
        browser = create("rig-browser", "browser", [browser_net], "--shm-size", "256m",
            "-e", "ACCESS_ROOM=rig", "-e", "ACCESS_GATEWAY_URL=http://rig-browser-gateway:3000",
            "-e", "BROWSER_PROXY_URL=http://rig-browser-gateway:3128", "-v", volumes[2] + ":/browser-data")
        gateway = create("rig-browser-gateway", "gateway", [corridor, browser_net], "-e", "TANK_KEY",
            "-e", "ACCESS_ROOM=rig", "-e", "BROWSER_HOST=rig-browser")
        brain = create("rig-brain", "brain", [corridor, sandbox_net], "-e", "TANK_KEY", "-e", "SANDBOX_KEY",
            "-v", volumes[1] + ":/data", "-e", "TANK_REGION=us-east")
        api = create("agent-rig", "api", [corridor], "-e", "TANK_KEY", "-e", "AGENT_NAME=rig",
            "-e", "DATABASE_URL=postgresql://postgres@postgres:5432/postgres", "-e", "RIG_BRAIN_URL=http://rig-brain:8001",
            "-e", "CATALOGUE_DIR=/app/catalogues", "-e", "DATA_DIR=/data", "-v", volumes[0] + ":/data")
        for name, port in ((api, 8000), (brain, 8001), (browser, 3000), (gateway, 3000), (sandbox, 8002)):
            ready(name, port)
        api_probe = r'''import httpx,json
from pathlib import Path
with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False) as client:
 assert client.get('/health').json()['ok'] is True
 config=json.loads(Path('/app/catalogues/second/publish.json').read_text())
 headers={'X-Rig-Key':config['keys'][0]['key'],'Origin':config['keys'][0]['origins'][0]}
 result=client.get('/v1/rig/search',params={'q':'lamp'},headers=headers)
 assert result.status_code==200 and 'Second Desk Lamp' in result.text
 assert client.post('/brain/tasks',json={'tenant_id':config['tenant_id'],'task_id':'00000000-0000-4000-8000-000000000001','home_region':'us-east','question':'Sample lamp'},headers=headers).status_code==401
print('PASS public health, real catalogue, shopper cannot start brain')
'''
        assert "PASS public" in docker("exec", "-i", api, "python", "-", input=api_probe)
        execution_probe = r'''import httpx,os,uuid
tenant,task=str(uuid.uuid4()),str(uuid.uuid4())
code="python -c \"import os; from pathlib import Path; assert not any(k in os.environ for k in ('TANK_KEY','SANDBOX_KEY','DATABASE_URL')); print('WASI')\""
with httpx.Client(trust_env=False,timeout=40) as client:
 body={'tenant_id':tenant,'task_id':task,'command':code}
 assert client.post('http://rig-sandbox:8002/exec',json=body).status_code==401
 result=client.post('http://rig-sandbox:8002/exec',json=body,headers={'X-Sandbox-Key':os.environ['SANDBOX_KEY']}).json()
 assert result['exit_code']==0 and 'WASI' in result['output'], result
 result=client.post('http://rig-sandbox:8002/exec',json={**body,'command':'python -c "import socket; socket.socket()"'},headers={'X-Sandbox-Key':os.environ['SANDBOX_KEY']}).json()
 assert result['exit_code']!=0
 headers={'X-Tank-Key':os.environ['TANK_KEY'],'X-Tenant-ID':tenant,'X-Home-Region':'us-east'}
 assert client.post('http://rig-browser-gateway:3000/render',json={'url':'http://127.0.0.1'},headers=headers).status_code==403
 try: client.get('http://rig-browser:3000/health',timeout=2)
 except httpx.HTTPError: pass
 else: raise AssertionError('brain reached private browser directly')
print('PASS sandbox authentication, no credentials, denied sockets, private browser')
'''
        assert "PASS sandbox" in docker("exec", "-i", brain, "python", "-", input=execution_probe)
        browser_probe = r'''import asyncio,os,socket
from playwright.async_api import async_playwright
assert 'TANK_KEY' not in os.environ
try: socket.create_connection(('1.1.1.1',443),timeout=1)
except OSError: pass
else: raise AssertionError('sealed browser has direct egress')
async def run():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  a,c=await b.new_context(),await b.new_context()
  await a.add_cookies([{'name':'tenant','value':'first','url':'https://example.com'}])
  assert await c.cookies()==[]
  await b.close()
asyncio.run(run())
print('PASS browser egress denied, no Tank key, separate tenant contexts')
'''
        assert "PASS browser" in docker("exec", "-i", browser, "python", "-", input=browser_probe)
        # Actual inspect evidence, translated only from the unique fixture
        # corridor to its production logical name. No production objects touched.
        data = {"containers": {}, "networks": {"tervory-gw-rig": False, sandbox_net: True, browser_net: True}}
        for name in (api, brain, sandbox, browser, gateway):
            info = json.loads(docker("inspect", name))[0]
            assert not info["HostConfig"]["Privileged"] and not info["HostConfig"].get("PortBindings")
            data["containers"][name] = {"uuid": project, "project": project,
                "service": info["Config"]["Labels"]["com.docker.compose.service"], "name": name,
                "networks": ["tervory-gw-rig" if n == corridor else n for n in info["NetworkSettings"]["Networks"]]}
        from test_room_seal import run_seal_check
        path = tmp_path / "rig-live-inspect.json"
        path.write_text(json.dumps(data))
        result = run_seal_check(tmp_path, str(path))
        assert f"agent-rig ({project}): sealed" in result.stdout
        assert "LEAK" not in result.stdout and "NOT SEALED" not in result.stdout
        # Other expected rooms are absent in this deliberately Rig-only fixture.
        assert result.returncode == 1 and "agent-base: NOT FOUND" in result.stdout
    finally:
        for container in reversed(containers):
            subprocess.run([executable, "rm", "-fv", container], capture_output=True)
        for volume in volumes:
            subprocess.run([executable, "volume", "rm", volume], capture_output=True)
        for network in reversed(networks):
            subprocess.run([executable, "network", "rm", network], capture_output=True)
