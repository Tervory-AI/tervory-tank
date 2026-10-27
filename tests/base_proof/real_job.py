"""Run the real Tank, Base worker and Workspace locally with offline external pages.

BASE_TEST_DATABASE_URL must name a local disposable PostgreSQL server with CREATE
DATABASE permission. Only public-page/DNS HTTP responses and Clerk are fixtures.
The applications, skills, collector, database and CSV route are unmodified.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[2]
PROOF = Path(__file__).resolve().parent


def port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


async def healthy(url: str, process: subprocess.Popen) -> None:
    async with httpx.AsyncClient() as client:
        for _ in range(120):
            assert process.poll() is None, f"Process exited before {url} was ready"
            try:
                if (await client.get(url, timeout=2)).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise AssertionError(f"Service did not become ready: {url}")


async def main() -> None:
    from playwright.async_api import async_playwright
    from base_product_fixtures import TENANT

    address = os.environ["BASE_TEST_DATABASE_URL"]
    parsed = urlsplit(address)
    assert parsed.hostname in {"127.0.0.1", "localhost"}, "Local fixture database only"
    name = "base_csv_proof_" + uuid.uuid4().hex[:12]
    admin = await asyncpg.connect(address)
    await admin.execute(f'CREATE DATABASE "{name}"')
    database = urlunsplit((parsed.scheme, parsed.netloc, "/" + name, "", ""))
    temporary = Path(tempfile.mkdtemp(prefix="base-real-job-"))
    output = Path(os.environ.get("BASE_PROOF_OUTPUT", str(temporary / "evidence")))
    output.mkdir(parents=True, exist_ok=True)
    processes, logs = [], []
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
            versions = {"normalize": "1.0.0", "resolve": "1.0.0", "find_site": "1.7.0", "scrape_site": "1.2.0",
                        "extract": "2.0.0", "contacts": "1.1.0", "socials": "1.0.1", "business_data": "2.0.0", "verify": "1.0.1"}
            for skill, version in versions.items():
                await conn.execute("UPDATE tank.skills SET state='retired' WHERE id=$1", "base." + skill)
                result = await conn.execute("UPDATE tank.skills SET state='approved' WHERE id=$1 AND version=$2", "base." + skill, version)
                assert result == "UPDATE 1", (skill, version)
        finally:
            await conn.close()
        room = temporary / "room"
        shutil.copytree(ROOT / "agents/base", room, ignore=shutil.ignore_patterns("__pycache__"))
        (room / "chassis").symlink_to(ROOT / "agents/_chassis/chassis", target_is_directory=True)
        room_env = {**env, "PYTHONPATH": str(room)}
        agent = start([sys.executable, str(__file__), "serve", "app:app", str(room_port)], room, "base-agent", room_env)
        await healthy(room_url + "/health", agent)

        workspace = Path(subprocess.check_output([sys.executable, str(PROOF / "workspace.py")], text=True).strip())
        web_env = {**env, "NEXT_TELEMETRY_DISABLED": "1",
                   "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==",
                   "CLERK_SECRET_KEY": "sk_test_dummy"}
        web = start(["node", str(workspace / "node_modules/next/dist/bin/next"), "dev", "--port", str(web_port)],
                    workspace, "workspace", web_env)
        web_url = f"http://localhost:{web_port}"
        await healthy(web_url + "/base", web)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            await page.goto(web_url + "/base", wait_until="networkidle", timeout=120000)
            await page.get_by_label("Business CSV").set_input_files({"name": "fixture-shop.csv", "mimeType": "text/csv",
                "buffer": b"name,state,city,phone,website\nFixture Shop,TX,Austin,+15125550101,https://shop.example/\n"})
            await page.get_by_role("button", name="Upload and verify", exact=True).first.click()
            await page.get_by_role("status").filter(has_text="Your list was received").wait_for(timeout=60000)
            async with httpx.AsyncClient(headers={"X-Tank-Key": "local-fixture"}, timeout=30) as client:
                params = {"tenant_id": str(TENANT)}
                conn = await asyncpg.connect(database)
                try:
                    for _ in range(120):
                        status = await conn.fetchval("SELECT status FROM agent_base.records WHERE tenant_id=$1", TENANT)
                        response = await client.get(tank_url + "/v1/base-product/records", params=params)
                        response.raise_for_status()
                        rows = response.json()["rows"]
                        if status in {"done", "failed"} and rows and rows[0]["fields"]["socials"]["verified"]:
                            break
                        await asyncio.sleep(1)
                    assert len(rows) == 1, rows
                    assert status == "done", status
                finally:
                    await conn.close()
                (output / "verified-records.json").write_text(json.dumps(rows, indent=2) + "\n")
            await page.get_by_role("button", name="View verified fields and sources").click()
            detail = page.locator('[aria-label="Verified fields"]')
            await detail.locator("dd p").filter(has_text="https://www.tiktok.com/@fixture-shop").wait_for(timeout=30000)
            await detail.scroll_into_view_if_needed()
            await page.screenshot(path=str(output / "real-job-1440.png"))
            async with page.expect_download() as pending:
                await page.locator('a[href*="metric=email_and_phone"]').first.click()
            await (await pending.value).save_as(str(output / "real-job.csv"))
            text = (output / "real-job.csv").read_text(encoding="utf-8-sig")
            exported = next(csv.DictReader(io.StringIO(text)))
            assert exported["tiktok"] == "https://www.tiktok.com/@fixture-shop"
            assert exported["facebook"] == "https://www.facebook.com/fixture-shop"
            assert exported["email"] == "info@shop.example"
            assert not any(mark in text for mark in "[]{}")
            for network in ("tiktok", "facebook"):
                assert exported[f"{network}_source_url"].startswith("https://shop.example/")
                assert exported[f"{network}_checked_at"]
            visible = await detail.locator("dd p").count()
            values = sum(len(exported[column].split("; ")) for column in exported
                         if column in {"email", "other_emails", "phone", "other_phones", "website", "other_websites",
                                       "facebook", "other_facebook", "tiktok", "other_tiktok"} and exported[column])
            assert visible == values == 5, (visible, values)
            await page.set_viewport_size({"width": 375, "height": 900})
            await page.screenshot(path=str(output / "real-job-375.png"))
            await browser.close()
            result = {"job": "CSV upload through Workspace -> real Tank -> real Base worker -> Workspace download",
                      "status": status, "verified_values_on_page": visible, "verified_values_in_csv": values,
                      "tiktok": exported["tiktok"], "facebook": exported["facebook"], "fixture": "local, fixture page"}
            (output / "real-job-output.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
    finally:
        import signal
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for log in logs:
            log.close()
        startup = (output / "tank-startup.log").read_text()
        print("Real Tank startup tail:\n" + "\n".join(startup.splitlines()[:8]))
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        from external_pages import install
        install()
        import uvicorn
        uvicorn.run(sys.argv[2], host="127.0.0.1", port=int(sys.argv[3]), app_dir=os.getcwd())
    else:
        asyncio.run(main())
