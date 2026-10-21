"""Opt-in checks of real cloud containers, without any model/provider credentials.

Build the four agents/base/Dockerfile.* images as tervory-agent1-*:cloud, then:
AGENT1_CONTAINER_IMAGES=1 pytest -q tests/test_agent1_container_runtime.py
Only this test's randomly named containers, volumes and networks are removed.
"""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("AGENT1_CONTAINER_IMAGES"), reason="Explicit cloud Docker checks")
ROOT = Path(__file__).resolve().parents[1]


def docker(*args, **kwargs):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=90, **kwargs)
    assert result.returncode == 0, result.stderr[-3000:]
    return result.stdout.strip()


def ready(container, command):
    for _ in range(60):
        result = subprocess.run(["docker", "exec", container, *command], capture_output=True, timeout=5)
        if result.returncode == 0:
            return
        if docker("inspect", "--format", "{{.State.Running}}", container) != "true":
            break
        time.sleep(1)
    # These containers have only random test credentials, no production values.
    logged = subprocess.run(["docker", "logs", "--tail", "20", container], capture_output=True, text=True)
    logs = logged.stdout + logged.stderr
    pytest.fail("Cloud container did not become ready: " + container + "\n" + logs)


def test_real_private_browser_and_other_room_boundary():
    prefix = "agent1-browser-test-" + uuid.uuid4().hex[:10]
    private, corridor, other = [prefix + suffix for suffix in ("-private", "-gw", "-other")]
    browser, gateway = prefix + "-browser", prefix + "-gateway"
    volume = prefix + "-data"
    key = uuid.uuid4().hex
    env = dict(os.environ, TANK_KEY=key)
    try:
        for network in (private, corridor, other):
            docker("network", "create", "--internal", network)
        docker("volume", "create", volume)
        docker("run", "-d", "--name", browser, "--network", private, "--network-alias", "base-browser",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-e", "TANK_KEY", "-e", "BASE_ALLOWED_HOSTS=www.atf.gov",
               "-v", volume + ":/browser-data", "-v", str(ROOT / "agents/_brain") + ":/app/brain:ro",
               "tervory-agent1-browser:cloud", env=env)
        docker("run", "-d", "--name", gateway, "--network", private, "--network-alias", "base-browser-gateway",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-e", "TANK_KEY", "-e", "BASE_ALLOWED_HOSTS=www.atf.gov",
               "tervory-agent1-gateway:cloud", env=env)
        docker("network", "connect", corridor, gateway)
        ready(browser, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health')"])
        ready(gateway, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health')"])
        script = '''import asyncio, os, socket, uuid, httpx
from playwright.async_api import async_playwright
async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='/usr/bin/chromium', headless=True)
        page = await browser.new_page()
        await page.set_content('<h1>Cloud Chromium proof</h1>')
        assert await page.title() == ''
        assert await page.locator('h1').inner_text() == 'Cloud Chromium proof'
        await browser.close()
asyncio.run(run())
headers = {'X-Tank-Key': os.environ['TANK_KEY'], 'X-Tenant-ID': str(uuid.uuid4()), 'X-Home-Region': 'us-east'}
assert httpx.post('http://127.0.0.1:3000/render',headers=headers,json={'url':'https://disallowed.example'}).status_code == 403
headers['X-Tank-Key'] = uuid.uuid4().hex
assert httpx.post('http://127.0.0.1:3000/render',headers=headers,json={'url':'https://www.atf.gov'}).status_code == 401
s = socket.socket(); s.settimeout(2)
assert s.connect_ex(('1.1.1.1',443)) != 0
s.close()
s = socket.create_connection(('base-browser-gateway',3128),2)
s.sendall(b'CONNECT disallowed.example:443 HTTP/1.1\\r\\nHost: disallowed.example\\r\\n\\r\\n')
assert b'403' in s.recv(1024)
s.close()
print('PASS Chromium, browser allowlist, wrong room key, direct egress, proxy allowlist')
'''
        assert docker("exec", browser, "python", "-c", script).startswith("PASS")
        address = json.loads(docker("inspect", browser))[0]["NetworkSettings"]["Networks"][private]["IPAddress"]
        probe = '''import socket, sys
try:
    socket.getaddrinfo('base-browser',3000)
except socket.gaierror:
    pass
else:
    raise AssertionError('another room resolved Base browser')
s = socket.socket(); s.settimeout(2)
assert s.connect_ex((sys.argv[1],3000)) != 0
print('PASS other room cannot resolve or connect to Base browser')
'''
        assert docker("run", "--rm", "--network", other, "tervory-agent1-browser:cloud", "python", "-c", probe, address).startswith("PASS")
    finally:
        subprocess.run(["docker", "rm", "-fv", browser, gateway], capture_output=True)
        subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
        for network in (private, corridor, other):
            subprocess.run(["docker", "network", "rm", network], capture_output=True)


def test_actual_hermes_docker_backend_is_offline_and_uses_own_volume():
    prefix = "agent1-sandbox-test-" + uuid.uuid4().hex[:10]
    network, daemon, volume = prefix + "-net", prefix + "-daemon", prefix + "-data"
    try:
        docker("network", "create", "--internal", network)
        docker("volume", "create", volume)
        docker("run", "-d", "--name", daemon, "--network", network, "--network-alias", "base-sandbox", "--privileged",
               "-v", volume + ":/data", "tervory-agent1-sandbox:cloud")
        ready(daemon, ["test", "-f", "/tmp/base-sandbox-ready"])
        script = r'''import json, os
from pathlib import Path
Path('/data/proof').mkdir(exist_ok=True)
os.environ.update(TERMINAL_ENV='docker', TERMINAL_DOCKER_IMAGE='tervory-base-sandbox:python3.12',
    TERMINAL_DOCKER_IMAGE_PINNED='1', TERMINAL_DOCKER_NETWORK='false', TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES='false',
    TERMINAL_DOCKER_FORWARD_ENV='[]', TERMINAL_DOCKER_VOLUMES='["/data/proof:/workspace"]',
    TERMINAL_DOCKER_EXTRA_ARGS='["--read-only","--pids-limit","128"]', TERMINAL_CWD='/workspace',
    TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE='false', HERMES_HOME='/tmp/hermes-proof')
from tools.terminal_tool import terminal_tool
command = "python -c 'import os,socket; from pathlib import Path; s=socket.socket(); s.settimeout(2); assert s.connect_ex((\"1.1.1.1\",443)) != 0; assert not any(k in os.environ for k in (\"TANK_KEY\",\"OPENAI_API_KEY\",\"DOCKER_HOST\")); Path(\"/workspace/proof\").write_text(\"offline\"); print(\"OFFLINE\")'"
result = json.loads(terminal_tool(command=command, timeout=30, task_id='cloud-proof'))
assert result.get('exit_code') == 0, result
assert 'OFFLINE' in result['output']
assert Path('/data/proof/proof').read_text() == 'offline'
print('PASS actual Hermes Docker tool, denied egress, no forwarded credentials, Base-only work mount')
'''
        output = docker("run", "--rm", "--network", network, "-v", volume + ":/data",
                        "-e", "DOCKER_HOST=tcp://base-sandbox:2375", "tervory-agent1-brain:cloud", "python", "-c", script)
        assert "PASS actual Hermes Docker tool" in output
    finally:
        subprocess.run(["docker", "rm", "-fv", daemon], capture_output=True)
        subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)
