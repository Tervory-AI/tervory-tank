"""GitHub API used by the service. Reads issues, opens draft PRs, never merges."""

from __future__ import annotations

from typing import Any

import httpx

from workers.github_app import (
    APP_PERMISSIONS,
    TokenRejected,
    assert_installation_token,
    installation_token_body,
    read_private_key,
    sign_app_jwt,
)
from workers.issues import WorkerIssue, issue_from_api, needs_brief_comment

API = "https://api.github.com"
_ACCEPT = "application/vnd.github+json"


class GitHubError(RuntimeError):
    pass


def _headers(token: str) -> dict[str, str]:
    assert_installation_token(token)
    return {
        "Accept": _ACCEPT,
        "User-Agent": "tervory-workers",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class GitHub:
    def __init__(self, repo: str, client: httpx.AsyncClient) -> None:
        if repo.count("/") != 1:
            raise GitHubError("repo must be owner/name")
        self.repo = repo
        self.client = client

    async def _send(self, method: str, url: str, token: str, body: dict[str, Any] | None = None) -> Any:
        if not url.startswith(f"{API}/"):
            raise GitHubError("refusing a GitHub URL outside api.github.com")
        if "/merge" in url or url.rstrip("/").endswith("/merges"):
            raise GitHubError("the worker token cannot merge")
        response = await self.client.request(method, url, headers=_headers(token), json=body)
        if response.status_code >= 400:
            raise GitHubError(f"GitHub {response.status_code} on {method} {url.split('?')[0]}")
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def mint_installation_token(self, *, app_id: str, installation_id: str, key_file: str) -> str:
        if not installation_id.isdigit():
            raise TokenRejected()
        jwt = sign_app_jwt(app_id, read_private_key(key_file))
        url = f"{API}/app/installations/{installation_id}/access_tokens"
        response = await self.client.post(
            url,
            headers={
                "Accept": _ACCEPT,
                "User-Agent": "tervory-workers",
                "Authorization": f"Bearer {jwt}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=installation_token_body(self.repo),
        )
        if response.status_code >= 400:
            raise GitHubError("GitHub refused the installation token")
        payload = response.json()
        permissions = payload.get("permissions") or {}
        if isinstance(permissions, dict) and set(permissions) - set(APP_PERMISSIONS):
            raise TokenRejected()
        token = str(payload.get("token") or "")
        assert_installation_token(token)
        return token

    async def list_issues(self, token: str) -> list[dict[str, Any]]:
        url = f"{API}/repos/{self.repo}/issues?labels=worker&state=open&per_page=50"
        payload = await self._send("GET", url, token)
        if not isinstance(payload, list):
            raise GitHubError("issue list was not a list")
        return payload

    def tasks(self, payloads: list[dict[str, Any]]) -> list[WorkerIssue]:
        tasks: list[WorkerIssue] = []
        for payload in payloads:
            task = issue_from_api(payload)
            if task is not None:
                tasks.append(task)
        return tasks

    def malformed(self, payloads: list[dict[str, Any]]) -> list[int]:
        numbers: list[int] = []
        for payload in payloads:
            if needs_brief_comment(payload) and isinstance(payload.get("number"), int):
                numbers.append(payload["number"])
        return numbers

    async def comment(self, token: str, number: int, body: str) -> None:
        url = f"{API}/repos/{self.repo}/issues/{number}/comments"
        await self._send("POST", url, token, {"body": body})

    async def open_pulls(self, token: str, branch: str) -> list[dict[str, Any]]:
        owner = self.repo.split("/", 1)[0]
        url = f"{API}/repos/{self.repo}/pulls?state=open&head={owner}:{branch}&per_page=20"
        payload = await self._send("GET", url, token)
        if not isinstance(payload, list):
            raise GitHubError("pull list was not a list")
        return payload

    async def create_draft(self, token: str, *, branch: str, title: str, body: str) -> dict[str, Any]:
        url = f"{API}/repos/{self.repo}/pulls"
        created = await self._send(
            "POST",
            url,
            token,
            {"title": title[:200], "head": branch, "base": "main", "body": body, "draft": True},
        )
        if not isinstance(created, dict) or created.get("draft") is not True:
            raise GitHubError("GitHub did not open a draft pull request")
        return created

    async def check_runs(self, token: str, sha: str) -> list[dict[str, Any]]:
        if not sha or any(char not in "0123456789abcdef" for char in sha.lower()) or len(sha) < 7:
            raise GitHubError("refusing to read checks for an unexpected revision")
        url = f"{API}/repos/{self.repo}/commits/{sha}/check-runs?per_page=100"
        payload = await self._send("GET", url, token)
        runs = payload.get("check_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise GitHubError("check runs were missing")
        return runs

    async def combined_status(self, token: str, sha: str) -> str:
        url = f"{API}/repos/{self.repo}/commits/{sha}/status"
        payload = await self._send("GET", url, token)
        state = payload.get("state") if isinstance(payload, dict) else None
        return str(state or "pending")

    async def mark_ready(self, token: str, *, node_id: str, body: str, number: int) -> None:
        if not node_id or len(node_id) > 200:
            raise GitHubError("missing pull request id")
        mutation = {
            "query": (
                "mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id})"
                "{pullRequest{isDraft number url}}}"
            ),
            "variables": {"id": node_id},
        }
        if "mergePullRequest" in mutation["query"]:
            raise GitHubError("the worker token cannot merge")
        result = await self._send("POST", f"{API}/graphql", token, mutation)
        errors = result.get("errors") if isinstance(result, dict) else None
        if errors:
            raise GitHubError("GitHub did not mark the pull request ready")
        url = f"{API}/repos/{self.repo}/pulls/{number}"
        await self._send("PATCH", url, token, {"body": body})


def ci_state(check_runs: list[dict[str, Any]], combined: str) -> str:
    """pending, green, or red. No checks yet is pending, so a draft is not marked ready early."""
    if not check_runs and combined in {"", "pending"}:
        return "pending"
    for run in check_runs:
        status = str(run.get("status") or "")
        if status != "completed":
            return "pending"
        conclusion = str(run.get("conclusion") or "")
        if conclusion in {"failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}:
            return "red"
        if conclusion not in {"success", "skipped", "neutral"}:
            return "pending"
    if combined == "failure" or combined == "error":
        return "red"
    if combined == "pending":
        return "pending"
    successes = [run for run in check_runs if run.get("conclusion") == "success"]
    if successes or combined == "success":
        return "green"
    return "pending"


def ready_body(summary: str) -> str:
    text = summary.strip()
    if text.lower().startswith("ready for review"):
        return text + "\n"
    return "ready for review\n\n" + text + "\n"


def draft_body(issue: WorkerIssue) -> str:
    title = " ".join(issue.title.split())
    return (
        f"Draft opened for issue #{issue.number}: {title}.\n\n"
        f"Brief: {issue.brief}\n\n"
        "This stays a draft until CI is green. The worker does not merge.\n"
    )

