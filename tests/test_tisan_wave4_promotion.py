"""One scanned test site promotes and rolls back using HTTP only, never Docker."""
import json
from uuid import uuid4

import httpx
import pytest

from agents.tisan import repo_scan
from tisan_promotion.test_promotion import rig as rig, TENANT, OLD, NEW
from test_tisan_publish import TENANT as BUILD_TENANT, build
from test_tisan_wave4_repo import corridor as corridor


@pytest.mark.asyncio
async def test_exact_scanned_site_promotes_and_rolls_back_without_docker(rig, corridor, tmp_path):
    fake, journal, promotion, _, _ = rig
    build(tmp_path)
    folder = tmp_path / 'builds' / TENANT / 'site'
    folder.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / 'builds' / BUILD_TENANT / 'site').rename(folder)
    manifest = json.loads((folder / '1.json').read_text())
    manifest['checks'] = [manifest['checks'][0]]
    manifest['archive'] = str(folder / '1.tar.gz')
    app, scans = corridor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank') as tank:
        measured = await repo_scan.attach(manifest, TENANT, http=tank)
        assert measured['ok'] is True
        publication = str(uuid4())
        journal.reserve(TENANT, 'site', publication, 'publish', 'placeholder-founder', 'build:1')
        journal.update(TENANT, 'site', publication, 'succeeded',
            {'expected': 'build:1', 'commit': NEW, 'url': 'https://placeholder-stage.test/'}, terminal=True)

        async def check(tenant, site, commit):
            return await repo_scan.promotion_gate(journal, tmp_path, tank, tenant, site, commit)
        promotion.repo_gate = check
        # An actual critical result received via the Tank/R5 corridor blocks the API mutation.
        scans['critical'] = 1
        blocked = await promotion.run(TENANT, 'site', str(uuid4()), 'promote', 'placeholder-founder', NEW)
        assert blocked['result'] == 'refused' and not fake.writes
        assert blocked['details']['repo_scan']['critical'] == 1
        scans['critical'] = 0
        operation = str(uuid4())
        promoted = await promotion.run(TENANT, 'site', operation, 'promote', 'placeholder-founder', NEW)
        assert promoted['result'] == 'pending'
        assert (await promotion.status(TENANT, 'site', operation))['result'] == 'succeeded'
        assert fake.sha['prod'] == NEW
        assert promoted['details']['repo_scan']['scan_id'] == measured['checks'][-1]['scan_id']
        assert await promotion.run(TENANT, 'site', operation, 'promote', 'placeholder-founder', NEW) == journal.get(TENANT, 'site', operation)
        rollback_id = str(uuid4())
        rollback = await promotion.run(TENANT, 'site', rollback_id, 'rollback', 'placeholder-founder', OLD)
        assert rollback['result'] == 'pending'
        assert (await promotion.status(TENANT, 'site', rollback_id))['result'] == 'succeeded'
        assert fake.sha['prod'] == OLD and len(fake.writes) == 4
        assert sum(method == 'POST' for method, _ in scans['calls']) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [None, {'ok': True, 'critical': 1}, {'ok': True, 'critical': False}])
async def test_missing_or_malformed_repo_gate_never_mutates_production(rig, bad):
    fake, _, promotion, _, _ = rig
    async def missing(*args):
        return bad
    promotion.repo_gate = None if bad is None else missing
    result = await promotion.run(TENANT, 'site', str(uuid4()), 'promote', 'placeholder-founder', NEW)
    assert result['result'] == 'refused' and not fake.writes


def test_room_has_no_docker_socket_mount():
    from pathlib import Path
    import yaml
    compose = yaml.safe_load((Path(__file__).resolve().parents[1] / 'agents/tisan/docker-compose.yml').read_text())
    for service in compose['services'].values():
        assert all('docker.sock' not in str(volume) for volume in service.get('volumes', []))
