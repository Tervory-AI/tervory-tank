"""Offline publish contract: real stored archives, fake GitHub and Coolify APIs."""
import ast
import base64
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import types
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

from agents.tisan import promotion, publish

TENANT = '11111111-1111-1111-1111-111111111111'
OTHER = '22222222-2222-2222-2222-222222222222'
OLD, NEW, TREE = 'a' * 40, 'b' * 40, 'c' * 40
REPO = 'owner/sites'
BRANCH = f'site/{TENANT}/site'
WORKFLOW = (Path(__file__).resolve().parents[1] / 'agents/tisan/templates/next-site/.github/workflows/ci.yml').read_bytes()


def tank_namespace(monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'tank/main.py'
    nodes = ast.parse(source.read_text()).body
    names = {'_tisan_publish_git_commit', 'tisan_publish_git', 'tisan_publish_proxy'}
    async def require_admin(x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        if x_tank_key != 'workspace-test-only' or x_tervory_admin != 'founder':
            raise HTTPException(404, 'not found')
    monkeypatch.setitem(sys.modules, 'admin', types.SimpleNamespace(require_admin=require_admin))
    ns = dict(app=FastAPI(), Depends=Depends, Request=Request, Response=Response, HTTPException=HTTPException,
              os=os, re=re, uuid=uuid, json=json, hashlib=hashlib, httpx=httpx)
    exec(compile(ast.Module(body=[n for n in nodes if getattr(n, 'name', '') in names], type_ignores=[]), str(source), 'exec'), ns)
    return ns


def build(root, *, member=None, passed=True):
    folder = root / 'builds' / TENANT / 'site'
    folder.mkdir(parents=True, exist_ok=True)
    contents = {'content/site.json': b'{"schema":"tisan.content/1"}',
                '.github/workflows/ci.yml': WORKFLOW, 'public/icon.png': bytes(range(256)),
                'scripts/run.sh': b'#!/bin/sh\nexit 0\n'}
    with tarfile.open(folder / '1.tar.gz', 'w:gz') as archive:
        for name, content in contents.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(content), 0o755 if name.endswith('.sh') else 0o644
            archive.addfile(info, io.BytesIO(content))
        if member:
            archive.addfile(member, io.BytesIO(b'x' * member.size))
    manifest = {'ok': passed, 'slug': 'site', 'build': 1, 'files': sorted(contents),
                'checks': [{'name': 'npm test', 'ok': passed}], 'detail': ''}
    (folder / '1.json').write_text(json.dumps(manifest))
    return contents, manifest


class FakeServices:
    def __init__(self):
        self.branch = OLD
        self.exists = True
        self.blobs = {}
        self.trees = []
        self.commits = []
        self.calls = []
        self.pinned = OLD
        self.deployed = OLD
        self.deployment = 'old-deploy'
        self.status = 'finished'
        self.fail_deploy = False
        self.reject_git = False
        self.private = True
        self.drop_commit_ack = False
        self.fqdn = 'https://stage.test/'
        self.git_branch = BRANCH

    async def transport(self, request):
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, str(request.url), body))
        if request.url.host == 'api.github.com':
            assert request.headers['authorization'] == 'Bearer credential-marker-test-only'
            assert request.extensions['timeout']['read'] == 30
            assert path.startswith('/repos/' + REPO)
            suffix = path.removeprefix('/repos/' + REPO)
            if self.reject_git:
                return httpx.Response(403, json={'error': 'credential-marker-test-only'})
            if suffix == '':
                return httpx.Response(200, json={'private': self.private, 'full_name': REPO, 'default_branch': 'main'})
            if request.method == 'GET' and '/git/ref/heads/' in suffix:
                if suffix.endswith('/main'):
                    return httpx.Response(200, json={'object': {'sha': OLD}})
                assert suffix.endswith(BRANCH)
                if not self.exists:
                    return httpx.Response(404)
                return httpx.Response(200, json={'ref': 'refs/heads/' + BRANCH, 'object': {'sha': self.branch}})
            if suffix == '/git/blobs':
                data = base64.b64decode(body['content'])
                sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                self.blobs[sha] = data
                return httpx.Response(201, json={'sha': sha})
            if suffix == '/git/trees':
                assert 'base_tree' not in body
                self.trees.append(body['tree'])
                return httpx.Response(201, json={'sha': TREE})
            if suffix == '/git/commits':
                self.commits.append(body)
                return httpx.Response(201, json={'sha': NEW})
            if request.method in ('PATCH', 'POST') and '/git/refs' in suffix:
                assert body['sha'] == NEW
                if request.method == 'PATCH':
                    assert body['force'] is False and suffix.endswith(BRANCH)
                else:
                    assert body['ref'] == 'refs/heads/' + BRANCH
                self.branch, self.exists = NEW, True
                if self.drop_commit_ack:
                    raise httpx.ReadTimeout('credential-marker-test-only')
                return httpx.Response(200, json={})
        elif request.url.host == 'coolify.test':
            assert request.headers['authorization'] == 'Bearer coolify-marker-test-only'
            assert 'prod' not in path
            if path == '/api/v1/applications/stage':
                if request.method == 'PATCH':
                    assert set(body) == {'git_commit_sha'}
                    self.pinned = body['git_commit_sha']
                return httpx.Response(200, json={'uuid': 'stage', 'status': 'running:healthy',
                    'git_commit_sha': self.pinned, 'git_repository': 'https://github.com/' + REPO,
                    'base_directory': '/', 'build_pack': 'nixpacks', 'git_branch': self.git_branch,
                    'fqdn': self.fqdn, 'settings': {'is_auto_deploy_enabled': False}})
            if path == '/api/v1/deployments/applications/stage':
                return httpx.Response(200, json={'deployments': [{'deployment_uuid': self.deployment,
                    'status': self.status, 'commit': self.deployed, 'pull_request_id': 0}]})
            if path == '/api/v1/deploy':
                assert body == {'uuid': 'stage'}
                self.deployment = 'new-deploy'
                self.deployed = self.pinned
                self.status = 'failed' if self.fail_deploy else 'finished'
                return httpx.Response(200, json={'deployments': [{'deployment_uuid': self.deployment, 'resource_uuid': 'stage'}]})
            if path == '/api/v1/deployments/new-deploy':
                return httpx.Response(200, json={'deployment_uuid': self.deployment, 'status': self.status,
                    'commit': self.deployed, 'pull_request_id': 0})
        raise AssertionError((request.method, str(request.url), body))


