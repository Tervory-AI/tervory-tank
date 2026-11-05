import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest

from workers.github_api import GitHubError
from workers.window_agent.github import UserGitHub
from workers.window_agent.review import review, right_lines


@pytest.mark.parametrize('changed_head,bad_line,receipt', [(False, False, True), (True, False, True), (False, True, True), (False, False, False)])
@pytest.mark.asyncio
async def test_review_publishes_only_valid_comments_on_the_reviewed_head(changed_head, bad_line, receipt):
    requests = []
    reads = 0
    sha = 'a' * 40

    def github_api(request):
        nonlocal reads
        requests.append(request)
        if request.url.path.endswith('/files'):
            return httpx.Response(200, json=[{'filename': 'counter.py', 'patch': '@@ -1 +1 @@\n-old\n+new'}])
        if request.method == 'GET':
            reads += 1
            return httpx.Response(200, json={'state': 'open', 'head': {'sha': 'b' * 40 if changed_head and reads > 1 else sha},
                'base': {'repo': {'full_name': 'alice/project'}}, 'changed_files': 1})
        body = json.loads(request.content)
        assert body['event'] == 'COMMENT' and body['commit_id'] == sha
        assert body['comments'][0]['side'] == 'RIGHT'
        return httpx.Response(200, json={'id': 8})

    turn = AsyncMock(return_value={'answer': json.dumps({'summary': 'One issue', 'comments': [
        {'path': 'counter.py', 'line': 99 if bad_line else 1, 'body': 'This count drops a row.'}]}),
        'requests': [], 'receipt': {'rows': [{'ledger_id': str(uuid.uuid4())}] if receipt else []}})
    heartbeat = AsyncMock()
    async with httpx.AsyncClient(transport=httpx.MockTransport(github_api)) as client:
        args = ({'job_id': str(uuid.uuid4()), 'pull_number': 7}, UserGitHub('alice/project', client),
                'github_pat_' + 'test' * 8, turn, heartbeat)
        if changed_head:
            outcome = await review(*args)
            assert outcome['status'] == 'superseded'
            assert all(r.method != 'POST' for r in requests)
        elif bad_line or not receipt:
            with pytest.raises(GitHubError):
                await review(*args)
            assert all(r.method != 'POST' for r in requests)
        else:
            outcome = await review(*args)
            assert outcome == {'status': 'done', 'pr_number': 7, 'sha': sha}
            heartbeat.assert_awaited_once()
        assert turn.call_args.args[0]['model'] == 'auto'
        assert all('/merge' not in r.url.path for r in requests)


def test_right_lines_map_context_additions_and_deletions():
    assert right_lines('@@ -10,3 +10,3 @@\n same\n-removed\n+added\n last\n@@ -99,0 +100 @@\n+tail') == {10, 11, 12, 100}


@pytest.mark.asyncio
async def test_review_refuses_incomplete_diff_before_spending():
    async def send(method, url, token, body=None):
        if url.endswith('/pulls/7'):
            return {'state': 'open', 'head': {'sha': 'a' * 40}, 'base': {'repo': {'full_name': 'alice/project'}}, 'changed_files': 1}
        return [{'filename': 'binary.png'}]
    github = UserGitHub('alice/project', None)
    github._send = send
    turn = AsyncMock()
    with pytest.raises(GitHubError):
        await review({'job_id': str(uuid.uuid4()), 'pull_number': 7}, github, 'unused', turn, AsyncMock())
    turn.assert_not_called()


from test_window_agents import agent_db as agent_db


