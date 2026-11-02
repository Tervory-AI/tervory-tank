"""Offline GitHub transport plus Command's real auth/dispatch/persistence paths."""
import base64
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException

import command
import command_repo as repo
from test_command import TENANT, OTHER
import test_command as command_tests

api = command_tests.api
command_pool = command_tests.command_pool
runtime = command_tests.runtime

TOOLS = {"repo.prs", "repo.pr", "repo.file"}
HEAD = "a" * 40
TREE = "b" * 40
BLOB = "c" * 40
ROOT = "/repos/Tervory-AI/tervory-tank/"
# This is an inert test marker, never a GitHub credential.
MARKER = "offline-stub-only"


def pull(number=17):
    return {"number": number, "title": "Read repository briefs", "draft": True,
            "head": {"sha": HEAD, "ref": "codex/repository-read"}, "body": "not exposed"}


class GitHubStub:
    def __init__(self):
        self.requests = []
        self.reply = self.default

    def __call__(self, request):
        # Every runtime GitHub request is captured here; this transport has no sockets.
        assert request.method == "GET"
        assert request.url.scheme == "https" and request.url.host == "api.github.com"
        assert request.url.port is None
        assert request.url.path.startswith(ROOT)
        assert request.headers["authorization"] == "Bearer " + MARKER
        assert "tenant_id" not in request.url.params
        self.requests.append(request)
        return self.reply(request)

    @staticmethod
    def default(request):
        path = request.url.path.removeprefix(ROOT)
        if path == "pulls":
            assert request.url.params["state"] == "open"
            return httpx.Response(200, json=[pull()])
        if path == "pulls/17":
            return httpx.Response(200, json=pull())
        if path == "pulls/17/files":
            return httpx.Response(200, json=[{"filename": "docs/brief.md", "status": "modified",
                "additions": 2, "deletions": 1, "changes": 3, "patch": "not exposed"}])
        if path == f"commits/{HEAD}/check-runs":
            return httpx.Response(200, json={"check_runs": [{"name": "CI", "status": "completed", "conclusion": "success"}]})
        if path == f"commits/{HEAD}/status":
            return httpx.Response(200, json={"statuses": [{"context": "deploy", "state": "success"}]})
        if path == "git/trees/main":
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": "docs", "type": "tree", "mode": "040000", "sha": TREE},
                {"path": "AGENTS.md", "type": "blob", "mode": "100644", "sha": BLOB}]})
        if path == f"git/trees/{TREE}":
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": "brief.md", "type": "blob", "mode": "100644", "sha": BLOB},
                {"path": "reference.tsx", "type": "blob", "mode": "100644", "sha": BLOB}]})
        if path == f"git/blobs/{BLOB}":
            raw = "# Brief\nRead only — preserve this spacing.\n".encode()
            return httpx.Response(200, json={"encoding": "base64", "size": len(raw), "content": base64.b64encode(raw).decode()})
        raise AssertionError("Unexpected GitHub path: " + path)


@pytest.fixture
def github(monkeypatch):
    stub = GitHubStub()
    original = httpx.AsyncClient

    def client(*args, **kwargs):
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(stub)
        else:
            assert isinstance(kwargs["transport"], httpx.ASGITransport)
        return original(*args, **kwargs)

    monkeypatch.setenv("TANK_GITHUB_READ_TOKEN", MARKER)
    monkeypatch.setattr(httpx, "AsyncClient", client)
    return stub


@pytest_asyncio.fixture
async def http_api(runtime, monkeypatch, github):
    async def fetch(sql, *args):
        if "JOIN tank.mcp_servers" in sql:
            assert "v.tenant_id=$1" in sql and args == (TENANT,)
            return []  # No saved MCP connection in this repository-tools fixture.
        assert "tank.tenant_squad" in sql
        return [{"agent": squad} for squad in command.SQUADS]

    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(fetch=fetch)

    monkeypatch.setattr(command, "db", lambda: SimpleNamespace(acquire=acquire))
    app = runtime.app = FastAPI()
    app.include_router(command.router)
    headers = {"x-tank-key": runtime.TANK_API_KEY, "x-tervory-user": "founder", "x-tervory-tenant": str(TENANT)}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank.internal", headers=headers) as client:
        yield client


