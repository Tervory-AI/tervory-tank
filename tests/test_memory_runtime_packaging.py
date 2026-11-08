"""Runtime packages must contain the security code exercised by integration tests."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_assertion_helpers_and_deployed_adapters_match_sources():
    assert (ROOT / 'tank/task_contract.py').read_bytes() == (
        ROOT / 'agents/_chassis/chassis/task_contract.py').read_bytes()
    source = (ROOT / 'agents/_chassis/chassis/user_assertion.py').read_bytes()
    for path in ('hermes/user_assertion.py', 'tank/command_tools/_user_assertion.py'):
        assert (ROOT / path).read_bytes() == source
    for name in ('opli_memory', 'workspace'):
        expected = (ROOT / 'integrations/tank' / (name + '.py')).read_text()
        expected = expected.replace('agents.opli', 'command_tools._opli').replace('integrations.workspace', 'command_tools._workspace')
        if name == 'opli_memory':
            expected = expected.replace('REQUEST_BODY_TOOLS =', 'TENANT_TOOLS = CLIENT_TOOLS\nREQUEST_BODY_TOOLS =')
        assert (ROOT / 'tank/command_tools' / (name + '.py')).read_text() == expected


def test_tank_personal_transports_work_without_repository_root():
    # -I excludes cwd/PYTHONPATH, matching Tank's ./tank-only build context.
    code = r'''
import asyncio, importlib.util, os, sys
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('hermes') is None
assert importlib.util.find_spec('chassis') is None
import httpx, engine_memory, memory_routes
from command_tools._shared_memory import MemoryClient
from command_tools._user_assertion import HEADER, verify_assertion
os.environ['TANK_API_KEY'] = 'placeholder-runtime-key'
tenant, user = '11111111-1111-1111-1111-111111111111', 'placeholder-runtime-user'
seen = []
async def claim(*args):
    return True
async def respond(request):
    actor = await verify_assertion(request.headers[HEADER], key='placeholder-runtime-key',
        product='hermes', tenant_id=tenant, method=request.method,
        target=request.url.raw_path.decode('ascii'), body=request.content, consume_nonce=claim)
    assert actor.user_id == user
    seen.append(request)
    return httpx.Response(200, json={'memories': []})
client_type = httpx.AsyncClient
factory = lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs)
engine_memory.HTTP = factory
memory_routes.httpx.AsyncClient = factory
async def main():
    await engine_memory.send('recall', {'tenant_id':tenant, 'user_id':user, 'query':'placeholder', 'task_type':'placeholder'})
    await memory_routes.hermes('GET', '/founder/records', user, params={'tenant_id':tenant, 'agent':'opli'})
    async with factory() as http:
        client = MemoryClient('http://placeholder', 'placeholder-runtime-key', 'opli', http)
        await client.records(tenant, user_id=user)
    assert len(seen) == 3
asyncio.run(main())
'''
    result = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT / 'tank')],
        cwd=ROOT / 'tank', capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_tank_tasks_and_skala_actor_work_without_chassis():
    code = r'''
import asyncio, importlib.util, os, sys
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('chassis') is None
os.environ['DATABASE_URL'] = 'postgresql://placeholder@127.0.0.1:9/placeholder'
os.environ['TANK_API_KEY'] = 'placeholder-runtime-key'
os.environ['LITELLM_MASTER_KEY'] = 'placeholder-runtime-key'
import agent_tasks, main, skala_memory_api, task_contract
from product_identity import User, actor_scope
from starlette.requests import Request
tenant, user = '11111111-1111-1111-1111-111111111111', 'placeholder-runtime-user'
request = Request({'type':'http', 'method':'GET', 'path':'/v1/skala/memory',
    'query_string':b'', 'headers':[(b'x-tank-key',b'placeholder-runtime-key')]})
async def check():
    with actor_scope(User(tenant, user, 'member')):
        assert await skala_memory_api.verified_actor(request, tenant) == {
            'tenant_id':tenant, 'user_id':user}
    assert task_contract.context(User(tenant, user, 'member'), tenant) == (tenant, tenant)
asyncio.run(check())
'''
    result = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT / 'tank')],
        cwd=ROOT / 'tank', capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
