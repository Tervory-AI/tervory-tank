"""A fresh process proves fixtures cannot determine the paid client's base class."""
import subprocess
import sys
from pathlib import Path


def test_paid_http_client_is_initialized_before_offline_transport_patches():
    root = Path(__file__).resolve().parents[1]
    script = r'''import asyncio
import runpy
import sys
import httpx

assert "paid_http" not in sys.modules
real_client = httpx.AsyncClient
runpy.run_path("tests/conftest.py")
class FixtureClient:
    def __init__(self, **kwargs):
        raise AssertionError("offline room double must not become Tank's client base")
httpx.AsyncClient = FixtureClient
import paid_http
assert paid_http.Client.__bases__ == (real_client,)
async def check():
    calls = []
    def answer(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"ok": True})
    async with paid_http.Client(transport=httpx.MockTransport(answer)) as client:
        response = await client.get("http://fixture.invalid/proof")
        assert response.json() == {"ok": True}
    assert calls == ["/proof"] and client.is_closed
asyncio.run(check())
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=root,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
