"""GitHub on the user's repository; reuse worker API and branch guards."""
from __future__ import annotations

import re

from workers.github_api import API, GitHub, GitHubError
from workers.github_app import assert_push_branch


class UserGitHub(GitHub):
    async def _send(self, method, url, token, body=None):
        prefix = f'{API}/repos/{self.repo}'
        if not (url == prefix or url.startswith(prefix + '/')) or '/merge' in url:
            raise GitHubError('GitHub operation refused')
        if not re.fullmatch(r'(?:github_pat_|gh[pous]_)[A-Za-z0-9_]+', token):
            raise GitHubError('Named GitHub credential refused')
        response = await self.client.request(method, url, json=body, headers={
            'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'tervory-workers',
        })
        if response.status_code >= 400:
            raise GitHubError(f'GitHub refused operation ({response.status_code})')
        return response.json() if response.content else {}

    async def default_branch(self, token):
        repo = await self._send('GET', f'{API}/repos/{self.repo}', token)
        branch = repo.get('default_branch', '')
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}', branch) or '..' in branch:
            raise GitHubError('Repository default branch refused')
        if repo.get('permissions', {}).get('push') is not True:
            raise GitHubError('This credential cannot write the selected repository')
        return branch

    async def draft(self, token, branch, base, title):
        assert_push_branch(branch)
        return await self._send('POST', f'{API}/repos/{self.repo}/pulls', token, {
            'head': branch, 'base': base, 'title': title[:200], 'draft': True,
            'body': 'Background task completed. See the Tervory receipt for model usage. Review before merging.',
        })
