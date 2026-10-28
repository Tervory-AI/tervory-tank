"""Chat -> Tank -> worker -> same-thread progress, entirely offline.

The integration fixture uses the real Tank router and isolated local Postgres.
GitHub and the model runner are doubles; the task test uses real local Git repos.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException

import command
from test_command import TENANT, api as api, command_pool as command_pool, runtime as runtime
from workers.command_tasks import CommandTask
from workers.github_api import GitHub
from workers.issues import WorkerIssue
from workers.service import Launcher, Service
from workers.settings import Settings
from workers.tank_status import TankControl
from workers.task_run import Outcome, parse_result

BUILD = str(uuid.UUID(int=101))
PR = 'https://github.com/Tervory-AI/tervory-tank/pull/123'
BRIEF = '# Change the greeting\n\n## Files you may change\n- `greeting.txt`\n\n## Work\nWrite hello.'
TOKEN = 'ghs_' + 't' * 36


def settings(tmp_path):
    return Settings(tank_url='http://tank:8000', code_dir=str(tmp_path / 'app'), state_dir=str(tmp_path / 'secrets'))


def build():
    return {'build_id': BUILD, 'tenant_id': str(TENANT), 'brief_markdown': BRIEF}


def outcome():
    return Outcome(status='draft', pr_url=PR, pr_number=123, node_id='PR_fixture', sha='a' * 40)


def github():
    return Mock(
        list_issues=AsyncMock(return_value=[]), tasks=Mock(return_value=[]), malformed=Mock(return_value=[]),
        mint_installation_token=AsyncMock(return_value=TOKEN),
        pull=AsyncMock(return_value={'number': 123, 'node_id': 'PR_fixture', 'html_url': PR, 'state': 'open',
                                    'draft': True, 'head': {'sha': 'a' * 40}}),
        check_runs=AsyncMock(return_value=[{'status': 'completed', 'conclusion': 'success'}]),
        combined_status=AsyncMock(return_value='success'), mark_ready=AsyncMock(), comment=AsyncMock(),
    )


class LocalQueue:
    def __init__(self):
        self.queued = [build()]
        self.replies = []
        self.reports = []
        self.requests = []
        self.paused = False
        self.progress_down = False

    def __call__(self, request):
        assert request.headers['x-tank-key'] == 'dummy-worker-key'
        self.requests.append(str(request.url))
        path = request.url.path
        if path == '/v1/workers/paused':
            return httpx.Response(200, json={'paused': self.paused})
        if path == '/v1/command/builds/next':
            return httpx.Response(200, content=json.dumps(self.queued.pop(0) if self.queued else None))
        if path.endswith('/progress'):
            if self.progress_down:
                return httpx.Response(503)
            body = json.loads(request.content)
            command.Progress(**body)  # Use the real wire schema for every report.
            self.reports.append(body)
            return httpx.Response(200, json=body)
        if path.endswith('/followups'):
            after = int(request.url.params['after'])
            return httpx.Response(200, json=[r for r in self.replies if r['followup_id'] > after])
        raise AssertionError(f'Unexpected local route: {path}')


def setup_worker(tmp_path, monkeypatch, queue=None):
    monkeypatch.setenv('TANK_KEY_WORKERS', 'dummy-worker-key')
    monkeypatch.delenv('TANK_KEY_FILE', raising=False)
    queue = queue or LocalQueue()
    client = httpx.AsyncClient(transport=httpx.MockTransport(queue))
    config = settings(tmp_path)
    gh = github()
    launcher = Mock(run=AsyncMock(return_value=outcome()))
    worker = Service(config, gh, launcher, TankControl(config, client))
    return worker, queue, gh, launcher, client


async def settle(worker):
    if worker.jobs:
        await asyncio.gather(*worker.jobs)


@pytest.mark.asyncio
async def test_queue_priority_capacity_pause_and_drain(tmp_path, monkeypatch):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    issue = WorkerIssue(1, 'Fallback', '', 'docs/cursor/EXAMPLE.md')
    gh.tasks.return_value = [issue]
    gh.open_pulls = AsyncMock(return_value=[])
    release = asyncio.Event()

    async def run(*args):
        await release.wait()
        return outcome()

    launcher.run.side_effect = run
    try:
        queue.paused = True
        await worker.poll_once(TOKEN)
        assert not any(url.endswith('/builds/next') for url in queue.requests)
        queue.paused = False
        (tmp_path / 'UPDATE_PENDING').touch()
        await worker.poll_once(TOKEN)
        assert launcher.run.call_count == 0
        (tmp_path / 'UPDATE_PENDING').unlink()
        await worker.poll_once(TOKEN)
        await asyncio.sleep(0)
        assert worker.busy
        assert launcher.run.call_count == 1
        assert isinstance(launcher.run.call_args.args[1], CommandTask)
        await worker.poll_once(TOKEN)
        assert launcher.run.call_count == 1
        assert len(worker.commands.inflight) == 1
        release.set()
        await settle(worker)
        assert not worker.busy
        # With the chat queue empty, the existing issue path still runs.
        launcher.run.side_effect = None
        launcher.run.return_value = Outcome(status='ready')
        await worker.poll_once(TOKEN)
        await settle(worker)
        assert launcher.run.call_args.args[1] == issue
    finally:
        release.set()
        await settle(worker)
        await client.aclose()


@pytest.mark.asyncio
async def test_restart_followups_cursor_same_pr_and_current_head_checks(tmp_path, monkeypatch):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    try:
        await worker.poll_once(TOKEN)
        await settle(worker)
        config, task, _ = launcher.run.call_args.args
        assert config.tenant_id == str(TENANT)
        assert task.body == BRIEF
        assert queue.reports[-1]['pr_url'] == PR
        queue.replies = [{'followup_id': 4, 'followup_text': 'Make it friendlier'},
                         {'followup_id': 9, 'followup_text': 'Use sentence case'}]
        restarted = Service(worker.settings, gh, launcher, worker.control)
        await restarted.poll_once(TOKEN)
        await settle(restarted)
        follow_task = launcher.run.call_args.args[1]
        assert follow_task.branch == task.branch
        assert follow_task.followups == tuple(queue.replies)
        assert restarted.commands.rows[BUILD]['cursor'] == 9
        again = Service(worker.settings, gh, launcher, worker.control)
        gh.pull.return_value['head']['sha'] = 'b' * 40
        await again.poll_once(TOKEN)
        assert launcher.run.call_count == 2
        gh.check_runs.assert_awaited_with(TOKEN, 'b' * 40)
        assert queue.reports[-1]['ci_status'] == 'passed'
        assert queue.reports[-1]['status'] == 'awaiting_review'
        assert 'ready' in queue.reports[-1]['step_label']
        gh.mark_ready.assert_awaited_once()
        gh.comment.assert_not_called()  # No synthetic GitHub issue for a chat build.
        journal = tmp_path / 'command-builds' / f'{BUILD}.json'
        assert journal.stat().st_mode & 0o777 == 0o600
        assert TOKEN not in journal.read_text()
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['pending', 'red'])
async def test_non_green_checks_stay_open_and_followups_can_fix_them(tmp_path, monkeypatch, state):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    try:
        await worker.poll_once(TOKEN)
        await settle(worker)
        gh.check_runs.return_value = [{'status': 'in_progress' if state == 'pending' else 'completed', 'conclusion': 'failure'}]
        await worker.poll_once(TOKEN)
        assert queue.reports[-1]['ci_status'] == ('pending' if state == 'pending' else 'failed')
        assert queue.reports[-1]['status'] == 'awaiting_review'
        gh.mark_ready.assert_not_called()
        queue.replies = [{'followup_id': 1, 'followup_text': 'Fix the check'}]
        await worker.poll_once(TOKEN)
        await settle(worker)
        assert launcher.run.call_count == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_failed_result_receipts_and_report_retry_do_not_repeat_work(tmp_path, monkeypatch):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    receipts = [str(uuid.uuid4()) for _ in range(103)]

    async def run(*args):
        queue.progress_down = True
        return Outcome(status='failed', detail='Required file scope is missing', ledger_ids=receipts)

    launcher.run.side_effect = run
    try:
        await worker.poll_once(TOKEN)
        await settle(worker)
        assert worker.commands.rows[BUILD]['outbox']
        queue.progress_down = False
        restarted = Service(worker.settings, gh, launcher, worker.control)
        await restarted.poll_once(TOKEN)
        assert launcher.run.call_count == 1
        assert queue.reports[-1]['status'] == 'failed'
        assert 'scope is missing' in queue.reports[-1]['step_label']
        assert [r for p in queue.reports for r in p.get('ledger_ids', [])] == receipts
        assert not restarted.commands.rows[BUILD]['outbox']
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_interrupted_edit_is_reported_without_relaunch(tmp_path, monkeypatch):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    try:
        worker.commands.load()
        queue.queued.clear()
        worker.commands.save({'task': CommandTask.from_payload(build()).payload(), 'phase': 'executing', 'cursor': 0})
        restarted = Service(worker.settings, gh, launcher, worker.control)
        await restarted.poll_once(TOKEN)
        launcher.run.assert_not_called()
        assert queue.reports[-1]['status'] == 'failed'
        assert 'interrupted' in queue.reports[-1]['step_label']
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_failed_followup_is_not_retried_or_marked_ready_on_old_checks(tmp_path, monkeypatch):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    try:
        await worker.poll_once(TOKEN)
        await settle(worker)
        queue.replies = [{'followup_id': 1, 'followup_text': 'Fix the text'}]
        launcher.run.return_value = Outcome(status='failed', detail='The edit failed')
        await worker.poll_once(TOKEN)
        await settle(worker)
        await worker.poll_once(TOKEN)
        assert launcher.run.call_count == 2
        assert queue.reports[-1]['pr_url'] == PR
        assert 'edit failed' in queue.reports[-1]['step_label']
        gh.mark_ready.assert_not_called()
        queue.replies.append({'followup_id': 2, 'followup_text': 'Try this corrected instruction'})
        launcher.run.return_value = outcome()
        await worker.poll_once(TOKEN)
        await settle(worker)
        assert launcher.run.call_args.args[1].followups == (queue.replies[-1],)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_closed_pr_finishes_without_merging(tmp_path, monkeypatch):
    worker, queue, gh, launcher, client = setup_worker(tmp_path, monkeypatch)
    try:
        await worker.poll_once(TOKEN)
        await settle(worker)
        gh.pull.return_value.update(state='closed', merged=True)
        await worker.poll_once(TOKEN)
        assert queue.reports[-1]['status'] == 'done'
        assert queue.reports[-1]['review_status'] == 'merged'
        gh.merge.assert_not_called()
        assert launcher.run.call_count == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_real_tank_confirm_to_result_and_thread_reply_on_same_pr(api, tmp_path, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={'title': 'A small change'})).json()['thread_id']
    other = (await client.post('/v1/command/threads', json={'title': 'Unrelated'})).json()['thread_id']
    card = (await client.post('/v1/command/build', json={'thread_id': thread, 'brief_markdown': BRIEF})).json()
    config = replace(settings(tmp_path), tank_url='http://fixture')
    control = TankControl(config, client)
    control.paused = AsyncMock(return_value=False)
    gh, launcher = github(), Mock(run=AsyncMock(return_value=outcome()))
    worker = Service(config, gh, launcher, control)
    await worker.poll_once(TOKEN)
    launcher.run.assert_not_called()  # Proposals do not start work.
    approved = await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'confirm'})
    build_id = approved.json()['build_id']
    await worker.poll_once(TOKEN)
    await settle(worker)
    assert launcher.run.call_args.args[0].tenant_id == str(TENANT)
    await worker.poll_once(TOKEN)
    detail = (await client.get(f'/v1/command/threads/{thread}')).json()
    step = next(s for s in detail['steps'] if s['step_id'] == build_id)
    assert step['link'] == PR and step['ci_status'] == 'passed'
    assert 'ready' in step['label']
    assert not (await client.get(f'/v1/command/threads/{other}')).json()['steps']
    # Send an ordinary thread reply; route_turn is offline and needs no model.
    monkeypatch.setattr(command, 'route_turn', AsyncMock(side_effect=HTTPException(503, 'offline model')))
    await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Change hello to welcome'})
    resumed = Service(config, gh, launcher, control)
    await resumed.poll_once(TOKEN)
    await settle(resumed)
    tasks = [call.args[1] for call in launcher.run.call_args_list]
    assert len(tasks) == 2 and tasks[0].branch == tasks[1].branch
    assert tasks[1].followups[0]['followup_text'] == 'Change hello to welcome'
    await resumed.poll_once(TOKEN)
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_builds') == 1
        row = await conn.fetchrow('SELECT * FROM tank.command_builds WHERE build_id=$1', uuid.UUID(build_id))
        assert row['status'] == 'awaiting_review' and row['pr_url'] == PR and row['ci_status'] == 'passed'
    assert launcher.run.call_count == 2


@pytest.mark.asyncio
async def test_launcher_mounts_private_brief_and_uses_build_tenant(tmp_path, monkeypatch):
    monkeypatch.setenv('TANK_KEY_WORKERS', 'dummy-worker-key')
    monkeypatch.delenv('TANK_KEY_FILE', raising=False)
    config = replace(settings(tmp_path), tank_url='http://127.0.0.1:8100', link='loopback', tenant_id=str(TENANT))
    task = CommandTask.from_payload(build())

    async def runner(argv, **kwargs):
        if argv[1] == 'info':
            return 0, '{"host":{"ociRuntime":{"name":"crun"}}}', ''
        assert BRIEF not in ' '.join(argv)
        assert f'WORKER_TENANT_ID={TENANT}' in argv
        payload = next((tmp_path / 'secrets').glob('*/command.json'))
        assert json.loads(payload.read_text())['body'] == BRIEF
        assert payload.stat().st_mode & 0o777 == 0o444
        return 0, outcome().line(), ''

    launcher = Launcher(runner)
    launcher._built = True
    result = await launcher.run(config, task, TOKEN)
    assert result.pr_url == PR
    assert not list((tmp_path / 'secrets').iterdir())


def test_task_runner_reuses_local_branch_and_pr_for_followup(tmp_path, monkeypatch, capsys):
    from workers.task import __main__ as entry
    remote, seed, checkout = tmp_path / 'remote.git', tmp_path / 'seed', tmp_path / 'work/repo'

    def git(*args, cwd=tmp_path):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

    git('init', '--bare', str(remote))
    git('init', '-b', 'main', str(seed))
    git('config', 'user.name', 'Offline fixture', cwd=seed)
    git('config', 'user.email', 'fixture@example.invalid', cwd=seed)
    (seed / 'greeting.txt').write_text('before\n')
    git('add', '.', cwd=seed)
    git('commit', '-m', 'Fixture', cwd=seed)
    git('remote', 'add', 'origin', str(remote), cwd=seed)
    git('push', 'origin', 'main', cwd=seed)
    task = CommandTask.from_payload(build())
    payload, token_file = tmp_path / 'command.json', tmp_path / 'token'
    token_file.write_text(TOKEN)
    payload.write_text(json.dumps(task.payload()))
    for key, value in {'WORKER_ISSUE': str(task.number), 'WORKER_BRIEF': task.brief, 'WORKER_BRANCH': task.branch,
                       'WORKER_TENANT_ID': str(TENANT), 'WORKER_REPO': 'Tervory-AI/tervory-tank',
                       'GITHUB_TOKEN_FILE': str(token_file)}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(entry, 'ROOT', checkout)
    monkeypatch.setattr(entry, 'COMMAND_FILE', payload)
    monkeypatch.setattr(entry, '_serve_proxy', lambda *args: None)
    gh = Mock(open_pulls=AsyncMock(return_value=[]), mark_draft=AsyncMock(),
              create_draft=AsyncMock(return_value={'html_url': PR, 'number': 123, 'node_id': 'PR_fixture'}))
    monkeypatch.setattr(entry, 'GitHub', lambda *args: gh)
    original_run = entry._run
    edit = ['hello\n', 'greeting.txt']

    def run(argv, cwd):
        if argv[0] == 'aider':
            message = Path(argv[argv.index('--message-file') + 1]).read_text()
            assert BRIEF in message and 'Do not push, merge, or deploy' in message
            (cwd / edit[1]).write_text(edit[0])
            return ''
        if 'clone' in argv:
            argv = [*argv[:-2], str(remote), argv[-1]]
        return original_run(argv, cwd)

    monkeypatch.setattr(entry, '_run', run)
    assert entry.main() == 0
    first = parse_result(capsys.readouterr().out)
    assert first.pr_url == PR
    first_sha = git('--git-dir', str(remote), 'rev-parse', f'refs/heads/{task.branch}')
    shutil.rmtree(checkout)
    task = replace(task, followups=({'followup_id': 1, 'followup_text': 'Use welcome'},))
    payload.write_text(json.dumps(task.payload()))
    gh.open_pulls.return_value = [{'html_url': PR, 'number': 123, 'node_id': 'PR_fixture', 'draft': False}]
    edit[0] = 'welcome\n'
    assert entry.main() == 0
    second = parse_result(capsys.readouterr().out)
    assert second.pr_url == first.pr_url and second.sha != first_sha
    assert git('--git-dir', str(remote), 'show', f'{task.branch}:greeting.txt') == 'welcome'
    assert git('--git-dir', str(remote), 'show', 'main:greeting.txt') == 'before'
    gh.create_draft.assert_awaited_once()
    gh.mark_draft.assert_awaited_once_with(TOKEN, 'PR_fixture')
    # Follow-ups still enforce the original confirmed file scope before pushing.
    shutil.rmtree(checkout)
    edit[1] = 'unapproved.txt'
    assert entry.main() == 1
    assert 'file list' in parse_result(capsys.readouterr().out).detail
    assert git('--git-dir', str(remote), 'rev-parse', f'refs/heads/{task.branch}') == second.sha
    # Closed original PRs never cause replacement PRs on the next reply.
    shutil.rmtree(checkout)
    gh.open_pulls.return_value = []
    assert entry.main() == 1
    assert 'no longer open' in parse_result(capsys.readouterr().out).detail
    gh.create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_runs_can_pass_without_legacy_commit_statuses():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
        'state': 'pending', 'total_count': 0, 'statuses': [],
    }))) as client:
        assert await GitHub('Tervory-AI/tervory-tank', client).combined_status(TOKEN, 'a' * 40) == ''
