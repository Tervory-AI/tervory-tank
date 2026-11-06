"""Public Workspace gate and the real internal gate, with external I/O faked."""
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
import httpx
import pytest

import radix_deploy
from test_command import TENANT, runtime as runtime
from test_deploy_changed import _script

ROOT = Path(__file__).resolve().parents[1]
ROUTE = 'workspace/app/v1/command/radix/deploy/gate/route.ts'


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', [False, True])
async def test_public_deploy_request_preserves_internal_gate_and_refuses_bad_auth(runtime, monkeypatch, tmp_path, blocked):
    runtime.TANK_API_KEY = 'placeholder-deploy-service-key'
    decision = {'app': 'agent-radix', 'blocked': blocked, 'cost_usd': 0,
                'findings': [{'id': '33333333-3333-4333-8333-333333333333', 'commit': 'a' * 40,
                              'severity': 'critical', 'rule': 'placeholder-rule'}] if blocked else []}
    read = AsyncMock(return_value=decision)
    monkeypatch.setattr(radix_deploy, 'decision', read)
    internal = FastAPI()
    internal.include_router(radix_deploy.build_router(), prefix='/v1/command')

    # Capture the real deploy caller's URL, header names, and setting mapping.
    deploy = _script(monkeypatch)
    monkeypatch.setenv('RADIX_DEPLOY_TANK_KEY', runtime.TANK_API_KEY)
    monkeypatch.setenv('RADIX_DEPLOY_TENANT_ID', str(TENANT))
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    wire = {}
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return json.dumps(decision).encode()
    def open_request(request, timeout):
        wire.update(url=request.full_url, headers=dict(request.header_items()))
        assert timeout == 10
        return Reply()
    monkeypatch.setattr(deploy.urllib.request, 'build_opener', lambda *args: SimpleNamespace(open=open_request))
    assert deploy.radix_blocks('agent-radix') is blocked

    async with httpx.AsyncClient(transport=httpx.ASGITransport(internal), base_url='http://placeholder-internal') as client:
        path = '/v1/command/radix/deploy/gate'
        query = {'tenant_id': str(TENANT), 'app': 'agent-radix'}
        accepted = await client.get(path, params=query, headers=wire['headers'])
        assert accepted.status_code == 200 and accepted.json() == decision
        read.assert_awaited_once_with(TENANT, 'agent-radix')
        for headers, status in [({}, 401), ({'X-Tank-Key': 'placeholder-wrong'}, 401),
                                ({'X-Tank-Key': runtime.TANK_API_KEY, 'X-Tervory-Tenant': 'placeholder-other'}, 403)]:
            assert (await client.get(path, params=query, headers=headers)).status_code == status
        assert read.await_count == 1
    wire['upstream'] = accepted.json()

    # Assemble only the candidate route and its real shared dependencies in a
    # disposable tree. The patch remains unapplied to Tank and vendor.
    patch = (ROOT / 'tank-patches/radix/public-gate.patch').read_text()
    assert patch.count('diff --git ') == 1 and f'+++ b/{ROUTE}\n' in patch
    assert '--- /dev/null\n' in patch
    checked = subprocess.run(['git', 'apply', '--check', str(ROOT / 'tank-patches/radix/public-gate.patch')],
                             cwd=tmp_path, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    candidate = ''.join(line[1:] for line in patch.splitlines(keepends=True)
                        if line.startswith('+') and not line.startswith('+++'))
    target = tmp_path / ROUTE
    target.parent.mkdir(parents=True)
    target.write_text(candidate)
    for name in ('workspace/lib/tank.ts', 'workspace/lib/workspace-origin.ts', 'workspace/lib/route-input.ts', 'workspace/lib/request.ts', 'workspace/lib/workspace-setup.ts', 'workspace/lib/product-hosts.ts', 'workspace/middleware.ts',
                 'workspace/app/v1/command/[...path]/route.ts', 'tests/command_acceptance_20261031/workspace_loader.cjs'):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    result = subprocess.run(['node', str(ROOT / 'tests/radix_public_gate/workspace.cjs'), str(tmp_path)],
                            cwd=ROOT, input=json.dumps(wire), text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
