"""WORKERS-1: own build workers. No database, no network, no real tokens."""

from __future__ import annotations

import ast
import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from workers.briefs import allowed_rules, outside_rules, path_allowed
from workers.egress import HostRefused, Policy, nft_script
from workers.egress_apply import apply
from workers.git_guard import clone_command, credential_fill, push_command
from workers.github_api import GitHub, GitHubError, ci_state, draft_body, ready_body
from workers.github_app import (
    APP_PERMISSIONS,
    JWT_TTL_S,
    TOKEN_MAX_S,
    MainPushRefused,
    MergeRefused,
    TokenRejected,
    assert_installation_token,
    installation_token_body,
    jwt_claims,
    merge_pull_request,
    sign_app_jwt,
)
from workers.issues import WorkerIssue, briefs_named, issue_from_api
from workers.podman_run import choose_runtime, kill_argv, task_argv
from workers.proxy import forward_chat
from workers.redact import redact
from workers.secrets_io import stage
from workers.service import Service
from workers.settings import PLATFORM_TENANT, Settings, SettingsError, from_mapping
from workers.status_page import render
from workers.tank_route import assert_tank_destination, normalize_messages, route_body
from workers.task_run import (
    aider_argv,
    changed_paths,
    commit_paths,
    finish_from_ci,
    parse_result,
)

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "ghs_example"
SHA = "abcdef1234567890"


