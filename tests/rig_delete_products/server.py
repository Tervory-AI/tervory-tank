"""Local-only proof: real Tank, Rig routes and Postgres; no production credentials."""
import asyncio
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "agents/rig"), str(ROOT / "agents/_chassis")]
from rigbox.retailer import Retailer
from rigbox.retailer_server import create_retailer_app
from rigbox.service import Service, hash_key
from rigbox.store import PgStore
from rigbox.api import mount

TENANT = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
# Public non-secret test markers, accepted only by these loopback proof processes.
MARKER = "offline-proof-only"
PUBLIC = "rk_pub_offline_proof"


def database_url():
    value = os.environ["RIG_DELETE_PROOF_DATABASE_URL"]
    parsed = urlsplit(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.endswith("_test") or parsed.password:
        raise RuntimeError("Use a passwordless, disposable loopback _test database")
    return value


def create_room():
    app = create_retailer_app(Service(None))
    mount(app)
    @asynccontextmanager
    async def lifespan(app):
        pool = await asyncpg.create_pool(database_url())
        app.state.rig = Service(PgStore(pool))
        try:
            yield
        finally:
            await pool.close()
    app.router.lifespan_context = lifespan
    return app


async def seed():
    pool = await asyncpg.create_pool(database_url())
    try:
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()
        if await store.products(TENANT) or await store.deleted_skus(TENANT):
            raise RuntimeError("Proof requires a fresh database")
        retailer = Retailer(Service(store))
        rows = [{"sku": sku, "name": name, "brand": "Workshop", "category": "furniture", "price": price,
                 "quantity": 1, "image_url": "https://example.com/catalogue.png", "family": "furniture"}
                for sku, name, price in [("D001", "Walnut desk", "14474"), ("C002", "Oak chair", "850"), ("S003", "Book shelf", "2400")]]
        for tenant in (TENANT, OTHER):
            result = await retailer.import_file(tenant, {"provider": "catalogue", "site": "https://example.com", "currency": "ZAR", "price_basis": "selling", "rows": rows,
                                                       "metadata": {"fits": [{"part_sku": "C002", "fits_sku": "D001", "note": "Catalogue fit"}]}})
            assert result["ok"]
        await store.add_quote(TENANT, "history-kept", {"sku": "D001", "price": 14474}, {})
        await store.put_key(TENANT, hash_key(PUBLIC), "publishable", ["https://shop.example"])
    finally:
        await pool.close()


def wait_ready(url, child):
    for _ in range(200):
        if child.poll() is not None:
            raise RuntimeError("Proof service exited; read startup.txt")
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.1)
    raise RuntimeError("Proof service did not become ready")


def run():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    asyncio.run(seed())
    env = {**os.environ, "DATABASE_URL": database_url(), "TANK_API_KEY": MARKER, "RIG_RETAILER_KEY": MARKER,
           "LITELLM_MASTER_KEY": MARKER, "LITELLM_BASE": "http://127.0.0.1:1", "REDIS_URL": "redis://127.0.0.1:1/0",
           "TERVORY_ADMIN_USER_IDS": "local-owner", "TANK_URL": "http://127.0.0.1:8054",
           "PYTHONPATH": os.pathsep.join([str(ROOT / "tests/rig_delete_products"), str(ROOT / "tank"), str(ROOT / "agents/rig"), str(ROOT / "agents/_chassis")])}
    children = []
    with (out / "startup.txt").open("w") as log:
        try:
            room = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:create_room", "--factory", "--host", "127.0.0.1", "--port", "8003", "--no-access-log"], env=env, cwd=ROOT, stdout=log, stderr=log)
            children.append(room)
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", 8003), timeout=.1):
                        break
                except OSError:
                    if room.poll() is not None:
                        raise RuntimeError("Room exited")
                    time.sleep(.1)
            # Resolve the real private corridor to this cloud machine's loopback.
            # No Tank function, router, auth check, HTTP client or DB is replaced.
            boot = "import socket; original=socket.getaddrinfo; socket.getaddrinfo=lambda host,*a,**k: original('127.0.0.1' if host in ('agent-rig',b'agent-rig') else host,*a,**k); import uvicorn; uvicorn.run('main:app',host='127.0.0.1',port=8054,access_log=False,loop='asyncio')"
            tank = subprocess.Popen([sys.executable, "-c", boot], cwd=ROOT / "tank", env=env, stdout=log, stderr=log)
            children.append(tank)
            wait_ready("http://127.0.0.1:8054/health", tank)
            check = httpx.get("http://127.0.0.1:8054/v1/access/rig/admin", headers={"x-tank-key": MARKER, "x-tervory-user": "local-owner", "x-tervory-tenant": TENANT}, trust_env=False)
            print("Real Tank panel:", check.status_code, check.json().get("detail", "ok"), flush=True)
            subprocess.run(["node", "tests/rig_delete_products/browser.cjs", str(out)], cwd=ROOT, env=env, check=True)
        finally:
            for child in reversed(children):
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    run()