@pytest.mark.asyncio
async def test_enabled_webhook_verifies_signature_deduplicates_head_and_stays_user_scoped(agent_db, monkeypatch):
    import hashlib
    import hmac
    import command
    import window_agents as agents
    import window_agent_reviews as reviews
    from fastapi import FastAPI
    monkeypatch.setattr(reviews, 'public_origin', lambda: 'https://app.tervory.com')
    owner = command.Actor(uuid.uuid4(), 'alice', False)
    actor = [owner]
    application = FastAPI()
    application.include_router(agents.router)
    application.include_router(reviews.router)
    application.dependency_overrides[agents.actor_identity] = lambda: actor[0]
    application.dependency_overrides[command.worker] = lambda: None
    token = 'github_pat_' + 'test' * 8
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://test') as client:
        await client.post('/v1/window-agents/vault/github', json={'name': 'github', 'value': token})
        config = {'repo': 'alice/project', 'credential_name': 'github', 'enabled': True}
        response = await client.post('/v1/window-agents/webhooks', json=config)
        assert response.status_code == 200
        hook = response.json()
        assert response.headers['cache-control'] == 'no-store'
        assert '/v1/command/window-agents/webhooks/' in hook['url']
        path = httpx.URL(hook['url']).path.replace('/v1/command/', '/v1/')
        payload = {'action': 'opened', 'number': 9, 'repository': {'full_name': 'alice/project'},
                   'pull_request': {'head': {'sha': 'a' * 40}, 'base': {'repo': {'full_name': 'alice/project'}}}}
        raw = json.dumps(payload).encode()
        headers = {'x-github-event': 'pull_request', 'x-github-delivery': str(uuid.uuid4()),
                   'x-hub-signature-256': 'sha256=' + hmac.new(hook['secret'].encode(), raw, hashlib.sha256).hexdigest()}
        bad = await client.post(path, content=raw, headers={**headers, 'x-hub-signature-256': 'sha256=' + '0' * 64})
        wrong_path = path.rsplit('/', 1)[0] + '/' + str(uuid.uuid4())
        wrong = await client.post(wrong_path, content=raw, headers=headers)
        wrong_tenant = await client.post(path.replace(str(owner.tenant_id), str(uuid.uuid4())), content=raw, headers=headers)
        assert bad.status_code == wrong.status_code == wrong_tenant.status_code == 404
        assert bad.json() == wrong.json() == {'detail': 'Not Found'}
        assert (await client.post(path, content=b'x' * 1_000_001, headers=headers)).status_code == 413
        assert (await client.get('/v1/window-agents/jobs')).json() == []
        async with agent_db.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM tank.window_agent_deliveries WHERE tenant_id=$1', owner.tenant_id) == 0
        first = await client.post(path, content=raw, headers=headers)
        assert first.status_code == 202
        assert (await client.post(path, content=raw, headers=headers)).status_code == 409
        changed = json.dumps({**payload, 'number': 10}).encode()
        changed_headers = {**headers, 'x-hub-signature-256': 'sha256=' + hmac.new(hook['secret'].encode(), changed, hashlib.sha256).hexdigest()}
        assert (await client.post(path, content=changed, headers=changed_headers)).status_code == 409
        again = await client.post(path, content=raw, headers={**headers, 'x-github-delivery': str(uuid.uuid4())})
        assert again.json() == first.json()
        rows = (await client.get('/v1/window-agents/jobs')).json()
        assert len(rows) == 1 and rows[0]['kind'] == 'review' and rows[0]['pull_number'] == 9
        assert token not in str(rows) and hook['secret'] not in str(rows)
        assert (await client.post('/v1/window-agents/worker/next', json={'kind': 'task'})).json() is None
        assert (await client.post('/v1/window-agents/worker/next', json={'kind': 'review'})).json()['kind'] == 'review'
        actor[0] = command.Actor(owner.tenant_id, 'bob', False)
        assert (await client.get('/v1/window-agents/jobs')).json() == []
        assert (await client.post('/v1/window-agents/webhooks', json=config)).status_code == 404
        actor[0] = owner
        disabled = await client.post('/v1/window-agents/webhooks', json={**config, 'enabled': False})
        assert disabled.json()['secret'] is None
        assert (await client.post(path, content=raw, headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_review_worker_uses_no_container_and_reports_result(monkeypatch):
    from workers.window_agent.service import WindowJobs
    from workers.settings import Settings
    worker = WindowJobs(Settings(), None, None, runner=AsyncMock())
    job = {'tenant_id': str(uuid.uuid4()), 'job_id': str(uuid.uuid4()), 'lease': 'z' * 43,
           'repo': 'alice/project', 'pull_number': 9, 'kind': 'review'}
    calls = []

    async def call(path, body=None, **kwargs):
        calls.append(path)
        if path.endswith('/credential'):
            return {'value': 'github_pat_' + 'test' * 8}
        return {'status': 'running'}

    monkeypatch.setattr(worker, 'call', call)
    expected = {'status': 'done', 'pr_number': 9, 'sha': 'a' * 40}
    fake = AsyncMock(return_value=expected)
    monkeypatch.setattr('workers.window_agent.review.review', fake)
    await worker.run_review(job)
    fake.assert_awaited_once()
    worker.runner.assert_not_called()
    assert calls[-1].endswith('/finish')


@pytest.mark.asyncio
async def test_merge_word_in_repository_is_allowed_but_merge_and_traversal_routes_are_not():
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={'default_branch': 'main', 'permissions': {'push': True}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        github = UserGitHub('alice/merge-helper', client)
        token = 'github_pat_' + 'test' * 8
        assert await github.default_branch(token) == 'main'
        for path in ['/pulls/1/merge', '/merges', '/merge-upstream', '/../../bob/private', '/%2e%2e/other']:
            with pytest.raises(GitHubError):
                await github._send('PUT', 'https://api.github.com/repos/alice/merge-helper' + path, token)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_queued_webhook_review_for_an_old_head_costs_nothing():
    github = UserGitHub('alice/project', None)
    github.pull = AsyncMock(return_value={'state': 'open', 'head': {'sha': 'b' * 40},
        'base': {'repo': {'full_name': 'alice/project'}}, 'changed_files': 1})
    turn = AsyncMock()
    result = await review({'job_id': str(uuid.uuid4()), 'pull_number': 8, 'target_sha': 'a' * 40},
                          github, 'unused', turn, AsyncMock())
    assert result == {'status': 'superseded', 'pr_number': 8, 'sha': None}
    turn.assert_not_called()
