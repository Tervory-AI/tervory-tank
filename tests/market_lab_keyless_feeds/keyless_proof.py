"""Real Tank, real room worker and local Postgres; saved publisher responses only."""
from __future__ import annotations

import argparse
import asyncio
import http.client
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "agents/market_lab"), str(ROOT / "agents/_chassis")]
from fixture_proof.server import database_url, free_port, wait_ready

FEED = "https://www.federalreserve.gov/feeds/press_all.xml"


async def prepare_database():
    from chassis.db import ensure_schema
    from core.ledger import PostgresLedger
    conn = await asyncpg.connect(database_url())
    try:
        await ensure_schema(conn, "market_lab")
        await PostgresLedger(conn).apply_schema()
    finally:
        await conn.close()


@contextmanager
def services(output):
    asyncio.run(prepare_database())
    output.mkdir(parents=True, exist_ok=True)
    room_port, tank_port = free_port(), free_port()

    class Corridor(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def forward(self):
            target = urlsplit(self.path)
            if target.scheme != "http" or target.netloc != "agent-market-lab:8000" or not target.path.startswith("/market/"):
                self.send_error(502)
                return
            conn = http.client.HTTPConnection("127.0.0.1", room_port, timeout=120)
            try:
                conn.request(self.command, target.path + ("?" + target.query if target.query else ""),
                    self.rfile.read(int(self.headers.get("content-length", "0"))),
                    {"content-type": self.headers.get("content-type", "application/json"), "x-tank-key": self.headers.get("x-tank-key", "")})
                response = conn.getresponse()
                data = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            finally:
                conn.close()

        do_GET = do_POST = do_PUT = do_DELETE = forward

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Corridor)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    env = {name: value for name, value in os.environ.items()
           if not name.startswith(("TANK_KEY", "CLERK_", "NEXT_PUBLIC_CLERK_", "R2_"))}
    for name in ("CENSUS_API_KEY", "FRED_API_KEY", "EIA_API_KEY", "NOAA_TOKEN", "LEGISCAN_API_KEY", "USPTO_API_KEY", "FEEDS_FIXTURES"):
        env.pop(name, None)
    env.update(TANK_API_KEY="placeholder-keyless-workspace-key", TANK_KEY_MARKET_LAB="placeholder-keyless-room-key",
        LITELLM_MASTER_KEY="placeholder-keyless-unused-provider-key", TANK_REGION="us-east", TERVORY_ADMIN_USER_IDS="",
        REDIS_URL="redis://127.0.0.1:1/0", TANK_URL=f"http://127.0.0.1:{tank_port}", NEXT_TELEMETRY_DISABLED="1",
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==",
        PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in ("tank", "agents/market_lab", "agents/_chassis", "tests/market_lab_keyless_feeds")))
    proxy_env = {"HTTP_PROXY": f"http://127.0.0.1:{proxy.server_port}", "http_proxy": f"http://127.0.0.1:{proxy.server_port}",
                 "NO_PROXY": "localhost,127.0.0.1", "no_proxy": "localhost,127.0.0.1"}
    children = []
    with (output / "services.log").open("w") as log:
        try:
            room = subprocess.Popen([sys.executable, "-m", "uvicorn", "keyless_room:app", "--host", "127.0.0.1", "--port", str(room_port), "--no-access-log"],
                cwd=ROOT, env={**env, **proxy_env, "TANK_KEY": env["TANK_KEY_MARKET_LAB"], "AGENT_NAME": "market_lab", "DATA_DIR": str(output / "room")}, stdout=log, stderr=log)
            children.append(room)
            wait_ready(f"http://127.0.0.1:{room_port}/health", room)
            tank = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(tank_port), "--no-access-log"],
                cwd=ROOT / "tank", env={**env, **proxy_env}, stdout=log, stderr=log)
            children.append(tank)
            wait_ready(env["TANK_URL"] + "/health", tank)
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


async def grants(owner, other):
    conn = await asyncpg.connect(database_url())
    try:
        for tenant in (owner, other):
            await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'market_lab','local-proof-user')", UUID(tenant))
    finally:
        await conn.close()