@pytest.fixture
def configured(monkeypatch):
    for key, value in {'TISAN_SITES_REPO': REPO, 'TISAN_GITHUB_TOKEN': 'credential-marker-test-only',
                       'TANK_KEY_TISAN': 'room-test-only', 'TANK_KEY': 'room-test-only',
                       'TERVORY_ADMIN_USER_IDS': 'founder', 'TISAN_COOLIFY_URL': 'https://coolify.test',
                       'TISAN_COOLIFY_TOKEN': 'coolify-marker-test-only'}.items():
        monkeypatch.setenv(key, value)


async def exercise(root, monkeypatch, fake):
    namespace = tank_namespace(monkeypatch)
    real_client = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs.get('trust_env') is False and kwargs.get('follow_redirects') is False
        return real_client(transport=httpx.MockTransport(fake.transport), **kwargs)
    # Execute the actual Tank Git route, including room/founder/tenant checks.
    namespace['httpx'] = types.SimpleNamespace(AsyncClient=client, HTTPError=httpx.HTTPError)
    async def corridor(request):
        if request.url.host == 'tank':
            return await httpx.ASGITransport(app=namespace['app']).handle_async_request(request)
        return await fake.transport(request)
    journal = promotion.Journal(root / 'promotion.sqlite3')
    journal.register(TENANT, 'site', {'staging': 'stage', 'production': 'prod', 'url': 'https://stage.test/'})
    http = real_client(transport=httpx.MockTransport(corridor))
    service = publish.Publisher(promotion, journal, promotion.Coolify(http, 'https://coolify.test', 'coolify-marker-test-only'),
                                http, root, 'http://tank:8000', 'room-test-only')
    return service, http, namespace