def _key_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _settings(**kwargs: object) -> Settings:
    base = dict(
        max_tasks=1,
        task_cpus=2,
        task_memory="4g",
        task_timeout_s=90 * 60,
        link="internal",
        tank_url="http://tank:8000",
        tenant_id=PLATFORM_TENANT,
        task_type="reason.brief",
        repo="Tervory-AI/tervory-tank",
        app_id="12345",
        installation_id="99",
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def test_boston_defaults_and_wireguard_and_za() -> None:
    settings = from_mapping({})
    assert settings.max_tasks == 1
    assert settings.task_cpus == 2
    assert settings.task_memory == "4g"
    assert settings.task_timeout_s == 90 * 60
    assert settings.link == "internal"
    assert settings.tank_url == "http://tank:8000"
    assert settings.tenant_id == PLATFORM_TENANT
    wire = from_mapping({"WORKER_LINK": "wireguard", "TANK_URL": "http://10.90.0.1:8000"})
    assert wire.tank_host == "10.90.0.1"
    assert wire.route_url() == "http://10.90.0.1:8000/v1/route"
    with pytest.raises(SettingsError):
        from_mapping({"WORKER_LINK": "wireguard", "TANK_URL": "https://api.openai.com/v1"})
    with pytest.raises(SettingsError):
        from_mapping({"TANK_URL": "http://8.8.8.8:8000"})
    with pytest.raises(SettingsError):
        from_mapping({"TANK_REGION": "za"})


def test_issue_label_names_one_brief() -> None:
    body = "Please run docs/cursor/EXAMPLE.md today."
    payload = {"number": 7, "title": "Fix the line", "body": body, "labels": [{"name": "worker"}]}
    task = issue_from_api(payload)
    assert task is not None
    assert task.brief == "docs/cursor/EXAMPLE.md"
    assert task.branch == "worker/EXAMPLE-7"
    assert issue_from_api({**payload, "labels": [{"name": "bug"}]}) is None
    assert issue_from_api({**payload, "pull_request": {"url": "x"}}) is None
    assert issue_from_api({**payload, "body": "docs/cursor/A.md and docs/cursor/B.md"}) is None
    assert briefs_named("docs/cursor/A.md\ndocs/cursor/A.md") == ["docs/cursor/A.md"]
    assert ".." not in "".join(briefs_named("docs/cursor/../../.env"))


def test_brief_file_list_matches_this_brief() -> None:
    text = (ROOT / "docs/cursor/WORKERS-1-own-build-agents.md").read_text(encoding="utf-8")
    rules = allowed_rules(text)
    assert "workers/" in rules
    assert "docker-compose.workers.yml" in rules
    assert ".env.example" in rules
    assert "docs/workers/README.md" in rules
    assert "tests/" in rules
    assert path_allowed("workers/task/Dockerfile", rules)
    assert path_allowed("tests/test_workers_1.py", rules)
    assert outside_rules(["tank/main.py", "workspace/app/tank/view.tsx"], rules) == [
        "tank/main.py",
        "workspace/app/tank/view.tsx",
    ]
    assert commit_paths(["docs/workers/README.md"], rules) == ["docs/workers/README.md"]
    with pytest.raises(RuntimeError):
        commit_paths(["tank/main.py"], rules)


def test_container_cannot_reach_a_host_outside_the_allow_list() -> None:
    policy = Policy(tank_host="10.90.0.1", tank_port=8000)
    refused = []

    def connect(address: tuple[str, int]) -> str:
        policy.check(address[0], address[1])
        return "connected"

    for host, port in (
        ("evil.example", 443),
        ("api.openai.com", 443),
        ("1.1.1.1", 443),
        ("litellm", 4000),
        ("github.com", 22),
        ("10.90.0.1", 443),
        ("127.0.0.1", 22),
    ):
        with pytest.raises(HostRefused):
            connect((host, port))
        refused.append(host)
    assert connect(("github.com", 443)) == "connected"
    assert connect(("api.github.com", 443)) == "connected"
    assert connect(("pypi.org", 443)) == "connected"
    assert connect(("files.pythonhosted.org", 443)) == "connected"
    assert connect(("registry.npmjs.org", 443)) == "connected"
    assert connect(("10.90.0.1", 8000)) == "connected"
    assert connect(("127.0.0.1", 8765)) == "connected"
    script = nft_script(
        {"github.com": ["140.82.112.3"], "pypi.org": ["151.101.0.223"], "registry.npmjs.org": ["104.16.0.1"]},
        tank_host="10.90.0.1",
        tank_port=8000,
        dns_servers=["10.0.2.3"],
    )
    assert "policy drop" in script
    assert "140.82.112.3" in script
    assert "1.1.1.1" not in script
    assert "0.0.0.0/0" not in script
    with pytest.raises(Exception):
        nft_script({}, tank_host="10.90.0.1", tank_port=8000, dns_servers=["10.0.2.3"])
    with pytest.raises(Exception):
        apply("table inet tervory_worker {}\n", ["false"])
    assert refused


def test_token_cannot_push_to_main_or_merge() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    for branch in ("main", "MAIN", "refs/heads/main", "master", "refs/heads/master"):
        with pytest.raises(MainPushRefused):
            push_command(branch)
        runner(["git", "push", "origin", branch])  # would be the unsafe call; the guard never returns it
    assert all("main" not in " ".join(push_command("worker/EXAMPLE-7")) for _ in range(1))
    pushed = push_command("worker/EXAMPLE-7")
    assert "HEAD:refs/heads/worker/EXAMPLE-7" in pushed
    assert "https://github.com/Tervory-AI/tervory-tank.git" in " ".join(
        clone_command("Tervory-AI/tervory-tank", "/work/repo")
    )
    assert "@" not in clone_command("Tervory-AI/tervory-tank", "/work/repo")[-2]
    with pytest.raises(MergeRefused):
        merge_pull_request(1)
    assert "administration" not in APP_PERMISSIONS
    assert set(APP_PERMISSIONS) == {"contents", "pull_requests", "issues"}
    body = installation_token_body("Tervory-AI/tervory-tank")
    assert body["permissions"] == APP_PERMISSIONS
    assert TOKEN_MAX_S <= 3600
    claims = jwt_claims("12345", now=1_700_000_000)
    assert int(claims["exp"]) - int(claims["iat"]) == JWT_TTL_S + 60
    assert int(claims["exp"]) - int(claims["iat"]) <= 600
    with pytest.raises(TokenRejected):
        assert_installation_token("ghp_exampletoken")
    with pytest.raises(TokenRejected):
        assert_installation_token("github_pat_example")
    assert_installation_token(TOKEN)
    with pytest.raises(PermissionError):
        credential_fill("protocol=https\nhost=gitlab.com\n", TOKEN)
    filled = credential_fill("protocol=https\nhost=github.com\n", TOKEN)
    assert "username=x-access-token" in filled
    assert calls  # the unsafe runner was not used by the guard


def test_app_jwt_is_short_lived_and_signed() -> None:
    pem = _key_pem()
    token = sign_app_jwt("12345", pem, now=1_700_000_000)
    header, payload, signature = token.split(".")
    assert header and payload and signature
    key = serialization.load_pem_private_key(pem, password=None)
    import base64

    def pad(part: str) -> bytes:
        return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))

    public = key.public_key()
    public.verify(pad(signature), f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    claims = json.loads(pad(payload))
    assert claims["iss"] == "12345"
    assert claims["exp"] - claims["iat"] <= 600


def test_fresh_podman_container_is_sealed() -> None:
    settings = _settings()
    argv = task_argv(
        settings,
        name="tervory-worker-7-abcd1234",
        runtime="runc",
        secret_dir="/var/lib/workers/tervory-worker-7-abcd1234",
        brief="docs/cursor/EXAMPLE.md",
        issue=7,
        branch="worker/EXAMPLE-7",
        title="Fix the line",
        hosts=[("tank", "10.0.1.8")],
    )
    assert argv[0] == "podman"
    assert "--rm" in argv
    assert "--privileged" not in argv
    assert "host" != argv[argv.index("--network") + 1]
    assert "docker.sock" not in " ".join(argv)
    assert "--cpus" in argv and argv[argv.index("--cpus") + 1] == "2"
    assert argv[argv.index("--memory") + 1] == "4g"
    assert "--read-only" in argv
    assert "tervory-worker-task:1" in argv
    assert "--add-host" in argv and "tank:10.0.1.8" in argv
    blob = " ".join(argv)
    assert "ghs_" not in blob
    assert "BEGIN PRIVATE KEY" not in blob
    assert choose_runtime({"host": {"ociRuntimes": {"runsc": {}, "crun": {}}}}) == "runsc"
    assert choose_runtime({"host": {"ociRuntime": {"name": "crun"}}}) == "crun"
    assert kill_argv("tervory-worker-7-abcd1234") == ["podman", "kill", "tervory-worker-7-abcd1234"]
    text = (ROOT / "workers/task/Dockerfile").read_text(encoding="utf-8")
    assert "node:22-bookworm-slim" in text
    assert "playwright==1.64.1" in (ROOT / "workers/task/requirements.txt").read_text(encoding="utf-8")
    assert "aider-chat==0.86.2" in (ROOT / "workers/task/requirements.txt").read_text(encoding="utf-8")
    assert "playwright install --with-deps chromium" in text
    entry = (ROOT / "workers/task/entrypoint.sh").read_text(encoding="utf-8")
    assert "workers.egress_apply" in entry
    assert "setpriv" in entry
    assert "--inh-caps=-all" in entry
    service_entry = (ROOT / "workers/entrypoint.sh").read_text(encoding="utf-8")
    assert "setpriv --reuid=worker" in service_entry
    for path in ROOT.joinpath("workers").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    raise AssertionError(f"{path} runs a shell")


def test_aider_and_model_calls_go_only_to_tank() -> None:
    argv = aider_argv("/tmp/worker-message.txt", ["docs/workers/README.md"], proxy_port=8765)
    blob = " ".join(argv)
    assert "http://127.0.0.1:8765/v1" in blob
    assert "--openai-api-key" not in argv
    for banned in ("api.openai.com", "anthropic.com", "openrouter.ai"):
        assert banned not in blob
    settings = _settings()
    seen: list[tuple[str, dict[str, object]]] = []

    async def send(url: str, payload: dict[str, object], key: str) -> dict[str, object]:
        seen.append((url, payload))
        assert key == "tank-key-example"
        return {
            "content": "done",
            "cost_usd": 0.125,
            "ledger_id": "11111111-1111-1111-1111-111111111111",
            "tokens_in": 3,
            "tokens_out": 4,
        }

    result = asyncio.run(
        forward_chat(
            {"messages": [{"role": "user", "content": "edit the line"}]},
            settings,
            issue=7,
            key="tank-key-example",
            send=send,
        )
    )
    assert seen[0][0] == "http://tank:8000/v1/route"
    assert seen[0][1]["tenant_id"] == PLATFORM_TENANT
    assert seen[0][1]["agent"] == "workers"
    assert seen[0][1]["skill"] == "worker.7"
    assert result["choices"][0]["message"]["content"] == "done"
    assert assert_tank_destination(settings).endswith("/v1/route")
    body = route_body(settings, normalize_messages([{"role": "user", "content": "hi"}]), issue=7, max_tokens=None)
    assert body["tenant_id"] == PLATFORM_TENANT


def test_draft_then_ready_only_when_ci_is_green() -> None:
    assert ci_state([], "pending") == "pending"
    assert ci_state([{"status": "completed", "conclusion": "failure"}], "failure") == "red"
    state, body = finish_from_ci(
        check_runs=[{"status": "completed", "conclusion": "success"}],
        combined="success",
        summary="Changed one line.",
    )
    assert state == "green"
    assert body is not None and body.startswith("ready for review\n")
    pending, nothing = finish_from_ci(check_runs=[{"status": "in_progress", "conclusion": None}], combined="pending", summary="x")
    assert pending == "pending" and nothing is None
    issue = WorkerIssue(7, "Fix the line", "docs/cursor/EXAMPLE.md", "docs/cursor/EXAMPLE.md")
    assert "draft" in draft_body(issue).lower()
    assert ready_body("Ship the line.").startswith("ready for review\n")


def test_secrets_are_redacted_and_not_in_the_result(tmp_path: Path) -> None:
    assert redact(f"Authorization: Bearer {TOKEN}") == "Authorization: Bearer [redacted]"
    header = "-----BEGIN " + "PRIVATE KEY-----"
    footer = "-----END " + "PRIVATE KEY-----"
    assert "BEGIN" not in redact(header + "\nabc\n" + footer)
    outcome = parse_result(
        'noise\nWORKER_RESULT {"status":"draft","pr_url":"https://github.com/Tervory-AI/tervory-tank/pull/4",'
        '"pr_number":4,"minutes":1.5,"cost_usd":0.02,"ledger_ids":["abc"],"sha":"abcdef1234567890"}\n'
    )
    assert outcome is not None
    assert outcome.status == "draft"
    assert TOKEN not in outcome.line()
    directory = tmp_path / "workers-secret-test"
    if directory.exists():
        for child in directory.iterdir():
            child.unlink()
    else:
        directory.mkdir()
    try:
        stage(directory, token=TOKEN, tank_key="tank-key-example")
        assert (directory / "token").read_text(encoding="utf-8") == TOKEN
        assert oct((directory / "token").stat().st_mode & 0o777) == oct(0o444)
        assert oct(directory.stat().st_mode & 0o777) == oct(0o711)
    finally:
        for child in directory.iterdir():
            child.unlink()
        directory.rmdir()


def test_host_env_template_names_the_settings() -> None:
    # The Docker workers app is retired; the host env file (workers/host/) carries the names.
    assert not (ROOT / "docker-compose.workers.yml").exists()
    template = (ROOT / "workers/host/worker.env.example").read_text(encoding="utf-8")
    for name in (
        "WORKER_MAX_TASKS",
        "WORKER_TASK_CPUS",
        "WORKER_TASK_MEMORY",
        "TANK_KEY_WORKERS",
        "GITHUB_APP_ID",
        "GITHUB_APP_PRIVATE_KEY_FILE",
        "TANK_URL",
    ):
        assert re.search(rf"^{name}=", template, re.M)
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "TANK_KEY_WORKERS" in env_example
    assert "BEGIN PRIVATE KEY" not in template
    assert "BEGIN PRIVATE KEY" not in (ROOT / "docs/workers/README.md").read_text(encoding="utf-8")


class _Open:
    """The founder's workers pause, switched off."""

    async def paused(self) -> bool:
        return False


class _Launcher:
    def __init__(self, outcome_status: str = "draft") -> None:
        self.calls = 0
        self.outcome_status = outcome_status
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    async def run(self, settings: Settings, task: WorkerIssue, token: str) -> object:
        from workers.task_run import Outcome

        self.calls += 1
        self.started.set()
        await self.release.wait()
        return Outcome(
            status=self.outcome_status,
            pr_url="https://github.com/Tervory-AI/tervory-tank/pull/4",
            pr_number=4,
            node_id="PR_NODE",
            sha=SHA,
            minutes=2.5,
            cost_usd=0.02,
            ledger_ids=["11111111-1111-1111-1111-111111111111"],
        )


def _client(handler) -> GitHub:
    transport = httpx.MockTransport(handler)
    return GitHub("Tervory-AI/tervory-tank", httpx.AsyncClient(transport=transport))


@pytest.mark.asyncio
async def test_worker_label_opens_a_draft_and_marks_ready(tmp_path: Path) -> None:
    seen: list[tuple[str, str, bytes]] = []
    pem = _key_pem()
    key_file = tmp_path / "app.pem"
    key_file.write_bytes(pem)

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        seen.append((request.method, str(request.url), body))
        url = str(request.url)
        if url.endswith("/access_tokens"):
            sent = json.loads(body)
            assert sent["permissions"] == APP_PERMISSIONS
            assert "administration" not in sent["permissions"]
            return httpx.Response(201, json={"token": TOKEN, "permissions": APP_PERMISSIONS})
        if "/issues?" in url and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 7,
                        "title": "Fix the line",
                        "body": "Run docs/cursor/EXAMPLE.md",
                        "labels": [{"name": "worker"}],
                    }
                ],
            )
        if "/pulls?" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        if url.endswith("/comments") and request.method == "POST":
            return httpx.Response(201, json={"id": 1})
        if url.endswith("/check-runs?per_page=100"):
            return httpx.Response(200, json={"check_runs": [{"name": "ci", "status": "completed", "conclusion": "success"}]})
        if url.endswith("/status"):
            return httpx.Response(200, json={"state": "success"})
        if url.endswith("/graphql"):
            query = json.loads(body)["query"]
            assert "mergePullRequest" not in query
            assert "markPullRequestReadyForReview" in query
            return httpx.Response(200, json={"data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}})
        if request.method == "PATCH" and "/pulls/4" in url:
            patched = json.loads(body)
            assert patched["body"].startswith("ready for review\n")
            return httpx.Response(200, json={"number": 4, "draft": False})
        return httpx.Response(404, json={"error": url})

    github = _client(handler)
    launcher = _Launcher()
    settings = _settings(private_key_file=str(key_file), state_dir=str(tmp_path))
    service = Service(settings, github, launcher, _Open())  # type: ignore[arg-type]
    service.pause_s = 0
    await service.poll_once(TOKEN)
    await asyncio.gather(*service.jobs)
    assert launcher.calls == 1
    assert service.records[0]["status"] == "ready"
    assert service.records[0]["pr_url"].endswith("/pull/4")
    assert service.records[0]["minutes"] == 2.5
    assert service.records[0]["cost_usd"] == 0.02
    comments = [json.loads(body)["body"] for method, url, body in seen if method == "POST" and url.endswith("/comments")]
    assert any(item.startswith("Worker draft:") for item in comments)
    assert any(item.startswith("Worker ready:") for item in comments)
    assert all(TOKEN not in item for item in comments)
    page = render(service.records)
    assert "Workers" in page
    assert "Fix" not in page or "EXAMPLE.md" in page
    assert "https://github.com/Tervory-AI/tervory-tank/pull/4" in page
    await github.client.aclose()


@pytest.mark.asyncio
async def test_ci_failure_stays_a_draft(tmp_path: Path) -> None:
    pem = _key_pem()
    key_file = tmp_path / "app.pem"
    key_file.write_bytes(pem)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": TOKEN, "permissions": APP_PERMISSIONS})
        if "/issues?" in url:
            return httpx.Response(
                200,
                json=[{"number": 7, "title": "Fix", "body": "docs/cursor/EXAMPLE.md", "labels": [{"name": "worker"}]}],
            )
        if "/pulls?" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        if url.endswith("/comments"):
            return httpx.Response(201, json={})
        if "check-runs" in url:
            return httpx.Response(200, json={"check_runs": [{"status": "completed", "conclusion": "failure"}]})
        if url.endswith("/status"):
            return httpx.Response(200, json={"state": "failure"})
        if url.endswith("/graphql") or request.method == "PATCH":
            raise AssertionError("a red check must not mark the pull request ready")
        return httpx.Response(404)

    github = _client(handler)
    service = Service(_settings(private_key_file=str(key_file)), github, _Launcher(), _Open())  # type: ignore[arg-type]
    service.pause_s = 0
    await service.poll_once(TOKEN)
    await asyncio.gather(*service.jobs)
    assert service.records[0]["status"] == "ci_failed"
    await github.client.aclose()


@pytest.mark.asyncio
async def test_one_task_at_a_time_and_bad_issue_gets_one_comment(tmp_path: Path) -> None:
    comments: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/issues?" in url and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {"number": 3, "title": "A", "body": "no brief here", "labels": [{"name": "worker"}]},
                    {"number": 7, "title": "B", "body": "docs/cursor/EXAMPLE.md", "labels": [{"name": "worker"}]},
                    {"number": 8, "title": "C", "body": "docs/cursor/OTHER.md", "labels": [{"name": "worker"}]},
                ],
            )
        if url.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": TOKEN, "permissions": APP_PERMISSIONS})
        if "/pulls?" in url:
            return httpx.Response(200, json=[])
        if url.endswith("/comments"):
            comments.append(int(url.rstrip("/").split("/")[-2]))
            return httpx.Response(201, json={})
        return httpx.Response(404)

    key_file = tmp_path / "workers-app-test.pem"
    key_file.write_bytes(_key_pem())
    github = _client(handler)
    launcher = _Launcher()
    launcher.release.clear()
    service = Service(_settings(private_key_file=str(key_file)), github, launcher, _Open())  # type: ignore[arg-type]
    await service.poll_once(TOKEN)
    await launcher.started.wait()
    await service.poll_once(TOKEN)
    assert launcher.calls == 1
    assert comments.count(3) == 1
    launcher.release.set()
    await asyncio.gather(*service.jobs)
    await github.client.aclose()


