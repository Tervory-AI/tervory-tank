"""Window job poller beside existing workers; no connection to window lifetime."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import replace
from pathlib import Path

import httpx

from workers.podman_run import build_argv, choose_runtime, container_name, kill_argv, task_argv, task_tank_url
from workers.secrets_io import _write
from workers.service import split, tank_hosts
from workers.window_agent.runtime import ContainerRunner
from workers.tank_status import tank_key
from workers.task_run import parse_result

log = logging.getLogger('workers')
IMAGE = 'tervory-window-agent:1'


def argv_for(settings, name, runtime, directory, job):
    argv = task_argv(replace(settings, tenant_id=job['tenant_id'], repo=job['repo']), name=name, runtime=runtime,
                     secret_dir=str(directory), brief='Window task', issue=1,
                     branch='worker/window-' + job['job_id'], title='Window task', hosts=tank_hosts(settings))
    # Reuse the worker's mounts/limits/network. This entry never installs a firewall
    # or escalates: the entire container starts as 1001 with zero capabilities.
    while '--cap-add' in argv:
        index = argv.index('--cap-add')
        del argv[index:index + 2]
    for i, arg in enumerate(argv):
        if arg in ('/work:rw,nosuid,nodev,size=3g', '/home/worker:rw,nosuid,nodev,size=256m'):
            argv[i] = arg + ',uid=1001,gid=1001'
    argv[-1:] = ['--user', '1001:1001', IMAGE]
    # No Tank service credential is staged in this container; only its job lease.
    index = argv.index('TANK_KEY_FILE=/run/secrets/tank_key')
    del argv[index - 1:index + 1]
    return argv


class WindowJobs:
    def __init__(self, settings, control, client, runner=None):
        self.settings, self.control, self.client = settings, control, client
        self.runner = runner or ContainerRunner()
        self.built = False

    async def call(self, path, body=None):
        response = await self.client.post(self.settings.tank_url.rstrip('/') + '/v1/window-agents/' + path,
                                          json=body or {}, headers={'x-tank-key': tank_key()}, timeout=30)
        if response.status_code == 409:
            raise asyncio.CancelledError()
        response.raise_for_status()
        return response.json()

    async def prepare(self):
        if self.built:
            return
        for argv in (build_argv(self.settings.code_dir), ['podman', 'build', '-t', IMAGE, '-f',
                     str(Path(self.settings.code_dir) / 'workers/window_agent/Dockerfile'), self.settings.code_dir]):
            code, _, _ = split(await self.runner(argv, timeout_s=3600))
            if code:
                raise RuntimeError('Window task image did not build')
        self.built = True

    async def run(self, job):
        name = container_name(1)
        directory = Path(self.settings.state_dir) / name
        path = f"worker/{job['tenant_id']}/{job['job_id']}"
        lease = {'lease': job['lease']}
        launched = None
        try:
            directory.mkdir(mode=0o711, parents=True)
            directory.chmod(0o711)
            credential = await self.call(path + '/credential', lease)
            _write(directory / 'token', credential['value'])
            payload = {**job, 'tank_url': task_tank_url(self.settings)}
            _write(directory / 'job.json', json.dumps(payload))
            code, output, _ = split(await self.runner(['podman', 'info', '--format', 'json'], timeout_s=60))
            if code:
                raise RuntimeError('Worker runtime unavailable')
            info = json.loads(output)
            if info.get('host', {}).get('security', {}).get('rootless') is not True:
                raise RuntimeError('Window tasks require the existing rootless worker runtime')
            argv = argv_for(self.settings, name, choose_runtime(info), directory, job)
            launched = asyncio.create_task(self.runner(argv, timeout_s=self.settings.task_timeout_s, kill=kill_argv(name)))
            while not launched.done():
                await self.call(path + '/heartbeat', lease)
                await asyncio.wait({launched}, timeout=2)
            _, output, _ = split(await launched)
            outcome = parse_result(output)
            await self.call(path + '/finish', {**lease, 'status': 'done' if outcome and outcome.pr_number else 'failed',
                                               'pr_number': outcome.pr_number if outcome else None, 'sha': outcome.sha if outcome else None})
        except (OSError, RuntimeError, ValueError, httpx.HTTPError):
            try:
                await self.call(path + '/finish', {**lease, 'status': 'failed'})
            except (httpx.HTTPError, asyncio.CancelledError):
                pass  # Durable heartbeat expiry preserves an uncertain result.
            raise
        finally:
            try:
                if launched and not launched.done():
                    launched.cancel()
                    try:
                        await launched
                    except asyncio.CancelledError:
                        pass
                # Also cover failures before the launch coroutine started.
                await self.runner(kill_argv(name), timeout_s=30)
            finally:
                shutil.rmtree(directory, ignore_errors=True)

    async def serve(self):
        while True:
            try:
                if not await self.control.paused():
                    # Build before claiming so a failed build never strands a job.
                    await self.prepare()
                    job = await self.call('worker/next')
                    if job:
                        try:
                            await self.run(job)
                        except asyncio.CancelledError:
                            # Job cancellation is distinct from service shutdown.
                            if asyncio.current_task().cancelling():
                                raise
                await asyncio.sleep(5)
            except (OSError, RuntimeError, ValueError, httpx.HTTPError):
                log.warning('Window job poll stopped; no task was replayed')
                await asyncio.sleep(5)
