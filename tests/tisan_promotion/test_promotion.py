"""Real HTTP client against an in-process fake Coolify; never a live target."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agents.tisan.promotion import Coolify, Journal, Promotion, Refused

TENANT = '00000000-0000-0000-0000-000000000011'
OTHER = '00000000-0000-0000-0000-000000000022'
OLD, NEW = 'a' * 40, 'b' * 40
TARGET = 'https://stage.example.org/'


class FakeCoolify:
    def __init__(self):
        self.api = FastAPI()
        self.calls = []
        self.sha = {'stage': NEW, 'prod': OLD}
        self.pin = dict(self.sha)
        self.latest = {'stage': 'stage-build', 'prod': 'prod-build'}
        self.deployments = {name: {'deployment_uuid': name, 'status': 'finished', 'commit': sha,
            'pull_request_id': 0} for name, sha in [('stage-build', NEW), ('prod-build', OLD)]}
        self.pending = False
        self.lost_ack = False
        self.automatic = False
        self.failing = False

        @self.api.api_route('/api/v1/{path:path}', methods=['GET', 'PATCH', 'POST'])
        async def serve(path: str, request: Request):
            self.calls.append((request.method, path, await request.json() if request.method != 'GET' else None))
            if request.headers.get('authorization') != 'Bearer test-only':
                return JSONResponse({}, status_code=401)
            if path.startswith('applications/'):
                app = path.split('/')[1]
                if request.method == 'PATCH':
                    self.pin[app] = (await request.json())['git_commit_sha']
                    return {'uuid': app}
                return {'uuid': app, 'git_commit_sha': self.pin[app], 'status': 'running:healthy',
                        'settings': {'is_auto_deploy_enabled': self.automatic}, 'git_repository': 'owner/site',
                        'build_pack': 'static', 'base_directory': '/',
                        'fqdn': TARGET.rstrip('/') if app == 'stage' else 'https://prod.example.org'}
            if path.startswith('deployments/applications/'):
                app = path.split('/')[-1]
                return {'deployments': [self.deployments[self.latest[app]]], 'count': 1}
            if path == 'deploy':
                app = (await request.json())['uuid']
                if self.sha[app] == self.pin[app] and not (await request.json()).get('force'):
                    return {'deployments': [{'resource_uuid': app, 'message': 'skipped unchanged deployment'}]}
                name = 'release-' + str(len(self.deployments))
                self.latest[app] = name
                self.deployments[name] = {'deployment_uuid': name, 'commit': self.pin[app],
                    'pull_request_id': 0, 'status': 'in_progress' if self.pending else 'finished'}
                if not self.pending:
                    self.sha[app] = self.pin[app]
                if self.lost_ack:
                    return JSONResponse({}, status_code=502)
                return {'deployments': [{'resource_uuid': app, 'deployment_uuid': name}]}
            if path.startswith('deployments/'):
                return self.deployments[path.split('/')[-1]]
            return JSONResponse({}, status_code=404)

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != 'GET']


@pytest_asyncio.fixture
async def rig(tmp_path):
    fake = FakeCoolify()
    journal = Journal(tmp_path / 'promotion.sqlite3')
    journal.register(TENANT, 'site', {'staging': 'stage', 'production': 'prod', 'url': TARGET})
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=fake.api))
    coolify = Coolify(http, 'https://coolify.test', 'test-only')
    live = {'passed': True, 'artifact': 'local-check'}
    gate = {'allowed': True, 'scan_id': 'scan-1', 'tenant_id': TENANT, 'target': TARGET,
            'artifact': 'commit:' + NEW, 'status': 'complete', 'high': 0, 'critical': 0,
            'completed_at': datetime.now(timezone.utc).isoformat()}
    async def check(url):
        assert url == TARGET
        return dict(live)
    async def scan(tenant, target, artifact):
        assert (tenant, target, artifact) == (TENANT, TARGET, 'commit:' + NEW)
        return dict(gate)
    service = Promotion(journal, coolify, check, scan)
    yield fake, journal, service, live, gate
    await http.aclose()


async def promote(service, ident=None):
    return await service.run(TENANT, 'site', ident or str(uuid.uuid4()), 'promote', 'founder', NEW)


@pytest.mark.asyncio
async def test_exact_promotion_rollback_and_durable_audit(rig):
    fake, journal, service, _, _ = rig
    op = str(uuid.uuid4())
    result = await promote(service, op)
    assert result['result'] == 'pending'
    assert fake.writes == [('PATCH', 'applications/prod', {'git_commit_sha': NEW}), ('POST', 'deploy', {'uuid': 'prod'})]
    assert fake.sha['prod'] == NEW
    result = await service.status(TENANT, 'site', op)
    assert result['result'] == 'succeeded'
    assert result['actor'] == 'founder' and result['created_at'] and result['updated_at']
    assert result['details']['previous'] == OLD and result['details']['commit'] == NEW
    restored = Journal(journal.path)
    assert restored.get(TENANT, 'site', op) == result
    assert restored.get(OTHER, 'site', op) is None
    assert await promote(service, op) == result
    assert len(fake.writes) == 2
    rollback = await service.run(TENANT, 'site', str(uuid.uuid4()), 'rollback', 'founder', OLD)
    assert rollback['result'] == 'pending' and fake.sha['prod'] == OLD
    result = await service.status(TENANT, 'site', rollback['id'])
    assert result['result'] == 'succeeded' and result['details']['previous'] == NEW


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('allowed', False), ('allowed', 'true'), ('status', 'pending'),
    ('status', 'error'), ('tenant_id', OTHER), ('target', 'https://other.example.org/'),
    ('artifact', 'commit:' + OLD), ('high', 1), ('high', False), ('critical', 1), ('scan_id', ''),
    ('completed_at', ''), ('completed_at', None), ('completed_at', datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
    ('completed_at', (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()),
    ('completed_at', (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())])
async def test_gate_fail_closed(rig, field, value):
    fake, _, service, _, gate = rig
    gate[field] = value
    assert (await promote(service))['result'] == 'refused'
    assert not fake.writes


@pytest.mark.asyncio
async def test_staging_page_failure_and_revision_change(rig):
    fake, _, service, live, _ = rig
    live['passed'] = False
    assert (await promote(service))['result'] == 'refused'
    assert not fake.writes
    async def changed(url):
        fake.pin['stage'] = OLD
        return {'passed': True}
    service.live_check = changed
    assert (await promote(service))['result'] == 'refused'
    assert not fake.writes


@pytest.mark.asyncio
async def test_pending_and_lost_ack_never_repeat_deploy(rig):
    fake, journal, service, _, _ = rig
    fake.lost_ack = True
    op = str(uuid.uuid4())
    first = await promote(service, op)
    assert first['result'] == 'unknown'
    assert (await promote(service, op)) == first
    assert len(fake.writes) == 2
    with pytest.raises(Refused, match='unresolved'):
        await promote(service)
    assert Journal(journal.path).get(TENANT, 'site', op)['result'] == 'unknown'


@pytest.mark.asyncio
async def test_queued_status_and_exact_completion(rig):
    fake, _, service, _, _ = rig
    fake.pending = True
    op = str(uuid.uuid4())
    result = await promote(service, op)
    assert (await service.status(TENANT, 'site', op))['result'] == 'pending'
    deployment = fake.deployments[result['details']['deployment']]
    deployment['status'] = 'finished'
    deployment['commit'] = OLD
    assert (await service.status(TENANT, 'site', op))['result'] == 'unknown'
    with pytest.raises(Refused):
        await promote(service)


@pytest.mark.asyncio
async def test_ownership_replay_and_concurrency(rig):
    fake, journal, service, _, _ = rig
    with pytest.raises(Refused):
        await service.run(OTHER, 'site', str(uuid.uuid4()), 'promote', 'founder', NEW)
    with pytest.raises(Refused):
        journal.register(OTHER, 'other', {'staging': 'prod', 'production': 'elsewhere', 'url': TARGET})
    started, release = asyncio.Event(), asyncio.Event()
    async def pause(url):
        started.set()
        await release.wait()
        return {'passed': True}
    service.live_check = pause
    first = asyncio.create_task(promote(service))
    await started.wait()
    with pytest.raises(Refused, match='unresolved'):
        await promote(service)
    release.set()
    result = await first
    with pytest.raises(Refused, match='identity'):
        await service.run(TENANT, 'site', result['id'], 'promote', 'other-user', NEW)
    assert len(fake.writes) == 2


@pytest.mark.asyncio
async def test_unpinned_automatic_and_unapproved_rollback(rig):
    fake, _, service, _, _ = rig
    fake.automatic = True
    assert (await promote(service))['result'] == 'refused'
    fake.automatic = False
    fake.pin['stage'] = 'HEAD'
    assert (await promote(service))['result'] == 'refused'
    result = await service.run(TENANT, 'site', str(uuid.uuid4()), 'rollback', 'founder', OLD)
    assert result['result'] == 'refused' and not fake.writes


def test_binding_and_token_url_validation(tmp_path):
    journal = Journal(tmp_path / 'audit.db')
    config = {'staging': 'stage', 'production': 'prod', 'url': TARGET}
    journal.register(TENANT, 'site', config)
    with pytest.raises(Refused):
        journal.register(TENANT, 'site', {**config, 'staging': 'elsewhere'})
    with pytest.raises(Refused):
        Coolify(None, 'https://user:password@coolify.test', 'test-only')
    with pytest.raises(Refused):
        Coolify(None, 'https://coolify.test', '')


@pytest.mark.asyncio
@pytest.mark.parametrize('callback,error', [('live_check', TimeoutError()), ('live_check', OSError()),
                                         ('radix_gate', httpx.ReadTimeout('test timeout'))])
async def test_preflight_transport_failure_releases_reservation(rig, callback, error):
    fake, _, service, _, _ = rig
    prior = getattr(service, callback)
    async def fail(*args):
        raise error
    setattr(service, callback, fail)
    result = await promote(service)
    assert result['result'] == 'refused' and not fake.writes
    setattr(service, callback, prior)
    assert (await promote(service))['result'] == 'pending'
    assert len(fake.writes) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['failed', 'cancelled-by-user'])
async def test_explicit_rollback_after_acknowledged_terminal_failure(rig, state):
    fake, journal, service, _, _ = rig
    fake.pending = True
    op = str(uuid.uuid4())
    pending = await promote(service, op)
    fake.deployments[pending['details']['deployment']]['status'] = state
    failed = await service.status(TENANT, 'site', op)
    assert failed['result'] == 'failed'
    assert (await promote(service, op))['result'] == 'failed'
    assert len(fake.writes) == 2
    with pytest.raises(Refused):
        await promote(service)
    fake.pending = False
    rollback = await service.run(TENANT, 'site', str(uuid.uuid4()), 'rollback', 'founder', OLD)
    assert rollback['result'] == 'pending'
    assert rollback['details']['recovery_of'] == op
    assert rollback['details']['commit'] == OLD
    assert fake.writes[-2:] == [('PATCH', 'applications/prod', {'git_commit_sha': OLD}), ('POST', 'deploy', {'uuid': 'prod', 'force': True})]
    assert (await service.status(TENANT, 'site', rollback['id']))['result'] == 'succeeded'
    assert Journal(journal.path).get(TENANT, 'site', op)['result'] == 'failed'


@pytest.mark.asyncio
async def test_failed_rollback_refuses_replaced_or_inflight_deployment(rig):
    fake, _, service, _, _ = rig
    pending = await promote(service)
    fake.deployments[pending['details']['deployment']]['status'] = 'failed'
    assert (await service.status(TENANT, 'site', pending['id']))['result'] == 'failed'
    fake.deployments[pending['details']['deployment']]['status'] = 'in_progress'
    result = await service.run(TENANT, 'site', str(uuid.uuid4()), 'rollback', 'founder', OLD)
    assert result['result'] == 'refused'
    assert len(fake.writes) == 2


@pytest.mark.asyncio
async def test_rollback_source_survives_long_refusal_history(rig):
    _, journal, service, _, _ = rig
    result = await promote(service)
    assert (await service.status(TENANT, 'site', result['id']))['result'] == 'succeeded'
    for _ in range(101):
        result = await service.run(TENANT, 'site', str(uuid.uuid4()), 'rollback', 'founder', NEW)
        assert result['result'] == 'refused'
    assert len(journal.history(TENANT, 'site')) == 100
    assert journal.latest_recorded(TENANT, 'site')['result'] == 'succeeded'
    result = await service.run(TENANT, 'site', str(uuid.uuid4()), 'rollback', 'founder', OLD)
    assert result['result'] == 'pending'


@pytest.mark.asyncio
async def test_malformed_gate_and_unresolved_queue_revision(rig):
    fake, _, service, _, _ = rig
    previous = service.radix_gate
    async def malformed(*args):
        return []
    service.radix_gate = malformed
    assert (await promote(service))['result'] == 'refused'
    service.radix_gate = previous
    fake.pending = True
    result = await promote(service)
    fake.deployments[result['details']['deployment']]['commit'] = 'HEAD'
    assert (await service.status(TENANT, 'site', result['id']))['result'] == 'pending'


@pytest.mark.asyncio
async def test_already_current_promotion_is_a_recorded_noop(rig):
    fake, _, service, _, _ = rig
    fake.sha['prod'] = fake.pin['prod'] = NEW
    fake.deployments['prod-build']['commit'] = NEW
    assert (await promote(service))['result'] == 'refused'
    assert not fake.writes
