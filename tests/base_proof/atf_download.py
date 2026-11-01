"""Real Tank/Base/Workspace proof of first download, saved-set protection and 403.

Only external HTTP and Clerk in a temporary Workspace are fixtures. The complete
saved ATF file is served unchanged; no application route or repository is mocked.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx

from real_job import healthy, port
from reference_adopt import stop

ROOT = Path(__file__).resolve().parents[2]
PROOF = Path(__file__).resolve().parent


def offline_reads() -> None:
    from test_base_atf_download import FILE_URL, LISTING, REFERENCE_URL, saved_file
    original = httpx.AsyncClient._transport_for_url
    content = saved_file()

    def response(request):
        url = str(request.url)
        if url in {REFERENCE_URL, FILE_URL}:
            assert request.headers["user-agent"] == "Tervory/1.0 (+https://tervory.com)"
            assert "x-tank-key" not in request.headers
            status = 403 if os.environ["BASE_ATF_FIXTURE_CASE"] == "blocked" else 200
            with Path(os.environ["BASE_ATF_READ_LOG"]).open("a") as log:
                log.write(json.dumps({"url": url, "status": status, "user_agent": request.headers["user-agent"],
                                      "time": time.monotonic()}) + "\n")
            return httpx.Response(status, content=b"" if status == 403 else LISTING.encode() if url == REFERENCE_URL else content)
        return httpx.Response(503, text="External service unavailable in local fixture proof")

    fixture = httpx.MockTransport(response)

    def transport(self, url):
        return original(self, url) if url.host in {"127.0.0.1", "localhost", "::1"} else fixture

    httpx.AsyncClient._transport_for_url = transport


async def run_case(case: str, playwright, output: Path) -> dict:
    from base_product_fixtures import TENANT, OTHER
    from test_base_reference_adopt import seed
    from test_base_atf_download import FILE_URL, REFERENCE_URL, SAVED_SHA

    address = os.environ["BASE_TEST_DATABASE_URL"]
    parsed = urlsplit(address)
    assert parsed.hostname in {"127.0.0.1", "localhost"}, "Local fixture database only"
    name = "base_download_proof_" + uuid.uuid4().hex[:12]
    admin = await asyncpg.connect(address)
    await admin.execute(f'CREATE DATABASE "{name}"')
    database = urlunsplit((parsed.scheme, parsed.netloc, "/" + name, "", ""))
    temporary = Path(tempfile.mkdtemp(prefix="base-atf-download-"))
    output.mkdir(parents=True, exist_ok=True)
    reads = output / "atf-reads.jsonl"
    reads.write_text("")
    processes, logs = [], []
    workspace = None
    tank_port, room_port, web_port = port(), port(), port()
    tank_url, room_url = f"http://127.0.0.1:{tank_port}", f"http://127.0.0.1:{room_port}"
    env = {**os.environ, "DATABASE_URL": database, "TANK_API_KEY": "local-fixture", "TANK_KEY_BASE": "local-room-fixture",
           "TANK_KEY": "local-room-fixture", "TANK_URL": tank_url, "BASE_AGENT_URL": room_url,
           "LITELLM_MASTER_KEY": "local-fixture", "LITELLM_URL": "http://127.0.0.1:9",
           "REDIS_URL": "redis://127.0.0.1:9/0", "PYTHONUNBUFFERED": "1", "AGENT_NAME": "base",
           "DATA_DIR": str(temporary / "data"), "SKILLS_DIR": str(ROOT / "tank/skills"),
           "BASE_ATF_FIXTURE_CASE": case, "BASE_ATF_READ_LOG": str(reads),
           "PYTHONPATH": f"{ROOT}:{ROOT / 'tank'}:{ROOT / 'tests'}"}

    def start(command, cwd, label, settings):
        log = (output / f"{label}.log").open("w")
        logs.append(log)
        process = subprocess.Popen(command, cwd=cwd, env=settings, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        return process

    try:
        before = []
        if case == "saved":
            conn = await asyncpg.connect(database)
            try:
                await conn.execute((ROOT / "tank/schema.sql").read_text())
                async with conn.transaction():
                    await seed(conn)
                before = [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")]
            finally:
                await conn.close()
        tank_command = [sys.executable, str(__file__), "serve", "main:app", str(tank_port)]
        tank = start(tank_command, ROOT / "tank", "tank-startup", env)
        await healthy(tank_url + "/health", tank)
        room = temporary / "room"
        shutil.copytree(ROOT / "agents/base", room, ignore=shutil.ignore_patterns("__pycache__"))
        (room / "chassis").symlink_to(ROOT / "agents/_chassis/chassis", target_is_directory=True)
        room_env = {**env, "PYTHONPATH": f"{room}:{ROOT}:{ROOT / 'tank'}:{ROOT / 'tests'}"}
        room_command = [sys.executable, str(__file__), "serve", "app:app", str(room_port)]
        agent = start(room_command, room, "base-agent", room_env)
        await healthy(room_url + "/health", agent)
        workspace = Path(subprocess.check_output([sys.executable, str(PROOF / "workspace.py")], text=True).strip())
        web = start(["node", str(workspace / "node_modules/next/dist/bin/next"), "dev", "--port", str(web_port)], workspace,
                    "workspace", {**env, "NEXT_TELEMETRY_DISABLED": "1",
                                  "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==",
                                  "CLERK_SECRET_KEY": "sk_test_dummy"})
        web_url = f"http://localhost:{web_port}"
        await healthy(web_url + "/base", web)
        browser = await playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto(web_url + "/base", wait_until="networkidle", timeout=120000)
        section = page.get_by_role("region", name="Reference licences and verified results")
        if case == "blocked":
            await section.get_by_role("alert").filter(has_text="ATF did not allow the read (HTTP 403). Automatic checks have stopped.").wait_for(timeout=120000)
            assert not await page.get_by_role("button", name="Start from reference", exact=True).is_enabled()
            # A fresh agent and Tank must honour the database stop without any
            # further outbound requests, even if ATF would now return a file.
            stop(agent)
            stop(tank)
            recovered_env = {**env, "BASE_ATF_FIXTURE_CASE": "empty"}
            agent = start(room_command, room, "base-agent-restarted", {**room_env, "BASE_ATF_FIXTURE_CASE": "empty"})
            await healthy(room_url + "/health", agent)
            tank = start(tank_command, ROOT / "tank", "tank-restarted", recovered_env)
            await healthy(tank_url + "/health", tank)
        else:
            count = 77611 if case == "empty" else 3
            await section.get_by_text(f"{count:,} ATF licences", exact=True).wait_for(timeout=180000)
            expected_date = "1 Sept 2025" if case == "empty" else "1 Sept 2026"
            assert expected_date in await section.inner_text()
            source = await section.get_by_role("link", name="Official source", exact=True).get_attribute("href")
            assert source == (FILE_URL if case == "empty" else REFERENCE_URL)
            assert await page.get_by_role("button", name="Start from reference", exact=True).is_enabled()
        # Exercise one more normal background pass before inspecting requests.
        await asyncio.sleep(16)
        for width, height in ((1440, 1000), (375, 900)):
            await page.set_viewport_size({"width": width, "height": height})
            await section.get_by_role("heading", name="Reference licences", exact=True).scroll_into_view_if_needed()
            await page.screenshot(path=str(output / f"reference-{width}.png"))
        async with httpx.AsyncClient(headers={"X-Tank-Key": "local-fixture"}, timeout=30) as client:
            response = await client.get(web_url + "/base/product/reference")
            response.raise_for_status()
            ref = response.json()
            for tenant in (TENANT, OTHER):
                shared = (await client.get(tank_url + "/v1/base-product/reference", params={"tenant_id": str(tenant)})).json()
                assert shared["total_all"] == ref["total_all"]
        calls = [json.loads(line) for line in reads.read_text().splitlines()]
        if case == "empty":
            assert [call["url"] for call in calls] == [REFERENCE_URL, FILE_URL]
            assert calls[1]["time"] - calls[0]["time"] >= 3
            assert ref["file"]["sha256"] == SAVED_SHA and ref["total_all"] == 77611
            assert not ref["file"]["adopted"]
        elif case == "saved":
            assert all(call["url"] == REFERENCE_URL for call in calls), "No file download for a saved set"
            assert ref["file"]["adopted"] and ref["total_all"] == 3 and ref["duplicate_count"] == 1
        else:
            assert len(calls) == 1 and calls[0]["status"] == 403
            assert ref["file"] is None and ref["refresh"]["status"] == "blocked"
        conn = await asyncpg.connect(database)
        try:
            assert [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")] == before
            assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_files") == (0 if case == "blocked" else 1)
        finally:
            await conn.close()
        await browser.close()
        result = {"case": case, "fixture": "local, fixture page", "licences": ref["total_all"],
                  "published_on": ref["file"]["published_on"] if ref["file"] else None,
                  "source_url": ref["file"]["source_url"] if ref["file"] else None,
                  "check": ref["refresh"], "atf_requests": len(calls),
                  "file_downloads": sum(call["url"] == FILE_URL for call in calls), "saved_rows_unchanged": True,
                  "shared_reference_for_both_tenants": True, "blocked_stop_survives_restarts": case == "blocked"}
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
        return result
    finally:
        for process in reversed(processes):
            stop(process)
        for log in logs:
            log.close()
        startup = (output / "tank-startup.log").read_text()
        print(f"Real Tank startup tail ({case}):\n" + "\n".join(startup.splitlines()[:10]), flush=True)
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
        if workspace:
            shutil.rmtree(workspace.parent)
        shutil.rmtree(temporary)


async def main() -> None:
    from playwright.async_api import async_playwright
    output = Path(os.environ["BASE_PROOF_OUTPUT"]).resolve()
    async with async_playwright() as playwright:
        results = [await run_case(case, playwright, output / case) for case in ("empty", "saved", "blocked")]
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        offline_reads()
        import uvicorn
        uvicorn.run(sys.argv[2], host="127.0.0.1", port=int(sys.argv[3]), app_dir=os.getcwd())
    else:
        asyncio.run(main())
