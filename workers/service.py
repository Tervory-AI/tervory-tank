"""Poll issues labelled worker and run each one in a fresh podman container."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import shutil
import socket
from pathlib import Path
from typing import Any

import httpx

from workers import status_page
from workers.github_api import GitHub, GitHubError, ci_state, ready_body
from workers.github_app import TokenRejected
from workers.issues import WorkerIssue
from workers.podman_run import build_argv, choose_runtime, container_name, kill_argv, task_argv
from workers.redact import install as install_redact
from workers.redact import redact
from workers.secrets_io import stage
from workers.settings import Settings, SettingsError, from_env
from workers.task_run import Outcome, parse_result, summary_for

log = logging.getLogger("workers")
MALFORMED = (
    "This issue needs exactly one brief file under docs/cursor/, "
    "for example docs/cursor/EXAMPLE.md. Nothing was started."
)


class Service:
    def __init__(self, settings: Settings, github: GitHub, launcher: "Launcher") -> None:
        self.settings = settings
        self.github = github
        self.launcher = launcher
        self.records: list[dict[str, Any]] = []
        self.inflight: set[int] = set()
        self.commented: set[int] = set()
        self.done: set[int] = set()
        self.jobs: list[asyncio.Task[None]] = []
        self.pause_s = 15

    def _record(self, **fields: Any) -> None:
        issue = fields.get("issue")
        kept = [row for row in self.records if row.get("issue") != issue]
        self.records[:] = kept
        self.records.insert(0, fields)

    async def poll_once(self, token: str) -> None:
        payloads = await self.github.list_issues(token)
        for number in self.github.malformed(payloads):
            if number in self.commented:
                continue
            await self.github.comment(token, number, MALFORMED)
            self.commented.add(number)
        running = len(self.inflight)
        for task in self.github.tasks(payloads):
            pulls = await self.github.open_pulls(token, task.branch)
            if pulls:
                await self._finish_existing(token, task, pulls[0])
                continue
            if task.number in self.inflight:
                continue
            if running >= self.settings.max_tasks:
                return
            running += 1
            self.inflight.add(task.number)
            self.jobs.append(asyncio.create_task(self._run(task)))

    async def _finish_existing(self, token: str, task: WorkerIssue, pull: dict[str, Any]) -> None:
        if task.number in self.done:
            return
        if pull.get("draft") is not True:
            self._record(
                issue=task.number,
                brief=task.brief,
                status="ready",
                pr_url=pull.get("html_url"),
                minutes=None,
                cost_usd=None,
            )
            self.done.add(task.number)
            return
        sha = str(pull.get("head", {}).get("sha") or "") if isinstance(pull.get("head"), dict) else ""
        if not sha:
            return
        state = ci_state(await self.github.check_runs(token, sha), await self.github.combined_status(token, sha))
        self._record(
            issue=task.number,
            brief=task.brief,
            status="draft" if state != "green" else "ready",
            pr_url=pull.get("html_url"),
            minutes=None,
            cost_usd=None,
        )
        if state != "green":
            return
        number = int(pull["number"])
        body = ready_body(f"Issue #{task.number} ({task.brief}) passed CI and is ready for review.")
        await self.github.mark_ready(token, node_id=str(pull.get("node_id") or ""), body=body, number=number)
        self.done.add(task.number)
        await self.github.comment(token, task.number, f"Worker ready: {pull.get('html_url')}")

    async def _run(self, task: WorkerIssue) -> None:
        token = ""
        try:
            token = await self._token()
            outcome = await self.launcher.run(self.settings, task, token)
            self._record(
                issue=task.number,
                brief=task.brief,
                status=outcome.status,
                pr_url=outcome.pr_url,
                minutes=outcome.minutes,
                cost_usd=outcome.cost_usd,
            )
            if outcome.pr_url:
                await self.github.comment(
                    token,
                    task.number,
                    (
                        f"Worker draft: {outcome.pr_url}\n"
                        f"Minutes: {outcome.minutes:.1f}\n"
                        f"Model cost: ${outcome.cost_usd:.6f}"
                    ),
                )
            if outcome.status == "draft" and outcome.sha and outcome.node_id and outcome.pr_number:
                await self._wait_ci(task, outcome)
        except (GitHubError, TokenRejected, OSError, RuntimeError) as exc:
            log.warning("task %s failed: %s", task.number, redact(str(exc)))
            self._record(issue=task.number, brief=task.brief, status="failed", pr_url=None, minutes=None, cost_usd=None)
        finally:
            self.inflight.discard(task.number)

    async def _wait_ci(self, task: WorkerIssue, outcome: Outcome) -> None:
        assert outcome.sha and outcome.node_id and outcome.pr_number
        deadline = asyncio.get_running_loop().time() + 30 * 60
        while asyncio.get_running_loop().time() < deadline:
            token = await self._token()
            state = ci_state(
                await self.github.check_runs(token, outcome.sha),
                await self.github.combined_status(token, outcome.sha),
            )
            if state == "pending":
                await asyncio.sleep(self.pause_s)
                continue
            if state != "green":
                self._record(
                    issue=task.number,
                    brief=task.brief,
                    status="ci_failed",
                    pr_url=outcome.pr_url,
                    minutes=outcome.minutes,
                    cost_usd=outcome.cost_usd,
                )
                return
            body = ready_body(summary_for(task, [], outcome.minutes, outcome.cost_usd))
            await self.github.mark_ready(token, node_id=outcome.node_id, body=body, number=outcome.pr_number)
            self._record(
                issue=task.number,
                brief=task.brief,
                status="ready",
                pr_url=outcome.pr_url,
                minutes=outcome.minutes,
                cost_usd=outcome.cost_usd,
            )
            await self.github.comment(
                token,
                task.number,
                f"Worker ready: {outcome.pr_url}\nMinutes: {outcome.minutes:.1f}\nModel cost: ${outcome.cost_usd:.6f}",
            )
            return

    async def _token(self) -> str:
        return await self.github.mint_installation_token(
            app_id=self.settings.app_id,
            installation_id=self.settings.installation_id,
            key_file=self.settings.private_key_file,
        )


class Launcher:
    """Builds the task image if needed and runs one sealed container."""

    def __init__(self, runner: "Runner") -> None:
        self.runner = runner
        self._built = False

    async def run(self, settings: Settings, task: WorkerIssue, token: str) -> Outcome:
        if not self._built:
            code, _ = await self.runner(build_argv(), timeout_s=60 * 60)
            if code != 0:
                raise RuntimeError("task image build failed")
            self._built = True
        info_code, info_out = await self.runner(["podman", "info", "--format", "json"], timeout_s=60)
        runtime = "runc"
        if info_code == 0:
            try:
                runtime = choose_runtime(json.loads(info_out))
            except json.JSONDecodeError:
                runtime = "runc"
        key = Path(os.environ["TANK_KEY_FILE"]).read_text(encoding="utf-8").strip() if os.environ.get("TANK_KEY_FILE") else os.environ.get("TANK_KEY_WORKERS", "").strip()
        if not key:
            raise RuntimeError("TANK_KEY_WORKERS is not set")
        name = container_name(task.number)
        secret_dir = Path(settings.state_dir) / name
        stage(secret_dir, token=token, tank_key=key)
        try:
            argv = task_argv(
                settings,
                name=name,
                runtime=runtime,
                secret_dir=str(secret_dir),
                brief=task.brief,
                issue=task.number,
                branch=task.branch,
                title=task.title,
                hosts=tank_hosts(settings),
            )
            code, output = await self.runner(argv, timeout_s=settings.task_timeout_s, kill=kill_argv(name))
        finally:
            shutil.rmtree(secret_dir, ignore_errors=True)
        outcome = parse_result(output)
        if outcome is None:
            raise RuntimeError("the container ended without a result" if code == 0 else "the container failed")
        outcome.runtime = outcome.runtime or runtime
        return outcome


def tank_hosts(settings: Settings) -> list[tuple[str, str]]:
    """Give the task container the Tank address the service can already reach."""
    host = settings.tank_host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, settings.tank_port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise RuntimeError("Tank did not resolve on the private link") from exc
        address = infos[0][4][0]
        ipaddress.ip_address(address)
        return [(host, address)]
    return []


class Runner:
    async def __call__(
        self,
        argv: list[str],
        *,
        timeout_s: int,
        kill: list[str] | None = None,
    ) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            raw, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            if kill:
                killer = await asyncio.create_subprocess_exec(*kill, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await killer.wait()
            process.kill()
            await process.communicate()
            raise RuntimeError("task timed out") from None
        return process.returncode or 0, raw.decode("utf-8", errors="replace")


async def serve(settings: Settings) -> None:
    install_redact()
    records: list[dict[str, Any]] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, asyncio.LimitOverrunError):
            writer.close()
            return
        line = request.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
        parts = line.split(" ")
        method, path = (parts[0], parts[1]) if len(parts) >= 2 else ("", "/")
        path = path.split("?", 1)[0]
        if method != "GET":
            body, status, kind = b"Method not allowed\n", "405 Method Not Allowed", "text/plain"
        elif path == "/health":
            body, status, kind = b'{"ok":true}\n', "200 OK", "application/json"
        elif path == "/workers":
            body = status_page.render(records).encode()
            status, kind = "200 OK", "text/html; charset=utf-8"
        elif path == "/workers.json":
            body = json.dumps(records).encode()
            status, kind = "200 OK", "application/json"
        else:
            body, status, kind = b"Not found\n", "404 Not Found", "text/plain"
        header = (
            f"HTTP/1.1 {status}\r\nContent-Type: {kind}\r\nContent-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
        ).encode()
        writer.write(header + body)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "0.0.0.0", settings.service_port)
    log.info("workers listening on %s", settings.service_port)
    if not settings.github_ready or not Path(settings.private_key_file).is_file():
        log.info("GitHub App is not configured; not taking tasks")
        async with server:
            await server.serve_forever()
        return
    async with httpx.AsyncClient(timeout=60) as client:
        github = GitHub(settings.repo, client)
        service = Service(settings, github, Launcher(Runner()))
        records_ref = service.records

        async def refresh_view() -> None:
            while True:
                records[:] = list(records_ref)
                await asyncio.sleep(1)

        asyncio.create_task(refresh_view())

        async def loop() -> None:
            while True:
                try:
                    token = await github.mint_installation_token(
                        app_id=settings.app_id,
                        installation_id=settings.installation_id,
                        key_file=settings.private_key_file,
                    )
                    await service.poll_once(token)
                except (GitHubError, TokenRejected, OSError, SettingsError) as exc:
                    log.warning("poll failed: %s", redact(str(exc)))
                await asyncio.sleep(settings.poll_s)

        async with server:
            await loop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    install_redact()
    try:
        settings = from_env()
    except SettingsError as exc:
        raise SystemExit(str(exc)) from None
    asyncio.run(serve(settings))


if __name__ == "__main__":
    main()
