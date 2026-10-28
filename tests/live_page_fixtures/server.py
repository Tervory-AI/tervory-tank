"""Local proof corridor: real Tank/Market Lab; no Tank replacements or live feeds."""
from __future__ import annotations
import asyncio
import http.client
import os
import secrets
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'agents/market_lab'), str(ROOT / 'agents/_chassis')]
from fixture_proof.server import database_url, free_port, seed, wait_ready

@contextmanager
def services(api_port: int = 8046, log=None, *, history: bool = False):
    database_url()
    sys.path[:0] = [str(ROOT / "agents/market_lab"), str(ROOT / "agents/_chassis")]
    asyncio.run(seed(history=history))
    room_port = free_port()

    class Corridor(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log request headers or credentials.

        def forward(self):
            destination = urlsplit(self.path)
            if destination.scheme != "http" or destination.netloc != "agent-market-lab:8000" or not (destination.path.startswith("/market/") or destination.path == "/quarantine"):
                self.send_error(502, "Only the local Market Lab corridor is available")
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            connection = http.client.HTTPConnection("127.0.0.1", room_port, timeout=30)
            try:
                connection.request(self.command, destination.path, body, {"content-type": "application/json", "x-tank-key": self.headers.get("x-tank-key", "")})
                response = connection.getresponse()
                data = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            finally:
                connection.close()

        do_GET = do_POST = forward

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Corridor)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "tank"), str(ROOT / "agents/market_lab"), str(ROOT / "agents/_chassis")]),
           "TANK_API_KEY": secrets.token_hex(32), "TANK_KEY_MARKET_LAB": secrets.token_hex(32),
           "LITELLM_MASTER_KEY": secrets.token_hex(32), "REDIS_URL": "redis://127.0.0.1:1/0",
           "TERVORY_ADMIN_USER_IDS": "proof-owner", "TANK_URL": f"http://127.0.0.1:{api_port}", "NEXT_TELEMETRY_DISABLED": "1"}
    for name in list(env):
        if name.startswith(("CLERK_", "NEXT_PUBLIC_CLERK_")) or name in {"FRED_API_KEY", "CENSUS_API_KEY", "LEGISCAN_API_KEY", "EIA_API_KEY", "NOAA_TOKEN", "FEEDS_FIXTURES"}:
            env.pop(name)
    room_env = {**env, "TANK_KEY": env["TANK_KEY_MARKET_LAB"]}
    # Local corridor forwarding, not an external network bypass. All other
    # destinations are refused by Corridor; HTTPS retains the managed proxy.
    tank_env = {**env, "HTTP_PROXY": f"http://127.0.0.1:{proxy.server_port}", "http_proxy": f"http://127.0.0.1:{proxy.server_port}", "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    children = []
    try:
        room = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(room_port), "--lifespan", "off", "--no-access-log"], cwd=ROOT / "agents/market_lab", env=room_env, stdout=log, stderr=log)
        children.append(room)
        wait_ready(f"http://127.0.0.1:{room_port}/openapi.json", room)
        tank = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"], cwd=ROOT / "tank", env=tank_env, stdout=log, stderr=log)
        children.append(tank)
        wait_ready(f"http://127.0.0.1:{api_port}/health", tank)
        yield env
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=2)
