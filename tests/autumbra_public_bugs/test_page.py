"""Real local Next routes, with only Clerk identity replaced in a temporary copy.

No live sign-in, credentials, Tank data or network services are used. Production
middleware, Shell, public page, admin layout and admin page remain the originals.
"""
import asyncio
import os
from pathlib import Path
import shutil
import socket

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[2]

CLIENT = '''"use client";
export function ClerkProvider({children}) { return children; }
export function OrganizationSwitcher() { return null; }
export function UserButton() { return null; }
export function useAuth() { return {isLoaded: false, userId: null}; }
'''
SERVER = '''import {headers} from "next/headers";
export async function auth() {
  const h = await headers();
  return {userId: h.get("x-offline-user"), orgRole: null};
}
export function clerkMiddleware(callback) {
  return request => callback(async () => ({
    userId: request.headers.get("x-offline-user"),
    redirectToSignIn: () => Response.redirect(new URL("/sign-in", request.url), 307),
  }), request);
}
export function createRouteMatcher(patterns) {
  return request => patterns.some(pattern => new RegExp("^" + pattern + "$").test(request.nextUrl.pathname));
}
'''


@pytest_asyncio.fixture
async def local_workspace(tmp_path):
    local = tmp_path / 'workspace'
    shutil.copytree(ROOT / 'workspace', local,
                    ignore=shutil.ignore_patterns('node_modules', '.next', '.env*', '*.tsbuildinfo'))
    (local / 'node_modules').symlink_to(ROOT / 'workspace/node_modules', target_is_directory=True)
    (local / 'offline-clerk-client.js').write_text(CLIENT)
    (local / 'offline-clerk-server.js').write_text(SERVER)
    (local / 'next.config.ts').write_text('''import path from "node:path";
export default { devIndicators: false, webpack(config) {
  config.resolve.alias["@clerk/nextjs$"] = path.resolve("offline-clerk-client.js");
  config.resolve.alias["@clerk/nextjs/server$"] = path.resolve("offline-clerk-server.js");
  return config;
} };
''')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    origin = f'http://localhost:{port}'
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1', 'TERVORY_ADMIN_USER_IDS': 'offline-founder',
           'TANK_URL': 'http://127.0.0.1:9'}
    with (tmp_path / 'next.log').open('w') as log:
        process = await asyncio.create_subprocess_exec(
            'node', str(local / 'node_modules/next/dist/bin/next'), 'dev', '--hostname', 'localhost',
            '--port', str(port), cwd=local, env=env, stdout=log, stderr=asyncio.subprocess.STDOUT)
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                for _ in range(120):
                    if process.returncode is not None:
                        pytest.fail('Offline Next exited: ' + (tmp_path / 'next.log').read_text()[-3000:])
                    try:
                        response = await client.get(origin + '/autumbra', timeout=2)
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(.5)
                else:
                    pytest.fail('Offline Next did not start: ' + (tmp_path / 'next.log').read_text()[-3000:])
            yield origin
        finally:
            process.terminate()
            await asyncio.wait_for(process.wait(), 15)


@pytest.mark.asyncio
async def test_public_host_and_direct_page_have_no_shell_admin_keeps_gate(local_workspace, real_chromium):
    from playwright.async_api import expect
    proof_dir = Path(os.environ['AUTUMBRA_PUBLIC_PROOF_DIR']) if os.environ.get('AUTUMBRA_PUBLIC_PROOF_DIR') else None
    if proof_dir:
        proof_dir.mkdir(parents=True, exist_ok=True)
    context = await real_chromium.new_context(viewport={'width': 1440, 'height': 1000})
    await context.route('**/*', lambda route: route.continue_()
                        if route.request.url.startswith(local_workspace + '/') else route.abort())
    page = await context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for host, path in [('app.tervory.com', '/autumbra'), ('protect.tervory.com', '/')]:
        await context.set_extra_http_headers({'x-forwarded-host': host})
        response = await page.goto(local_workspace + path)
        assert response.status == 200
        assert 'id="app-sidebar"' not in await response.text()
        await expect(page.locator('.autumbra-public')).to_be_visible()
        await expect(page.locator('#app-sidebar')).to_have_count(0)
        await expect(page.locator('.app-shell')).to_have_count(0)
        assert '/admin/autumbra' not in await page.locator('body').inner_text()
        assert await page.locator('a[href="/admin/autumbra"]').count() == 0
        if proof_dir:
            await page.screenshot(path=proof_dir / f'offline-{host}.png', full_page=True)

    # Inspect the actual middleware's redirect, without visiting real Clerk.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for host in ('app.tervory.com', 'protect.tervory.com'):
            response = await client.get(local_workspace + '/admin/autumbra', headers={'x-forwarded-host': host})
            assert response.status_code == 307
            assert response.headers['location'].endswith('/sign-in')

    await context.set_extra_http_headers({'x-forwarded-host': 'app.tervory.com', 'x-offline-user': 'offline-founder'})
    response = await page.goto(local_workspace + '/admin/autumbra')
    assert response.status == 200
    await expect(page.locator('#app-sidebar')).to_be_visible()
    await expect(page.get_by_role('navigation', name='Workspace', exact=True)).to_be_visible()
    await expect(page.get_by_role('link', name='Dashboard', exact=True)).to_be_visible()
    await expect(page.get_by_role('link', name='Billing', exact=True)).to_be_visible()
    assert not errors
    if proof_dir:
        await page.screenshot(path=proof_dir / 'offline-admin-autumbra.png', full_page=True)
    await context.close()
