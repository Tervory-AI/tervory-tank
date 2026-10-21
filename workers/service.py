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
from workers.issues import FAILED_LABEL, WorkerIssue
from workers.podman_run import build_argv, choose_runtime, container_name, kill_argv, task_argv
from workers.redact import install as install_redact
from workers.redact import redact
from workers.secrets_io import stage
from workers.settings import Settings, SettingsError, from_env
from workers.tank_status import HEARTBEAT_S, LastError, TankControl
from workers.task_run import Outcome, parse_result, summary_for

log = logging.getLogger("workers")
# A task that fails this many times in a row stops retrying and is marked failed.
MAX_FAILURES = 3
MAX_ERROR = 1500
MALFORMED = (
    "This issue needs exactly one brief file under docs/cursor/, "
    "for example docs/cursor/EXAMPLE.md. Nothing was started."
)


class TaskFailed(RuntimeError):
    """The task container failed. detail holds the redacted tail of its stderr and stdout."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


def failure_text(exc: BaseException) -> str:
    """One redacted error for the log, the panel and the issue comment."""
    text = str(exc)
    detail = getattr(exc, "detail", "")
    if detail:
        text = f"{text}\n{detail}"
    return redact(text)[-MAX_ERROR:]


def stopped_comment(failures: int, error: str) -> str:
    fence = "~~~~"
    return (
        f"Worker stopped: this task failed {failures} times in a row, so it will not be retried.\n"
        f"Last error:\n{fence}\n{error.replace(fence, '~~~')}\n{fence}\n"
        f"Fix the cause, then remove the `{FAILED_LABEL}` label to let a worker try again."
    )


def update_pending(settings: Settings) -> bool:
    """workers/updater.py leaves UPDATE_PENDING next to the code while it waits for a task."""
    return (Path(settings.code_dir).parent / "UPDATE_PENDING").exists()


class Service:
    def __init__(self, settings: Settings, github: GitHub, launcher: "Launcher", control: TankControl | None = None) -> None:
        self.settings = settings
        self.control = control
        self.github = github
        self.launcher = launcher
        self.records: list[dict[str, Any]] = []
        self.inflight: set[int] = set()
        self.commented: set[int] = set()
        self.done: set[int] = set()
        # Consecutive failures per issue. Reset on any run that produces a result.
        self.failures: dict[int, int] = {}
        # Stopped in this process when GitHub would not take the failed label.
        self.stopped: set[int] = set()
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
            if task.number in self.inflight or task.number in self.stopped:
                continue
            if running >= self.settings.max_tasks:
                return
            # An auto-update is waiting for the running task: take nothing new until it is applied.
            if update_pending(self.settings):
                return
            # The founder's workers pause is read before taking any task. It fails closed.
            if self.control is None or await self.control.paused():
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
            if outcome.status == "failed" and not outcome.pr_url:
                raise TaskFailed("the task reported a failure", outcome.detail)
            self.failures.pop(task.number, None)
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
            error = failure_text(exc)
            log.warning("task %s failed: %s", task.number, redact(str(exc)))
            await self._failed(task, error, token)
        finally:
            self.inflight.discard(task.number)

    async def _failed(self, task: WorkerIssue, error: str, token: str) -> None:
        failures = self.failures.get(task.number, 0) + 1
        self.failures[task.number] = failures
        if failures < MAX_FAILURES:
            self._record(
                issue=task.number, brief=task.brief, status="failed", pr_url=None, minutes=None, cost_usd=None,
                failures=failures, error=error,
            )
            return
        # Stop retrying. The label keeps it stopped across restarts; the comment records the error.
        self.stopped.add(task.number)
        self._record(
            issue=task.number, brief=task.brief, status="stopped", pr_url=None, minutes=None, cost_usd=None,
            failures=failures, error=error,
        )
        log.warning("task %s stopped after %s failures in a row; not retrying", task.number, failures)
        try:
            token = token or await self._token()
            await self.github.comment(token, task.number, stopped_comment(failures, error))
            await self.github.add_label(token, task.number, FAILED_LABEL)
        except (GitHubError, TokenRejected, OSError, RuntimeError) as exc:
            # Still stopped in this process; it will be retried only after a restart.
            log.warning("task %s: could not mark the issue failed: %s", task.number, redact(str(exc)))
            return
        self.stopped.discard(task.number)
        self.failures.pop(task.number, None)

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
            code, build_out, build_err = split(await self.runner(build_argv(settings.code_dir), timeout_s=60 * 60))
            build_out = joined(build_out, build_err)
            if code != 0:
                log.warning("task image build failed (exit %s). Last podman lines:\n%s", code, podman_tail(build_out))
                raise RuntimeError("task image build failed")
            self._built = True
        info_code, info_out, info_err = split(await self.runner(["podman", "info", "--format", "json"], timeout_s=60))
        if info_code != 0:
            log.warning("podman info failed (exit %s). Last podman lines:\n%s", info_code, podman_tail(joined(info_out, info_err)))
            raise RuntimeError("podman info failed")
        try:
            runtime = choose_runtime(json.loads(info_out))
        except json.JSONDecodeError:
            raise RuntimeError("podman info was not JSON") from None
        key = Path(os.environ["TANK_KEY_FILE"]).read_text(encoding="utf-8").strip() if os.environ.get("TANK_KEY_FILE") else os.environ.get("TANK_KEY_WORKERS", "").strip()
        if not key:
            raise RuntimeError("TANK_KEY_WORKERS is not set")
        name = container_name(task.number)
        secret_dir = Path(settings.state_dir) / name
        try:
            # Inside the try: a partly written secret dir is removed even when staging fails.
            stage(secret_dir, token=token, tank_key=key)
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
            code, output, errors = split(await self.runner(argv, timeout_s=settings.task_timeout_s, kill=kill_argv(name)))
        finally:
            shutil.rmtree(secret_dir, ignore_errors=True)
        outcome = parse_result(output)
        if outcome is None:
            # Never let the task's own secrets reach the log or the issue, even if it echoed them.
            err_tail = podman_tail(scrub(errors, key, token))
            out_tail = podman_tail(scrub(output, key, token))
            log.warning(
                "task container exit %s. Last stderr lines:\n%s\nLast stdout lines:\n%s", code, err_tail, out_tail
            )
            detail = f"exit {code}. stderr: {err_tail}" + (f"\nstdout: {out_tail}" if out_tail != "(no output)" else "")
            raise TaskFailed("the container ended without a result" if code == 0 else "the container failed", detail)
        outcome.runtime = outcome.runtime or runtime
        return outcome


def split(result: tuple[Any, ...]) -> tuple[int, str, str]:
    """(code, stdout, stderr) from a runner. Older runners return (code, output)."""
    if len(result) == 3:
        return int(result[0]), str(result[1] or ""), str(result[2] or "")
    return int(result[0]), str(result[1] or ""), ""


def joined(stdout: str, stderr: str) -> str:
    return "\n".join(part for part in (stdout.rstrip(), stderr.rstrip()) if part)


def scrub(text: str, *secrets_: str) -> str:
    for value in secrets_:
        if value and len(value) >= 8:
            text = text.replace(value, "[redacted]")
    return text


def podman_tail(output: str | None, lines: int = 20) -> str:
    """The last lines of podman's output, redacted, for the log."""
    tail = (output or "").rstrip().splitlines()[-lines:]
    return redact("\n".join(tail)) or "(no output)"


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
    ) -> tuple[int, str, str]:
        """Returns (exit code, stdout, stderr). stdout carries WORKER_RESULT; stderr is kept for failures."""
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            raw, err = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            if kill:
                killer = await asyncio.create_subprocess_exec(*kill, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await killer.wait()
            process.kill()
            await process.communicate()
            raise RuntimeError("task timed out") from None
        return (
            process.returncode or 0,
            raw.decode("utf-8", errors="replace"),
            (err or b"").decode("utf-8", errors="replace"),
        )


async def serve(settings: Settings) -> None:
    install_redact()
    records: list[dict[str, Any]] = []
    state: dict[str, Any] = {"busy": False, "issue": None}
    last_error = LastError()
    log.addHandler(last_error)

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
            body = (json.dumps({"ok": True, "busy": bool(state["busy"])}) + "\n").encode()
            status, kind = "200 OK", "application/json"
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

    # Loopback only. On the Boston host nothing else should reach the status page.
    server = await asyncio.start_server(handle, "127.0.0.1", settings.service_port)
    log.info("workers listening on 127.0.0.1:%s", settings.service_port)
    async with httpx.AsyncClient(timeout=60) as client:
        control = TankControl(settings, client)
        inflight: set[int] = set()

        async def beat() -> None:
            while True:
                await control.paused()
                await control.heartbeat(issue=min(inflight) if inflight else None, last_error=last_error.line)
                await asyncio.sleep(HEARTBEAT_S)

        asyncio.create_task(beat())
        if not settings.github_ready or not Path(settings.private_key_file).is_file():
            log.warning("GitHub App is not configured; not taking tasks")
            async with server:
                await server.serve_forever()
            return
        github = GitHub(settings.repo, client)
        service = Service(settings, github, Launcher(Runner()), control)
        records_ref = service.records
        inflight = service.inflight

        async def refresh_view() -> None:
            while True:
                records[:] = list(records_ref)
                state["busy"] = bool(service.inflight)
                state["issue"] = min(service.inflight) if service.inflight else None
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