@pytest.mark.asyncio
@pytest.mark.parametrize('new_branch', [False, True])
async def test_publish_commits_every_file_and_workflow_unchanged_then_only_staging(tmp_path, monkeypatch, configured, caplog, new_branch):
    contents, manifest = build(tmp_path)
    fake = FakeServices()
    fake.exists = not new_branch
    service, http, _ = await exercise(tmp_path, monkeypatch, fake)
    body = publish.PublishRequest(tenant_id=TENANT, slug='site', build=1, operation_id=uuid.uuid4())
    async with http:
        row = await service.run(body, 'founder')
        assert row['result'] == 'pending'
        row = await service.status(body, 'founder')
        assert row['result'] == 'succeeded'
        assert row['details']['url'] == 'https://stage.test/' and row['details']['commit'] == NEW
        writes = len(fake.calls)
        assert (await service.run(body, 'founder')) == row
        assert len(fake.calls) == writes
    assert len(fake.commits) == 1
    assert json.loads(fake.commits[0]['message'].split('\n\n', 1)[1]) == manifest
    assert fake.commits[0]['parents'] == [OLD]
    committed = {entry['path']: fake.blobs[entry['sha']] for entry in fake.trees[0]}
    assert committed == contents
    assert committed['.github/workflows/ci.yml'] == WORKFLOW
    assert next(entry for entry in fake.trees[0] if entry['path'] == 'scripts/run.sh')['mode'] == '100755'
    assert 'credential-marker-test-only' not in json.dumps(row) + caplog.text
    assert 'coolify-marker-test-only' not in json.dumps(row) + caplog.text
    assert not any('prod' in url for _, url, _ in fake.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['deploy', 'git', 'lost-ack', 'wrong-branch', 'wrong-url', 'public-repo', 'wrong-commit'])
async def test_failed_or_ambiguous_publish_never_touches_production_or_repeats(tmp_path, monkeypatch, configured, caplog, failure):
    build(tmp_path)
    fake = FakeServices()
    fake.fail_deploy = failure == 'deploy'
    fake.reject_git = failure == 'git'
    fake.drop_commit_ack = failure == 'lost-ack'
    fake.private = failure != 'public-repo'
    if failure == 'wrong-branch':
        fake.git_branch = f'site/{OTHER}/site'
    if failure == 'wrong-url':
        fake.fqdn = 'https://other.test/'
    service, http, _ = await exercise(tmp_path, monkeypatch, fake)
    body = publish.PublishRequest(tenant_id=TENANT, slug='site', build=1, operation_id=uuid.uuid4())
    async with http:
        row = await service.run(body, 'founder')
        if failure == 'wrong-commit':
            fake.deployed = OLD
        row = await service.status(body, 'founder')
        expected = 'failed' if failure == 'deploy' else 'refused' if failure in ('wrong-branch', 'wrong-url') else 'unknown'
        assert row['result'] == expected
        count = len(fake.calls)
        assert (await service.run(body, 'founder')) == row
        assert len(fake.calls) == count
        if expected != 'refused':
            with pytest.raises(promotion.Refused, match='unresolved'):
                await service.run(body.model_copy(update={'operation_id': uuid.uuid4()}), 'founder')
    assert not any('prod' in url for _, url, _ in fake.calls)
    assert 'credential-marker-test-only' not in json.dumps(row) + caplog.text
    assert 'coolify-marker-test-only' not in json.dumps(row) + caplog.text


@pytest.mark.asyncio
async def test_tenant_binding_and_publish_promotion_share_reservation(tmp_path, monkeypatch, configured):
    build(tmp_path)
    fake = FakeServices()
    service, http, _ = await exercise(tmp_path, monkeypatch, fake)
    body = publish.PublishRequest(tenant_id=OTHER, slug='site', build=1, operation_id=uuid.uuid4())
    async with http:
        with pytest.raises(promotion.Refused, match='not registered'):
            await service.run(body, 'founder')
        assert not fake.calls
        body = body.model_copy(update={'tenant_id': uuid.UUID(TENANT)})
        service.journal.reserve(TENANT, 'site', str(uuid.uuid4()), 'promote', 'founder', OLD)
        with pytest.raises(promotion.Refused, match='unresolved'):
            await service.run(body, 'founder')
        assert not fake.calls