@pytest.mark.asyncio
async def test_founder_catalogue_and_client_never_offered_or_allowed(http_api, github):
    founder = (await http_api.get("/v1/command/tools")).json()
    assert TOOLS <= set(founder)
    prompt = command.planning_message(command.Actor(TENANT, "founder", True))["content"]
    assert all(tool in prompt for tool in TOOLS)
    for tenant in (TENANT, OTHER):
        headers = {"x-tervory-user": "client", "x-tervory-tenant": str(tenant), "x-tervory-admin": "founder"}
        offered = (await http_api.get("/v1/command/tools", headers=headers)).json()
        assert not TOOLS & set(offered)
        for name, params in (("prs", {}), ("pr", {"number": 17}), ("file", {"path": "AGENTS.md"})):
            assert (await http_api.get("/v1/command/repo/" + name, params=params, headers=headers)).status_code == 403
            with pytest.raises(HTTPException) as denied:
                await command.dispatch_action(command.PlannedAction(tool="repo." + name, arguments=params), command.Actor(tenant, "client", True, command.SQUADS))
            assert denied.value.status_code == 403
        assert not any(tool in command.planning_message(command.Actor(tenant, "client", False, command.SQUADS))["content"] for tool in TOOLS)
    assert github.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("setting", [None, "", "   "])
async def test_missing_setting_hides_and_disables_even_old_actions(http_api, github, monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv("TANK_GITHUB_READ_TOKEN")
    else:
        monkeypatch.setenv("TANK_GITHUB_READ_TOKEN", setting)
    assert not TOOLS & set((await http_api.get("/v1/command/tools")).json())
    for tool, args in (("repo.prs", {}), ("repo.pr", {"number": 17}), ("repo.file", {"path": "AGENTS.md"})):
        with pytest.raises(HTTPException) as denied:
            await command.dispatch_action(command.PlannedAction(tool=tool, arguments=args), command.Actor(TENANT, "founder", True))
        assert denied.value.status_code == 403
    assert github.requests == []


@pytest.mark.asyncio
async def test_real_dispatch_returns_pr_fields_checks_and_changed_files(http_api, github):
    actor = command.Actor(TENANT, "founder", True)
    status, data = await command.dispatch_action(command.PlannedAction(tool="repo.prs"), actor)
    assert status == 200
    pr = data["items"][0]
    assert (pr["number"], pr["title"], pr["draft"], pr["branch"]) == (17, pull()["title"], True, pull()["head"]["ref"])
    assert pr["head_sha"] == HEAD and pr["checks_green"] is True
    assert pr["checks"][0]["name"] == "CI" and pr["statuses"][0]["context"] == "deploy"
    assert data["has_more"] is False and data["next_page"] is None
    status, detail = await command.dispatch_action(command.PlannedAction(tool="repo.pr", arguments={"number": 17}), actor)
    assert status == 200 and detail["files"] == [{"filename": "docs/brief.md", "status": "modified", "additions": 2, "deletions": 1, "changes": 3}]
    assert detail["checks_green"] is True
    assert "not exposed" not in json.dumps([data, detail])
    assert "patch" not in detail["text"] and MARKER not in json.dumps(detail)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def test_non_get_routes_impossible(http_api, github, method):
    for path in ("prs", "pr?number=17", "file?path=AGENTS.md"):
        assert (await http_api.request(method, "/v1/command/repo/" + path)).status_code == 405
    assert github.requests == []


@pytest.mark.parametrize("key,value", [("method", "POST"), ("url", "https://other.invalid/"), ("repository", "other/repo"), ("ref", "other"), ("tenant_id", str(OTHER)), ("token", MARKER)])
def test_no_caller_override(github, key, value):
    for tool, arguments in (("repo.prs", {}), ("repo.pr", {"number": 17}), ("repo.file", {"path": "AGENTS.md"})):
        with pytest.raises(HTTPException) as denied:
            command.validate_action(command.PlannedAction(tool=tool, arguments={**arguments, key: value}), command.Actor(TENANT, "founder", True))
        assert denied.value.status_code == 422
    assert github.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["tank/main.py", ".env", "workspace/package.json", "docs", "", "/docs/brief.md", "docs/../.env", "../AGENTS.md", "docs/./brief.md", "docs//brief.md", "docs/%2e%2e/.env", "docs/%252e%252e/.env", "docs\\brief.md", "docs/brief.md?ref=other", "docs/brief.md#fragment", "https://other.invalid/x.md", "docs/brief\x00.md", "AGENTS.MD"])