def check(env, output, *, browser=False):
    owner, other = str(uuid4()), str(uuid4())
    asyncio.run(grants(owner, other))
    from keyless_browser import session
    with httpx.Client(base_url=env["TANK_URL"], trust_env=False, timeout=30) as client, session(env, owner, output) if browser else nullcontext(None) as page:
        def vault(method, path, *, tenant=owner, data=None):
            headers = {"x-tank-key": env["TANK_API_KEY"], "x-tervory-user": "local-proof-user", "x-tervory-squad": "market_lab"}
            return client.request(method, "/v1/vaults/lab.vault/" + path, headers=headers,
                **({"json": {"tenant_id": tenant, **data}} if data is not None else {"params": {"tenant_id": tenant}}))

        def market(operation, *, tenant=owner, **data):
            return client.post("/v1/market-lab/" + operation, json={"tenant_id": tenant, **data}, headers={"x-tank-key": env["TANK_API_KEY"]})

        assert client.get("/v1/vaults/lab.vault/plugins", params={"tenant_id": owner}).status_code == 401
        assert vault("POST", "links", data={"url": "http://127.0.0.1/private", "label": "", "frequency": "daily"}).status_code >= 400
        if page:
            page.get_by_role("button", name="Plugins", exact=True).click()
            page.get_by_role("tab", name="Source links", exact=True).click()
            page.locator('input[name="link"]').fill(FEED)
            page.locator('input[name="label"]').fill("Federal Reserve")
            page.get_by_role("button", name="Add link", exact=True).click()
            page.get_by_text("Saved.", exact=True).wait_for()
        else:
            response = vault("POST", "links", data={"url": FEED, "label": "Federal Reserve", "frequency": "daily"})
            assert response.status_code == 200, response.text
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            response = vault("GET", "plugins")
            assert response.status_code == 200, response.text
            links = response.json()["links"]
            if links and links[0]["status"] == "checked":
                break
            time.sleep(.2)
        else:
            raise AssertionError("the real worker did not finish the queued feed import")
        ident = links[0]["id"]
        assert links[0]["last_checked"]
        assert vault("GET", "plugins", tenant=other).json()["links"] == []
        overview = market("overview").json()
        feed = next(row for row in overview["feeds"] if row["id"] == "rss_" + ident)
        assert feed["rows"] == 20 and feed["state"] == "on"
        doc_id = feed["document_id"]
        doc = market("document", document_id=doc_id).json()
        assert len(doc["events"]) == 20 and doc["fetched_at"]
        assert all(row["url"].startswith("https://www.federalreserve.gov/") and row["fetched_at"] for row in doc["events"])
        assert market("document", tenant=other, document_id=doc_id).status_code == 404
        assert not any(row["id"].startswith("rss_") for row in market("overview", tenant=other).json()["feeds"])
        assert market("ask", question="Federal Reserve").json()["facts"]
        # Tenant B cannot remove A's subscription or its evidence.
        assert vault("DELETE", "links/" + ident, tenant=other).status_code == 200
        assert market("document", document_id=doc_id).status_code == 200
        if page:
            page.get_by_role("button", name="Close", exact=True).click()
            page.get_by_text("20 stored observations", exact=True).wait_for(timeout=30000)
            page.screenshot(path=str(output / "overview.png"), full_page=True)
            page.locator(f'a[href="/market-lab/sources/{doc_id}"]').click()
            page.get_by_role("link", name="Original notice", exact=True).first.wait_for()
            page.screenshot(path=str(output / "source.png"), full_page=True)
        assert vault("DELETE", "links/" + ident).status_code == 200
        assert vault("GET", "plugins").json()["links"] == []
        assert market("document", document_id=doc_id).status_code == 404
        result = {"proof": "local, fixture page", "tank": "real app startup and HTTP routes", "worker": "real room scheduler and job worker",
            "rss_items": 20, "source_links": 20, "retrieval_times": 20, "tenant_isolation": "passed",
            "private_url_rejected": True, "delete_stops_subscription_and_removes_evidence": True,
            "model_calls": 0, "browser_add_link": bool(page)}
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    with services(args.output) as env:
        check(env, args.output, browser=args.browser)
