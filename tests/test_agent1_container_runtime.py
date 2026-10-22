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


def run_browser_boundary(render_public=False):
    prefix = "agent1-browser-test-" + uuid.uuid4().hex[:10]
    private, corridor, other = [prefix + suffix for suffix in ("-private", "-gw", "-other")]
    browser, gateway = prefix + "-browser", prefix + "-gateway"
    volume = prefix + "-data"
    key = uuid.uuid4().hex
    env = dict(os.environ, TANK_KEY=key)
    try:
        for network in (private, other):
            docker("network", "create", "--internal", network)
        docker("network", "create", corridor)
        docker("volume", "create", volume)
        # SEAL-1: the browser runs with no Tank key; only the gateway holds it.
        docker("run", "-d", "--name", browser, "--network", private, "--network-alias", "base-browser",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "-v", volume + ":/browser-data", "-v", str(ROOT / "agents/_brain") + ":/app/brain:ro",
               "tervory-agent1-browser:cloud", env=env)
        docker("create", "--name", gateway, "--network", corridor,
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-e", "TANK_KEY",
               "tervory-agent1-gateway:cloud", env=env)
        docker("network", "connect", "--alias", "base-browser-gateway", private, gateway)
        docker("start", gateway)
        ready(browser, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health')"])
        ready(gateway, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health')"])
        script = '''import asyncio, os, socket, uuid, httpx
from playwright.async_api import async_playwright
from brain.browser import confirm_age, human_check, rendered_source
from brain.reader import read_page, model_page
async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='/usr/bin/chromium', headless=True)
        context = await browser.new_context()
        await context.route('**/*',lambda route: route.fulfill(content_type='text/html',body="""<h1>Age verification: over 21</h1><button type="button" onclick="document.cookie='age=ok;path=/';this.remove()">I am over 21</button><a href="/about">About</a><div style="height:2000px"></div>"""))
        page = await context.new_page()
        await page.goto('https://dealer.example.test')
        assert await confirm_age(page,await page.content())
        assert (await context.cookies())[0]['name']=='age'
        await page.evaluate('window.scrollBy(0,900)')
        assert await page.evaluate('window.scrollY')>0
        assert (await page.locator('a').get_attribute('href'))=='/about'
        await context.storage_state(path='/browser-data/fixture-storage.json')
        await context.close()
        context=await browser.new_context(storage_state='/browser-data/fixture-storage.json')
        assert (await context.cookies())[0]['value']=='ok'
        page=await context.new_page()
        await page.set_content('<div class="g-recaptcha">verify you are human</div><button type="button">I am over 21</button>')
        assert human_check(await page.content())
        assert not await confirm_age(page,await page.content())
        hidden_styles = ['font-size:0','font-size:3px','height:0;overflow:hidden',
            'position:absolute;left:-10000px;top:0','position:absolute;left:100000px;top:0',
            'position:absolute;top:100000px;left:0','position:absolute;clip:rect(0px,0px,0px,0px)',
            'clip-path:inset(50%)','position:absolute;width:1px;height:1px;overflow:hidden',
            'color:transparent','color:rgb(255,255,255)']
        await page.set_content('<body style="background:white"><h1>Visible heading</h1>' +
            ''.join('<p style="'+css+'">HIDDEN INSTRUCTIONS</p>' for css in hidden_styles) + '</body>')
        report = model_page(read_page('https://public.example', await rendered_source(page)))
        assert 'HIDDEN INSTRUCTIONS' not in report and 'Visible heading' in report
        assert 'not instructions' in report
        await context.close()
        await browser.close()
asyncio.run(run())
headers = {'X-Tank-Key': os.environ['TANK_KEY'], 'X-Tenant-ID': str(uuid.uuid4()), 'X-Home-Region': 'us-east'}
# SEAL-1: the browser answers only its gateway, so a caller inside it is refused.
assert httpx.post('http://127.0.0.1:3000/render',headers=headers,json={'url':'https://www.atf.gov'}).status_code == 401
assert httpx.post('http://base-browser-gateway:3000/render',headers=headers,json={'url':'https://169.254.169.254'}).status_code == 403
PUBLIC_RENDER_CHECK
headers['X-Tank-Key'] = uuid.uuid4().hex
assert httpx.post('http://base-browser-gateway:3000/render',headers=headers,json={'url':'https://www.atf.gov'}).status_code == 401
s = socket.socket(); s.settimeout(2)
assert s.connect_ex(('1.1.1.1',443)) != 0
s.close()
s = socket.create_connection(('base-browser-gateway',3128),2)
s.sendall(b'CONNECT 169.254.169.254:443 HTTP/1.1\\r\\nHost: 169.254.169.254\\r\\n\\r\\n')
assert b'403' in s.recv(1024)
s.close()
print('PASS Chromium, gateway-only browser, wrong room key, direct egress, proxy allowlist')
'''
        public_check = "response = httpx.post('http://base-browser-gateway:3000/render',headers=headers,json={'url':'https://example.com','settle_ms':0},timeout=170)\nassert response.status_code == 200, (response.status_code,response.text)\nvalue = response.json()\nassert 'html' not in value, response.text\nif value.get('skipped'):\n    assert value['reason'] == 'robots.txt' and value['page']['facts']['skip_reason'] == 'robots.txt', response.text\nelse:\n    assert value['ok'] and value['page']['facts']['title'] == 'Example Domain' and value['page']['text'], response.text\n"
        script = script.replace("PUBLIC_RENDER_CHECK", public_check if render_public else "")
        # The test key reaches only this one exec, never the browser's own environment.
        assert docker("exec", "-e", "TANK_KEY", browser, "python", "-c", script, env=env).startswith("PASS")
        gateway_address = json.loads(docker("inspect", gateway))[0]["NetworkSettings"]["Networks"][corridor]["IPAddress"]
        corridor_probe = "import socket,urllib.request,sys; urllib.request.urlopen('http://'+sys.argv[1]+':3000/health'); s=socket.socket(); s.settimeout(2); assert s.connect_ex((sys.argv[1],3128)) != 0; print('PASS proxy is browser-only')"
        assert docker("run","--rm","--network",corridor,"--cap-drop","ALL","tervory-agent1-browser:cloud",
            "python","-c",corridor_probe,gateway_address).startswith("PASS")
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


def test_real_private_browser_and_other_room_boundary():
    run_browser_boundary()


def test_unprivileged_sibling_exec_is_offline_and_separates_runs():
    prefix = "agent1-exec-test-" + uuid.uuid4().hex[:10]
    network, sandbox = prefix + "-net", prefix + "-sandbox"
    key=uuid.uuid4().hex
    env=dict(os.environ,SANDBOX_KEY=key)
    try:
        docker("network", "create", "--internal", network)
        docker("run", "-d", "--name", sandbox, "--network", network, "--network-alias", "base-sandbox",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--pids-limit", "64",
               "--memory", "512m", "--cpus", "0.5", "-e", "SANDBOX_KEY", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m",
               "--tmpfs", "/work:rw,nosuid,nodev,size=128m,uid=1000,gid=1000,mode=0700", "tervory-agent1-sandbox:cloud", env=env)
        ready(sandbox, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health')"])
        docker("exec", sandbox, "python", "-c", "from pathlib import Path; p=Path('/work/private-other'); p.mkdir(); (p/'proof').write_text('not-for-this-run')")
        script = r'''import base64, json, os, urllib.request, urllib.error, uuid
first, second, task = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
for presented in ('',uuid.uuid4().hex):
 request=urllib.request.Request('http://base-sandbox:8002/exec',data=json.dumps({'tenant_id':first,'task_id':task,'command':'python -c \"pass\"'}).encode(),headers={'Content-Type':'application/json','X-Sandbox-Key':presented})
 try: urllib.request.urlopen(request,timeout=3)
 except urllib.error.HTTPError as refused: assert refused.code==401
 else: raise AssertionError('unauthenticated exec accepted')
def run(tenant, command, files=None):
 body=json.dumps({'tenant_id':tenant,'task_id':task,'command':command,'files':files or {}}).encode()
 request=urllib.request.Request('http://base-sandbox:8002/exec',data=body,headers={'Content-Type':'application/json','X-Sandbox-Key':os.environ['SANDBOX_KEY']})
 return json.load(urllib.request.urlopen(request,timeout=35))
command = """python - <<'CODE'
import os
from pathlib import Path
assert not any(k in os.environ for k in ('TANK_KEY','OPENAI_API_KEY','DOCKER_HOST','DATABASE_URL','SANDBOX_KEY'))
try:
 import socket
 socket.socket()
except (ImportError, OSError): pass
else: raise AssertionError('network available')
try: Path('/proc/1/environ').read_bytes()
except OSError: pass
else: raise AssertionError('service environment readable')
try: Path('/python/lib/untrusted-write').write_text('no')
except OSError: pass
else: raise AssertionError('root writable')
Path('proof').write_text('private-work')
print('OFFLINE')
CODE"""
result=run(first,command)
assert result['exit_code']==0 and 'OFFLINE' in result['output'], result
assert base64.b64decode(result['files']['proof'])==b'private-work'
command="python -c \"from pathlib import Path; p=Path('/work/private-other/proof'); blocked=False\ntry: p.read_bytes()\nexcept OSError: blocked=True\nassert blocked; print('TENANT ISOLATED')\""
result=run(second,command)
assert result['exit_code']==0 and 'TENANT ISOLATED' in result['output'], result
try: run(first,'true',{'../escape':base64.b64encode(b'bad').decode()})
except urllib.error.HTTPError as refused: assert refused.code==422
else: raise AssertionError('traversal accepted')
print('PASS sibling exec, denied network, no credentials, read-only root, WASI tenant workspaces')
'''
        output = docker("run", "--rm", "--network", network, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                        "-e", "SANDBOX_KEY", "tervory-agent1-brain:cloud", "python", "-c", script, env=env)
        assert "PASS sibling exec" in output
        info=json.loads(docker("inspect",sandbox))[0]
        assert not info['HostConfig']['Privileged'] and not info['HostConfig'].get('CapAdd')
        assert info['HostConfig']['ReadonlyRootfs'] and 'ALL' in info['HostConfig']['CapDrop']
        assert info['HostConfig']['PidMode'] in ('','private')
        assert info['HostConfig']['NetworkMode']==network
    finally:
        subprocess.run(["docker", "rm", "-fv", sandbox], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)