async def test_disallowed_files_never_reach_github(http_api, github, path):
    assert (await http_api.get("/v1/command/repo/file", params={"path": path})).status_code == 422
    with pytest.raises(HTTPException) as denied:
        command.validate_action(command.PlannedAction(tool="repo.file", arguments={"path": path}), command.Actor(TENANT, "founder", True))
    assert denied.value.status_code == 422
    assert github.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["AGENTS.md", "docs/brief.md", "docs/reference.tsx"])
async def test_file_read_main_exact_utf8_and_no_arbitrary_content_endpoint(http_api, github, path):
    status, result = await command.dispatch_action(command.PlannedAction(tool="repo.file", arguments={"path": path}), command.Actor(TENANT, "founder", True))
    assert status == 200 and result == {"name": path, "ref": "main", "sha": BLOB, "text": "# Brief\nRead only — preserve this spacing.\n"}
    assert github.requests[0].url.path == ROOT + "git/trees/main"
    assert github.requests[-1].url.path == ROOT + "git/blobs/" + BLOB
    assert all(not request.url.query for request in github.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("entry_type,mode", [("blob", "120000"), ("commit", "160000"), ("tree", "040000")])
async def test_symlink_submodule_or_directory_not_read(http_api, github, entry_type, mode):
    github.reply = lambda request: httpx.Response(200, json={"truncated": False, "tree": [{"path": "AGENTS.md", "type": entry_type, "mode": mode, "sha": BLOB}]})
    assert (await http_api.get("/v1/command/repo/file", params={"path": "AGENTS.md"})).status_code == 422
    assert len(github.requests) == 1


@pytest.mark.asyncio
async def test_symlink_parent_not_traversed(http_api, github):
    github.reply = lambda request: httpx.Response(200, json={"truncated": False, "tree": [{"path": "docs", "type": "blob", "mode": "120000", "sha": BLOB}]})
    assert (await http_api.get("/v1/command/repo/file", params={"path": "docs/brief.md"})).status_code == 422
    assert len(github.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("conclusion,statuses,expected", [("failure", [], "failure"), ("cancelled", [], "failure"), (None, [], "pending"), ("success", ["pending"], "pending"), ("success", ["failure"], "failure"), ("success", ["error"], "failure"), ("success", ["success"], "success"), ("skipped", [], "success"), ("neutral", [], "success")])
async def test_checks_never_hide_failed_or_pending_results(http_api, github, conclusion, statuses, expected):
    def reply(request):
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(200, json={"check_runs": [{"name": "CI", "status": "completed" if conclusion else "in_progress", "conclusion": conclusion}]})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"statuses": [{"context": "deploy", "state": s} for s in statuses]})
        return github.default(request)
    github.reply = reply
    result = (await http_api.get("/v1/command/repo/prs")).json()["items"][0]
    assert result["checks_state"] == expected and result["checks_green"] == (expected == "success")


@pytest.mark.asyncio
async def test_absent_and_incomplete_checks_are_unknown(http_api, github, monkeypatch):
    monkeypatch.setattr(repo, "MAX_CHECK_PAGES", 2)
    for incomplete in (False, True):
        def reply(request):
            if request.url.path.endswith(("/check-runs", "/status")):
                body = {"check_runs": [], "statuses": []}
                if incomplete:
                    body["check_runs"] = [{"name": "CI", "status": "completed", "conclusion": "success"}]
                return httpx.Response(200, json=body, headers={"Link": '<https://other.invalid/>; rel="next"'} if incomplete else {})
            return github.default(request)
        github.reply = reply
        result = (await http_api.get("/v1/command/repo/prs")).json()["items"][0]
        assert result["checks_state"] == "unknown" and result["checks_green"] is None
        assert result["checks_complete"] is not incomplete


