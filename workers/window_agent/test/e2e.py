"""Manual offline acceptance: real CLI edits and git; fake GitHub and Tank.

Run after npm ci --prefix cli:
  PYTHONPATH=. python workers/window_agent/test/e2e.py
No live model, provider, GitHub mutation, database or Docker socket is used.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx

from workers.window_agent import task as task_module
from workers.window_agent.github import UserGitHub
from workers.window_agent.review import review

SOURCE = Path(__file__).resolve().parents[3]


def git(*argv, cwd=None):
    return subprocess.check_output(['git', *argv], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()


async def acceptance(root):
    seed, remote, checkout = root / 'seed', root / 'remote.git', root / 'repo'
    seed.mkdir()
    git('init', '-b', 'develop', cwd=seed)
    git('config', 'user.name', 'Acceptance', cwd=seed)
    git('config', 'user.email', 'acceptance@example.invalid', cwd=seed)
    (seed / 'file.txt').write_text('old\n')
    git('add', 'file.txt', cwd=seed)
    git('commit', '-m', 'Seed', cwd=seed)
    git('clone', '--bare', str(seed), str(remote))
    job = {'job_id': str(uuid.uuid4()), 'repo': 'alice/project', 'prompt': 'Update file.txt', 'pull_number': 8}
    branch = 'worker/window-' + job['job_id']
    calls, task_receipts, review_receipts = [], [], []
    created = False
    published = False

    def fake_github(request):
        nonlocal created, published
        calls.append((request.method, request.url.path))
        assert request.url.host == 'api.github.com' and '/merge' not in request.url.path
        path = request.url.path
        if path == '/repos/alice/project':
            return httpx.Response(200, json={'default_branch': 'develop', 'permissions': {'push': True}})
        if path.endswith('/pulls') and request.method == 'POST':
            body = json.loads(request.content)
            assert body['head'] == branch and body['base'] == 'develop' and body['draft'] is True
            git('--git-dir', str(remote), 'rev-parse', 'refs/heads/' + branch)
            created = True
            return httpx.Response(201, json={'number': 8, 'html_url': 'https://github.com/alice/project/pull/8'})
        sha = git('--git-dir', str(remote), 'rev-parse', 'refs/heads/' + branch)
        if path.endswith('/pulls/8'):
            assert created
            return httpx.Response(200, json={'state': 'open', 'head': {'sha': sha}, 'changed_files': 1,
                'base': {'repo': {'full_name': 'alice/project'}}})
        if path.endswith('/files'):
            diff = git('--git-dir', str(remote), 'diff', 'develop...' + branch, '--', 'file.txt')
            return httpx.Response(200, json=[{'filename': 'file.txt', 'patch': diff[diff.index('@@'):]}])
        if path.endswith('/reviews'):
            body = json.loads(request.content)
            assert body['event'] == 'COMMENT' and body['commit_id'] == sha
            assert body['comments'][0]['path'] == 'file.txt' and body['comments'][0]['line'] == 1
            published = True
            return httpx.Response(200, json={'id': 1})
        raise AssertionError('Unexpected GitHub request')

    original = task_module.run

    def run(argv, cwd=None, **kwargs):
        if 'clone' in argv:
            assert argv[-2] == 'https://github.com/alice/project.git'
            return original(['git', 'clone', '--depth', '1', '--branch', 'develop', remote.as_uri(), str(checkout)], root)
        if argv[0] == 'node':
            result = subprocess.check_output(['node', str(SOURCE / 'workers/window_agent/test/fake-loop.mjs'), str(checkout)], text=True, timeout=60)
            task_receipts.extend(json.loads(result)['receipts'])
            return ''
        return original(argv, cwd or checkout, **kwargs)

    async def turn(body):
        assert body['model'] == 'auto' and 'file.txt' in body['history'][0]['content']
        receipt = {'ledger_id': str(uuid.uuid4()), 'cost_usd': 0}
        review_receipts.append(receipt)
        return {'answer': json.dumps({'summary': 'Fixture review', 'comments': [
            {'path': 'file.txt', 'line': 1, 'body': 'Fixture comment on the changed line.'}]}),
            'requests': [], 'receipt': {'rows': [receipt]}}

    async def heartbeat():
        return None

    token = 'github_pat_' + 'test' * 8
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake_github)) as client:
        with patch.object(task_module, 'ROOT', checkout), patch.object(task_module, 'run', run):
            outcome = await task_module.task(job, token, client)
        assert created and outcome.pr_number == 8 and task_receipts
        assert (checkout / 'file.txt').read_text() == 'new\n'
        result = await review(job, UserGitHub(job['repo'], client), token, turn, heartbeat)
    assert published and review_receipts and result['status'] == 'done'
    return {'status': 'passed', 'sequence': ['task', 'branch', 'PR', 'review'],
            'branch': branch, 'pr_url': outcome.pr_url, 'task_receipts': len(task_receipts),
            'review_receipts': len(review_receipts), 'github_operations': len(calls)}


def main():
    directory = os.environ.get('TMPDIR')
    with tempfile.TemporaryDirectory(prefix='window-agents-e2e-', dir=directory) as temporary:
        print(json.dumps(asyncio.run(acceptance(Path(temporary))), sort_keys=True))


if __name__ == '__main__':
    main()