@pytest.mark.asyncio
async def test_existing_green_draft_is_marked_ready_without_a_new_container() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/issues?" in url:
            return httpx.Response(
                200,
                json=[{"number": 7, "title": "Fix", "body": "docs/cursor/EXAMPLE.md", "labels": [{"name": "worker"}]}],
            )
        if "/pulls?" in url and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 4,
                        "draft": True,
                        "node_id": "PR_NODE",
                        "html_url": "https://github.com/Tervory-AI/tervory-tank/pull/4",
                        "head": {"sha": SHA},
                    }
                ],
            )
        if "check-runs" in url:
            return httpx.Response(200, json={"check_runs": [{"status": "completed", "conclusion": "success"}]})
        if url.endswith("/status"):
            return httpx.Response(200, json={"state": "success"})
        if url.endswith("/graphql"):
            return httpx.Response(200, json={"data": {}})
        if request.method == "PATCH":
            assert json.loads(request.read())["body"].startswith("ready for review\n")
            return httpx.Response(200, json={})
        if url.endswith("/comments"):
            return httpx.Response(201, json={})
        return httpx.Response(404)

    github = _client(handler)
    launcher = _Launcher()
    service = Service(_settings(), github, launcher, _Open())  # type: ignore[arg-type]
    await service.poll_once(TOKEN)
    assert launcher.calls == 0
    assert service.records[0]["status"] == "ready"
    await github.client.aclose()


