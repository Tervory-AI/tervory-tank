def test_skala_client_without_source_chassis():
    """The actual opt-in client factory must work in Tank's deployed package."""
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    code = r'''
import asyncio, importlib.util, os, sys
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('chassis') is None
import httpx
from skala_memory_client import memory_client_for_skala
from command_tools._user_assertion import HEADER, verify_assertion
os.environ['TANK_KEY_SKALA'] = 'placeholder-skala-packaging-key'
os.environ['TANK_API_KEY'] = 'placeholder-workspace-packaging-key'
tenant, user = '11111111-1111-1111-1111-111111111111', 'placeholder-owner'
seen = []
async def claim(*args):
    return True
async def respond(request):
    actor = await verify_assertion(request.headers[HEADER], key=os.environ['TANK_KEY_SKALA'],
        product='hermes', tenant_id=tenant, method=request.method,
        target=request.url.raw_path.decode('ascii'), body=request.content, consume_nonce=claim)
    assert actor.user_id == user
    assert request.method == 'GET' and request.url.path == '/records'
    seen.append(request)
    return httpx.Response(200, json={'memories': []})
async def check():
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = memory_client_for_skala(base_url='http://placeholder-hermes', http=http, user_id=user)
        assert await client.records(tenant) == []
    assert len(seen) == 1
asyncio.run(check())
'''
    result = subprocess.run([sys.executable, '-I', '-c', code, str(root / 'tank')],
                            cwd=root / 'tank', capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
