"""Real Tank -> Base reference adoption -> Workspace proof, with local fixtures.

Run with PYTHONPATH=tank:tests and BASE_TEST_DATABASE_URL pointing at a local
PostgreSQL server with CREATE DATABASE permission. No live reads or sign-in.
Only external HTTP responses and Clerk in a temporary Workspace are fixtures.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx

from real_job import healthy, port

ROOT = Path(__file__).resolve().parents[2]
PROOF = Path(__file__).resolve().parent


def offline_reads() -> None:
    """Keep the real reference routes; replace only their external HTTP boundary."""
    original = httpx.AsyncClient._transport_for_url

    def response(request: httpx.Request) -> httpx.Response:
        if request.url.host in {"atf.gov", "www.atf.gov"}:
            return httpx.Response(200, text='<html><a href="/0926-ffl-list-complete.txt">September 2026 complete list</a></html>',
                                  headers={"content-type": "text/html"})
        return httpx.Response(503, text="External service unavailable in local fixture proof")

    fixture = httpx.MockTransport(response)

    def transport(self, url):
        return original(self, url) if url.host in {"127.0.0.1", "localhost", "::1"} else fixture

    httpx.AsyncClient._transport_for_url = transport


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


async def main() -> None:
    from playwright.async_api import async_playwright
    from base_product_fixtures import TENANT, OTHER
    from test_base_reference_adopt import seed

    address = os.environ["BASE_TEST_DATABASE_URL"]
    parsed = urlsplit(address)
    assert parsed.hostname in {"127.0.0.1", "localhost"}, "Local fixture database only"
    name = "base_adopt_proof_" + uuid.uuid4().hex[:12]
    admin = await asyncpg.connect(address)
    await admin.execute(f'CREATE DATABASE "{name}"')
    database = urlunsplit((parsed.scheme, parsed.netloc, "/" + name, "", ""))
    temporary = Path(tempfile.mkdtemp(prefix="base-reference-adopt-"))
    output = Path(os.environ.get("BASE_PROOF_OUTPUT", str(temporary / "evidence")))
    output.mkdir(parents=True, exist_ok=True)
    processes, logs = [], []
    workspace = None
    tank_port, room_port, web_port = port(), port(), port()
    tank_url, room_url = f"http://127.0.0.1:{tank_port}", f"http://127.0.0.1:{room_port}"
    env = {**os.environ, "DATABASE_URL": database, "TANK_API_KEY": "local-fixture", "TANK_KEY_BASE": "local-room-fixture",
           "TANK_KEY": "local-room-fixture", "TANK_URL": tank_url, "BASE_AGENT_URL": room_url,
           "LITELLM_MASTER_KEY": "local-fixture", "LITELLM_URL": "http://127.0.0.1:9",
           "REDIS_URL": "redis://127.0.0.1:9/0", "PYTHONUNBUFFERED": "1", "AGENT_NAME": "base",
           "DATA_DIR": str(temporary / "data"), "SKILLS_DIR": str(ROOT / "tank/skills")}

    def start(command, cwd, label, settings):
        log = (output / f"{label}.log").open("w")
        logs.append(log)
        process = subprocess.Popen(command, cwd=cwd, env=settings, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append(process)
        return process

    try:
        tank = start([sys.executable, str(__file__), "serve", "main:app", str(tank_port)], ROOT / "tank", "tank-startup", env)
        await healthy(tank_url + "/health", tank)
        conn = await asyncpg.connect(database)
        try:
            async with conn.transaction():
                ids = await seed(conn)
            before = [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")]
        finally:
            await conn.close()

        room = temporary / "room"
        shutil.copytree(ROOT / "agents/base", room, ignore=shutil.ignore_patterns("__pycache__"))
        (room / "chassis").symlink_to(ROOT / "agents/_chassis/chassis", target_is_directory=True)
        room_env = {**env, "PYTHONPATH": str(room)}
        command = [sys.executable, str(__file__), "serve", "app:app", str(room_port)]
        agent = start(command, room, "base-agent-rejected", {**room_env, "TANK_KEY": "deliberately-wrong-fixture-key"})
        await healthy(room_url + "/health", agent)

        workspace = Path(subprocess.check_output([sys.executable, str(PROOF / "workspace.py")], text=True).strip())
        web = start(["node", str(workspace / "node_modules/next/dist/bin/next"), "dev", "--port", str(web_port)], workspace,
                    "workspace", {**env, "NEXT_TELEMETRY_DISABLED": "1",
                                  "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==",
                                  "CLERK_SECRET_KEY": "sk_test_dummy"})
        web_url = f"http://localhost:{web_port}"
        await healthy(web_url + "/base", web)
        async with async_playwright() as playwright, httpx.AsyncClient(headers={"X-Tank-Key": "local-fixture"}, timeout=30) as client:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            await page.goto(web_url + "/base", wait_until="networkidle", timeout=120000)
            message = "The reference could not be loaded: The Base reference service returned HTTP 401."
            alert = page.get_by_role("alert").filter(has_text=message)
            await alert.wait_for(timeout=60000)
            section = page.get_by_role("region", name="Reference licences and verified results")
            for width, height in ((1440, 1000), (375, 900)):
                await page.set_viewport_size({"width": width, "height": height})
                await section.scroll_into_view_if_needed()
                await alert.scroll_into_view_if_needed()
                await page.screenshot(path=str(output / f"reference-failed-{width}.png"))
            failed = (await client.get(web_url + "/base/product/reference")).json()
            assert failed["file"] is None and failed["total_all"] == 0 and failed["refresh"]["message"] == message
            (output / "reference-failed.json").write_text(json.dumps(failed, indent=2) + "\n")

            # Recover through the next normal 15-second background pass, without
            # calling adopt directly or restarting Tank or Workspace.
            stop(agent)
            agent = start(command, room, "base-agent-recovered", room_env)
            await healthy(room_url + "/health", agent)
            await section.get_by_text("3 ATF licences", exact=True).wait_for(timeout=90000)
            duplicate = section.get_by_text("1 duplicate row was found. The newest row for each licence is used.", exact=True)
            await duplicate.wait_for(timeout=30000)
            assert await page.get_by_role("button", name="Start from reference", exact=True).is_enabled()
            assert await alert.count() == 0
            for width, height in ((1440, 1000), (375, 900)):
                await page.set_viewport_size({"width": width, "height": height})
                await section.get_by_role("heading", name="Reference licences", exact=True).scroll_into_view_if_needed()
                await page.screenshot(path=str(output / f"reference-loaded-{width}.png"))
            loaded = (await client.get(web_url + "/base/product/reference")).json()
            assert loaded["total_all"] == 3 and loaded["duplicate_count"] == 1 and loaded["collectors"] == 1
            assert loaded["selected"] == 2 and loaded["refresh"]["status"] == "current"
            for tenant in (TENANT, OTHER):
                shared = (await client.get(tank_url + "/v1/base-product/reference", params={"tenant_id": str(tenant)})).json()
                assert shared["total_all"] == 3 and shared["duplicate_count"] == 1
                assert any(row["name"] == "Newest Fixture Business" for row in shared["rows"])
            (output / "reference-loaded.json").write_text(json.dumps(loaded, indent=2) + "\n")
            conn = await asyncpg.connect(database)
            try:
                assert [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")] == before
                assert await conn.fetchval("SELECT legacy_record_id FROM tank.base_reference_entries WHERE licence_key='5-74-00001'") == ids[1]
                assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_files") == 1
            finally:
                await conn.close()
            await browser.close()
            result = {"job": "Saved platform rows -> real Tank background adoption -> real Base FFL route -> real Workspace",
                      "fixture": "local, fixture page", "failure_http_status": 401, "failure_on_page": message,
                      "recovered_without_restarting_tank": True, "platform_source_rows": 4,
                      "reference_licences": 3, "duplicate_rows": 1, "collectors": 1, "default_batch_licences": 2,
                      "newest_row_kept": True, "source_rows_unchanged": True, "shared_reference_for_both_tenants": True,
                      "atf_header_spellings": ["PREMISE_*", "prem_*", "prem *"], "latest_check": loaded["refresh"]["status"]}
            (output / "reference-output.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
    finally:
        for process in reversed(processes):
            stop(process)
        for log in logs:
            log.close()
        startup = (output / "tank-startup.log").read_text()
        print("Real Tank startup tail:\n" + "\n".join(startup.splitlines()[:10]))
        print("Reference failure log:\n" + "\n".join(line for line in startup.splitlines() if "reference could not" in line))
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
        if workspace:
            shutil.rmtree(workspace.parent)
        if not output.is_relative_to(temporary):
            shutil.rmtree(temporary)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        offline_reads()
        import uvicorn
        uvicorn.run(sys.argv[2], host="127.0.0.1", port=int(sys.argv[3]), app_dir=os.getcwd())
    else:
        asyncio.run(main())