def test_changed_paths_and_panel_escapes() -> None:
    assert changed_paths("docs/workers/README.md\n", "workers/task/Dockerfile\n") == [
        "docs/workers/README.md",
        "workers/task/Dockerfile",
    ]
    page = render([{"issue": 1, "brief": "<script>", "status": "draft", "pr_url": "https://example.com", "minutes": 1, "cost_usd": 0}])
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


@pytest.mark.asyncio
async def test_merge_url_is_refused() -> None:
    github = _client(lambda request: httpx.Response(200, json={}))
    with pytest.raises(GitHubError):
        await github._send("POST", "https://api.github.com/repos/Tervory-AI/tervory-tank/pulls/1/merge", TOKEN)
    with pytest.raises(GitHubError):
        await github._send("GET", "https://evil.example/repos", TOKEN)
    await github.client.aclose()


def _long_token() -> str:
    # Shape of a real installation token today: ghs_ prefix, about 390 characters, with - and .
    body = ("AbC1_-x." * 60)[:386]
    token = "ghs_" + body
    assert len(token) == 390 and "-" in token and "." in token
    return token


def test_installation_token_accepts_current_github_shape():
    from workers.github_app import assert_token_response

    token = _long_token()
    assert_installation_token(token)
    body = {"token": token, "permissions": {**APP_PERMISSIONS, "metadata": "read"}}
    assert assert_token_response(body) == token


