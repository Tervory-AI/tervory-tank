"""WORKERS-3: updater drain races, with no network, containers or real keys."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from workers import service as worker_service
from workers.issues import WorkerIssue
from workers.settings import Settings
from workers.task_run import Outcome


class GitHub:
    def __init__(self, *args):
        self.release_poll = asyncio.Event()
        self.task = WorkerIssue(211, "Example", "docs/cursor/EXAMPLE.md", "docs/cursor/EXAMPLE.md")

    async def mint_installation_token(self, **kwargs):
        return "offline-token"

    async def list_issues(self, token):
        await self.release_poll.wait()
        return []

    def malformed(self, payloads):
        return []

    def tasks(self, payloads):
        return [self.task]

    async def open_pulls(self, token, branch):
        return []


def test_update_requested_during_pause_check_prevents_task_start(tmp_path):
    async def run():
        checking_pause, release_pause = asyncio.Event(), asyncio.Event()

        async def paused():
            checking_pause.set()
            await release_pause.wait()
            return False

        github = GitHub()
        github.release_poll.set()
        control = AsyncMock()
        control.paused.side_effect = paused
        service = worker_service.Service(Settings(code_dir=str(tmp_path / "app")), github, AsyncMock(), control)
        service._run = AsyncMock()
        polling = asyncio.create_task(service.poll_once("offline-token"))
        try:
            await asyncio.wait_for(checking_pause.wait(), timeout=5)
            # The initial update_pending check has passed. The updater writes
            # its drain marker while Tank's pause response is still pending.
            marker = tmp_path / "UPDATE_PENDING"
            marker.write_text("new-commit\n")
            release_pause.set()
            await asyncio.wait_for(polling, timeout=5)
            await asyncio.gather(*service.jobs)
            assert service.inflight == set()
            assert service.jobs == []
            service._run.assert_not_awaited()
            # Clearing the drain marker permits the same task on a later poll.
            marker.unlink()
            await service.poll_once("offline-token")
            await asyncio.gather(*service.jobs)
            service._run.assert_awaited_once_with(github.task)
        finally:
            polling.cancel()
            await asyncio.gather(polling, *service.jobs, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize("configured", [False, True])
def test_health_reads_live_tasks_before_the_next_view_refresh(tmp_path, monkeypatch, configured):
    async def run():
        baseline_tasks = asyncio.all_tasks()
        baseline_handlers = list(worker_service.log.handlers)
        view_refreshed, task_started, finish_task = (asyncio.Event() for _ in range(3))
        github = GitHub()
        control = AsyncMock()
        control.paused.return_value = False

        async def launch(*args):
            task_started.set()
            await finish_task.wait()
            return Outcome(status="ready", minutes=0, cost_usd=0)

        launcher = AsyncMock()
        launcher.run.side_effect = launch

        class Server:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def serve_forever(self):
                view_refreshed.set()
                await asyncio.Event().wait()

        class Writer:
            def write(self, data):
                self.data = data

            async def drain(self):
                pass

            def close(self):
                pass

        sleep = asyncio.sleep

        async def freeze_view(seconds):
            if seconds == 1:
                # Cache an idle view once, then keep the next refresh blocked.
                view_refreshed.set()
                await asyncio.Event().wait()
            else:
                await sleep(seconds)

        listener = AsyncMock(return_value=Server())
        monkeypatch.setattr(worker_service.asyncio, "start_server", listener)
        monkeypatch.setattr(worker_service.asyncio, "sleep", freeze_view)
        monkeypatch.setattr(worker_service, "GitHub", lambda *args: github)
        monkeypatch.setattr(worker_service, "TankControl", lambda *args: control)
        monkeypatch.setattr(worker_service, "Launcher", lambda *args: launcher)
        key = tmp_path / "offline-key"
        key.write_text("not parsed by the offline GitHub fixture")
        settings = Settings(code_dir=str(tmp_path / "app"), app_id="fixture" if configured else "",
                            installation_id="fixture", private_key_file=str(key))
        service = worker_service.Service(settings, github, launcher, control)
        monkeypatch.setattr(worker_service, "Service", lambda *args: service)

        async def health():
            reader, writer = asyncio.StreamReader(), Writer()
            reader.feed_data(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await listener.call_args.args[0](reader, writer)
            header, body = writer.data.split(b"\r\n\r\n", 1)
            assert header.startswith(b"HTTP/1.1 200 OK")
            return json.loads(body)

        serving = asyncio.create_task(worker_service.serve(settings))
        try:
            await asyncio.wait_for(view_refreshed.wait(), timeout=5)
            assert await health() == {"ok": True, "busy": False}
            if configured:
                github.release_poll.set()
                await asyncio.wait_for(task_started.wait(), timeout=5)
                # A task has started since the idle refresh. The updater must
                # see busy immediately, even while that cached view is frozen.
                (tmp_path / "UPDATE_PENDING").write_text("new-commit\n")
                assert await health() == {"ok": True, "busy": True}
                finish_task.set()
                await asyncio.wait_for(asyncio.gather(*service.jobs), timeout=5)
                assert await health() == {"ok": True, "busy": False}
        finally:
            tasks = (asyncio.all_tasks() - baseline_tasks) | {serving}
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for handler in worker_service.log.handlers[:]:
                if handler not in baseline_handlers:
                    worker_service.log.removeHandler(handler)

    asyncio.run(run())
