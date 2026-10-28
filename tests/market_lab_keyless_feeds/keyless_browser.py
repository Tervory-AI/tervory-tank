"""An isolated Next wrapper around the unchanged production components/actions.

Only identity is supplied locally, in a temporary directory; no sign-in or
production authentication code is changed. Screens carry the fixture label.
"""
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from fixture_proof.run import prepare, WORKSPACE
from fixture_proof.server import free_port, wait_ready


@contextmanager
def session(env, owner, output):
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix="market-keyless-browser-") as raw:
        folder = Path(raw)
        prepare(folder)
        # Existing wrapper markup and source-page component, with this test's
        # owner rather than the older proof's fixed tenant.
        for path in (folder / "app").rglob("*.tsx"):
            path.write_text(path.read_text().replace("00000000-0000-0000-0000-000000000905", owner))
        identity = folder / "local-identity.ts"
        identity.write_text('export async function activeTenant(){return ' + json.dumps({
            "tenantId": owner, "orgId": "org_local_fixture", "orgName": "Local fixture workspace", "userId": "local-proof-user"
        }) + ';}\n')
        (folder / "next.config.mjs").write_text('export default {experimental:{externalDir:true},devIndicators:false,webpack(config){config.resolve.alias={"@/lib/tenant$":'
            + json.dumps(str(identity)) + ',...config.resolve.alias,"@":' + json.dumps(str(WORKSPACE)) + '};return config;}};')
        page = folder / "app/market-lab/page.tsx"
        page.write_text(f'''import {{MarketLabView}} from "@/app/market-lab/view";
import {{loadMarketLab}} from "@/app/market-lab/load";
import {{loadLabPlugins}} from "@/app/market-lab/vault-server";
import {{emptyFlags}} from "@/app/market-lab/catalog";
import {{refreshFeeds}} from "@/app/market-lab/actions";
export const dynamic="force-dynamic";
export default async function Page(){{return <MarketLabView model={{await loadMarketLab("{owner}")}} plugins={{await loadLabPlugins()}} envKeys={{emptyFlags()}} refresh={{refreshFeeds}} workspaceName="Local fixture workspace" quarantine={{null}}/>;}}
''')
        port = free_port()
        with (output / "workspace.log").open("w") as log:
            child = subprocess.Popen(["node", str(WORKSPACE / "node_modules/next/dist/bin/next"), "dev", "--hostname", "127.0.0.1", "--port", str(port)],
                cwd=folder, env=env, stdout=log, stderr=log)
            try:
                url = f"http://127.0.0.1:{port}/market-lab"
                wait_ready(url, child)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"), headless=True, args=["--no-sandbox"])
                    try:
                        tab = browser.new_page(viewport={"width": 1440, "height": 1100})
                        tab.goto(url, wait_until="networkidle")
                        yield tab
                    finally:
                        browser.close()
            finally:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