def test_installation_token_shape_still_refused():
    for bad in (_long_token() + "\n", "ghs_abc\ndef", "ghs_abcd\r", "ghs_" + "a" * 1001, "ghs_ab", "gho_" + "a" * 40, "ghs_abc def"):
        with pytest.raises(TokenRejected):
            assert_installation_token(bad)


def test_token_response_permissions():
    from workers.github_app import assert_token_response

    token = _long_token()
    for permissions in (
        {**APP_PERMISSIONS, "metadata": "write"},
        {**APP_PERMISSIONS, "metadata": "read", "administration": "read"},
        {**APP_PERMISSIONS, "administration": "write"},
        {**APP_PERMISSIONS, "workflows": "write"},
        {**APP_PERMISSIONS, "metadata": "read", "secrets": "read"},
    ):
        with pytest.raises(TokenRejected):
            assert_token_response({"token": token, "permissions": permissions})
    assert assert_token_response({"token": token, "permissions": dict(APP_PERMISSIONS)}) == token


def _mint(tmp_path: Path, response_body: dict) -> str:
    key_file = tmp_path / "app-key.pem"
    key_file.write_bytes(_key_pem())
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url}")
        return httpx.Response(201, json=response_body)

    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await GitHub("Tervory-AI/tervory-tank", client).mint_installation_token(
                app_id="5378545", installation_id="12345678", key_file=str(key_file)
            )

    try:
        return asyncio.run(run())
    finally:
        assert seen == ["POST https://api.github.com/app/installations/12345678/access_tokens"]


def test_mint_installation_token_accepts_metadata_read(tmp_path: Path):
    token = _long_token()
    body = {"token": token, "expires_at": "2026-10-21T12:00:00Z", "permissions": {**APP_PERMISSIONS, "metadata": "read"}}
    assert _mint(tmp_path, body) == token


def test_mint_installation_token_refuses_extra_permissions(tmp_path: Path):
    token = _long_token()
    for permissions in (
        {**APP_PERMISSIONS, "metadata": "read", "administration": "write"},
        {**APP_PERMISSIONS, "administration": "read"},
        {**APP_PERMISSIONS, "metadata": "write"},
        {**APP_PERMISSIONS, "workflows": "write"},
    ):
        with pytest.raises(TokenRejected):
            _mint(tmp_path, {"token": token, "permissions": permissions})
    with pytest.raises(TokenRejected):
        _mint(tmp_path, {"token": token + "\n", "permissions": dict(APP_PERMISSIONS)})


def test_redact_hides_the_whole_current_token():
    token = _long_token()
    cleaned = redact(f"token={token} done")
    assert "ghs_" not in cleaned and token[10:40] not in cleaned and cleaned.endswith(" done")