@pytest.mark.parametrize('kind', ['traversal', 'symlink', 'duplicate', 'failed', 'missing-file'])
def test_archive_refuses_unsafe_or_unchecked_build(tmp_path, kind):
    member = None
    if kind in ('traversal', 'symlink', 'duplicate'):
        member = tarfile.TarInfo('../outside' if kind == 'traversal' else 'public/icon.png' if kind == 'duplicate' else 'link')
        if kind == 'symlink':
            member.type, member.linkname = tarfile.SYMTYPE, '/etc/passwd'
    build(tmp_path, member=member, passed=kind != 'failed')
    if kind == 'missing-file':
        path = tmp_path / 'builds' / TENANT / 'site/1.json'
        manifest = json.loads(path.read_text())
        manifest['files'].append('absent')
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        publish.stored_build(tmp_path, TENANT, 'site', 1)
    assert not (tmp_path / 'outside').exists()


@pytest.mark.asyncio
async def test_room_founder_checks_and_wait_for_finished_deployment(tmp_path, monkeypatch, configured):
    build(tmp_path)
    fake = FakeServices()
    service, http, ns = await exercise(tmp_path, monkeypatch, fake)
    real_client = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs == {'trust_env': False, 'follow_redirects': False}
        return real_client(transport=httpx.MockTransport(http._transport.handler), **kwargs)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setattr(publish, 'httpx', types.SimpleNamespace(AsyncClient=client, HTTPError=httpx.HTTPError))
    app = FastAPI()
    publish.mount(app, promotion)
    body = {'tenant_id': TENANT, 'slug': 'site', 'build': 1, 'operation_id': str(uuid.uuid4())}
    headers = {'X-Tank-Key': 'room-test-only', 'X-Tervory-Admin': 'founder'}
    async with http, real_client(transport=httpx.ASGITransport(app=app), base_url='http://room') as browser:
        assert (await browser.post('/publish/build', json=body)).status_code == 404
        assert (await browser.post('/publish/build', json=body, headers={**headers, 'X-Tervory-Admin': 'member'})).status_code == 404
        assert not fake.calls
        result = await browser.post('/publish/build', json=body, headers=headers)
        assert result.status_code == 200 and result.json()['result'] == 'succeeded'
        changed = {**body, 'build': 2}
        assert (await browser.post('/publish/status', json=changed, headers=headers)).status_code == 503


@pytest.mark.asyncio
async def test_tank_corridor_founder_room_tenant_and_action_checks(monkeypatch, configured):
    ns = tank_namespace(monkeypatch)
    calls = []
    async def upstream(request):
        calls.append(request)
        return httpx.Response(200, json={'result': 'pending'})
    headers = {'X-Tank-Key': 'workspace-test-only', 'X-Tervory-Admin': 'founder'}
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as corridor:
        ns['_http'] = corridor
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=ns['app']), base_url='http://tank') as browser:
            assert (await browser.post('/v1/tisan/publish/build', json={})).status_code == 404
            assert (await browser.post('/v1/tisan/publish/production', headers=headers, json={})).status_code == 404
            assert (await browser.post('/v1/tisan/publish/build', headers=headers, content='x' * 8193)).status_code == 413
            assert (await browser.post('/v1/tisan/publish/build', headers=headers, json={'tenant_id': TENANT})).status_code == 200
            assert len(calls) == 1 and str(calls[0].url) == 'http://agent-tisan:8000/publish/build'
            assert calls[0].headers['x-tank-key'] == 'room-test-only'
            assert (await browser.post('/v1/tisan/publish/git', headers=headers, json={})).status_code == 404
            room = {**headers, 'X-Tank-Key': 'room-test-only', 'X-Tervory-Tenant': OTHER}
            assert (await browser.post('/v1/tisan/publish/git', headers=room, json={'tenant_id': TENANT})).status_code == 503
            room['X-Tervory-Admin'] = 'member'
            assert (await browser.post('/v1/tisan/publish/git', headers=room, json={})).status_code == 404
