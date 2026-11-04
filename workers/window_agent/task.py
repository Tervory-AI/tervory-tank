"""Non-root task entry. Use the existing loop and publish only a new branch."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx

from workers.git_guard import clone_command
from workers.github_app import assert_push_branch
from workers.task_run import git_identity, Outcome
from workers.window_agent.github import UserGitHub

ROOT = Path('/work/repo')
HELPER = 'credential.helper=!python3 -m workers.window_agent.credential'


def run(argv, cwd=ROOT, *, timeout=300):
    result = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError('Repository command failed')
    return result.stdout.decode().strip()


async def task(job, token, client):
    github = UserGitHub(job['repo'], client)
    base = await github.default_branch(token)
    branch = assert_push_branch('worker/window-' + job['job_id'])
    clone = clone_command(job['repo'], str(ROOT))
    clone[clone.index('credential.helper=!python3 -m workers.git_guard')] = HELPER
    clone[clone.index('--branch') + 1] = base
    run(clone, Path('/work'))
    run(['git', 'checkout', '-b', branch])
    for argv in git_identity():
        run(argv)
    run(['node', '/opt/tervory/workers/window_agent/loop.mjs'], timeout=5400)
    run(['git', 'add', '--all'])
    # A no-change task produces no misleading empty PR.
    run(['git', 'commit', '-m', 'Apply background task'])
    sha = run(['git', 'rev-parse', 'HEAD'])
    run(['git', '-c', 'credential.helper=', '-c', HELPER, 'push', 'origin', f'HEAD:refs/heads/{branch}'])
    created = await github.draft(token, branch, base, job['prompt'].splitlines()[0])
    return Outcome(status='draft', pr_url=created['html_url'], pr_number=created['number'], sha=sha)


def main():
    if os.getuid() == 0:
        raise SystemExit('Task must run without root')
    job = json.loads(Path('/run/secrets/job.json').read_text())
    token = Path('/run/secrets/token').read_text().strip()

    async def execute():
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            return await task(job, token, client)
    try:
        result = asyncio.run(execute())
    except Exception:
        result = Outcome(status='failed', detail='Task stopped; inspect its branch before retrying.')
    print(result.line(), flush=True)
    return 0 if result.pr_url else 1


if __name__ == '__main__':
    raise SystemExit(main())