@pytest.mark.asyncio
async def test_pagination_pins_host_and_later_failure_is_not_green(http_api, github):
    def reply(request):
        if request.url.path == ROOT + "pulls":
            return httpx.Response(200, json=[pull()], headers={"Link": '<https://other.invalid/steal>; rel="next"'})
        if request.url.path.endswith("/check-runs"):
            second = request.url.params["page"] == "2"
            return httpx.Response(200, json={"check_runs": [{"name": "CI", "status": "completed", "conclusion": "failure" if second else "success"}]}, headers={} if second else {"Link": '<https://other.invalid/>; rel="next"'})
        return github.default(request)
    github.reply = reply
    result = (await http_api.get("/v1/command/repo/prs", params={"page": 3, "limit": 1})).json()
    assert result["page"] == 3 and result["next_page"] == 4 and result["has_more"] is True
    assert result["items"][0]["checks_green"] is False
    assert len(result["items"][0]["checks"]) == 2
    assert '"next_page": 4' in result["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [301, 302, 307, 401, 403, 404, 429, 500])
async def test_redirects_and_api_errors_never_leak_or_follow(http_api, github, code):
    github.reply = lambda request: httpx.Response(code, text="private upstream response", headers={"Location": "https://other.invalid/"})
    result = await http_api.get("/v1/command/repo/prs")
    assert result.status_code == 502 and result.json() == {"detail": repo.FAILURE}
    assert len(github.requests) == 1 and MARKER not in result.text


@pytest.mark.asyncio
async def test_network_error_is_sanitized(http_api, github):
    def failed(request):
        raise httpx.ConnectError("private upstream detail", request=request)
    github.reply = failed
    result = await http_api.get("/v1/command/repo/prs")
    assert result.status_code == 502 and result.json() == {"detail": repo.FAILURE}


@pytest.mark.asyncio
async def test_get_helper_refuses_write_paths_and_arbitrary_hosts(github):
    async with repo.github() as client:
        for path in ("issues/17/comments", "pulls/17/merge", "../other", "https://other.invalid/", "git/trees/other", "pulls/17?state=closed"):
            with pytest.raises(HTTPException) as denied:
                await repo._get(client, path)
            assert denied.value.status_code == 422
        with pytest.raises(TypeError):
            await repo._get(client, "pulls", method="POST")
    assert github.requests == []


@pytest.mark.asyncio
async def test_confirmed_read_saved_replayed_and_isolated(api, runtime, github, monkeypatch):
    client, pool = api
    runtime.app = client._transport.app
    question = "which PRs are open and are their checks green?"
    ledger_id = await command_tests.seed_ledger(pool)
    planner = AsyncMock(return_value=SimpleNamespace(ledger_id=ledger_id, content=json.dumps({
        "text": "", "actions": [{"tool": "repo.prs", "arguments": {}}]})))
    monkeypatch.setattr(command, "route_turn", planner)
    thread = (await client.post("/v1/command/threads", json={"title": question})).json()["thread_id"]
    assert (await client.post(f"/v1/command/threads/{thread}/turn", json={"text": question})).status_code == 200
    data = (await client.get(f"/v1/command/threads/{thread}")).json()
    assert planner.call_args.args[1][-1]["content"] == question
    assert "repo.prs" in planner.call_args.args[1][0]["content"]
    card = data["cards"][0]
    assert card["status"] == "pending" and github.requests == []
    url = f"/v1/command/cards/{card['card_id']}"
    monkeypatch.setenv("TANK_GITHUB_READ_TOKEN", "")
    assert (await client.post(url, json={"action": "confirm"})).status_code == 403
    monkeypatch.setenv("TANK_GITHUB_READ_TOKEN", MARKER)
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "")
    assert (await client.post(url, json={"action": "confirm"})).status_code == 403
    assert github.requests == []
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder")
    assert (await client.post(url, json={"action": "confirm"})).json()["status"] == "confirmed"
    count = len(github.requests)
    assert count == 3
    assert (await client.post(url, json={"action": "confirm"})).json()["status"] == "confirmed"
    assert len(github.requests) == count
    saved = (await client.get(f"/v1/command/threads/{thread}")).json()
    result = saved["cards"][0]["result"]
    assert result["items"][0]["checks_green"] is True
    assert '"number": 17' in result["text"]
    events = (await client.get(f"/v1/command/threads/{thread}/events")).text
    assert "checks_green" in events and MARKER not in events
    for headers in ({"x-tervory-user": "client"}, {"x-tervory-tenant": str(OTHER)}):
        assert (await client.get(f"/v1/command/threads/{thread}", headers=headers)).status_code == 404
        assert (await client.get(f"/v1/command/threads/{thread}/events", headers=headers)).status_code == 404
        assert (await client.post(url, json={"action": "confirm"}, headers=headers)).status_code == 404
        assert (await client.get("/v1/command/threads", headers=headers)).json() == []
    # Optional browser handoff is a real saved snapshot from this offline integration,
    # not a hand-authored result or a live GitHub claim.
    proof = os.environ.get("COMMAND_REPO_SNAPSHOT")
    if proof:
        Path(proof).write_text(json.dumps(saved, ensure_ascii=False))
        Path(proof + ".pending").write_text(json.dumps(data, ensure_ascii=False))


@pytest.mark.asyncio
async def test_entire_page_visible_beyond_the_existing_five_item_preview(http_api, github):
    github.reply = lambda request: httpx.Response(200, json=[pull(number) for number in range(1, 8)]) if request.url.path == ROOT + "pulls" else github.default(request)
    result = (await http_api.get("/v1/command/repo/prs")).json()
    assert result["count"] == 7
    assert [row["number"] for row in json.loads(result["text"])["items"]] == list(range(1, 8))


@pytest.mark.asyncio
async def test_pr_file_pagination_excludes_patches(http_api, github):
    def reply(request):
        if request.url.path.endswith("/files"):
            assert dict(request.url.params) == {"page": "2", "per_page": "1"}
            return httpx.Response(200, json=[{"filename": "new.md", "previous_filename": "old.md", "status": "renamed", "patch": "not exposed"}], headers={"Link": '<https://other.invalid/>; rel="next"'})
        return github.default(request)
    github.reply = reply
    result = (await http_api.get("/v1/command/repo/pr", params={"number": 17, "page": 2, "limit": 1})).json()
    assert result["page"] == 2 and result["next_page"] == 3 and result["has_more"] is True
    assert result["files"] == [{"filename": "new.md", "previous_filename": "old.md", "status": "renamed"}]
    assert "not exposed" not in result["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"number": 0}, {"number": -1}, {"number": "17/merge"}, {"number": 17, "page": 0}, {"number": 17, "limit": 51}])
async def test_invalid_pr_arguments_refused_before_request(http_api, github, params):
    assert (await http_api.get("/v1/command/repo/pr", params=params)).status_code == 422
    assert github.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [(b"not JSON", 502), (b"null", 502), (b"{}", 502), (b"x" * 1025, 413)])
async def test_malformed_or_oversized_response_refused(http_api, github, monkeypatch, body, expected):
    monkeypatch.setattr(repo, "MAX_RESPONSE_BYTES", 1024)
    github.reply = lambda request: httpx.Response(200, content=body)
    response = await http_api.get("/v1/command/repo/prs")
    assert response.status_code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [
    ({"truncated": True, "tree": []}, 502),
    ({"truncated": False, "tree": []}, 404),
    ({"truncated": False, "tree": [{"path": "AGENTS.md", "type": "blob", "mode": "100644", "sha": "../other"}]}, 502),
])
async def test_missing_truncated_or_invalid_tree_refused(http_api, github, body, expected):
    github.reply = lambda request: httpx.Response(200, json=body)
    assert (await http_api.get("/v1/command/repo/file", params={"path": "AGENTS.md"})).status_code == expected
    assert len(github.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"encoding": "base64", "size": 1, "content": "AA=="},
    {"encoding": "base64", "size": 1, "content": "/w=="},
    {"encoding": "base64", "size": 0, "content": "invalid"},
    {"encoding": "base64", "size": 64001, "content": ""},
    {"encoding": "base64", "size": 0, "content": "YQ=="},
])
async def test_binary_invalid_or_oversized_file_refused(http_api, github, body):
    github.reply = lambda request: httpx.Response(200, json=body) if "/blobs/" in request.url.path else github.default(request)
    assert (await http_api.get("/v1/command/repo/file", params={"path": "AGENTS.md"})).status_code == 422
