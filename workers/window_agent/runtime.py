"""Cancellation-safe container runs on the existing worker subprocess runner."""
from __future__ import annotations

import asyncio

from workers.service import Runner


class ContainerRunner(Runner):
    async def __call__(self, argv, *, timeout_s, kill=None):
        if not kill:
            return await super().__call__(argv, timeout_s=timeout_s)
        # Shield startup: cancellation must not lose a just-spawned podman child.
        starting = asyncio.create_task(asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
        process = None
        communication = None
        try:
            process = await asyncio.shield(starting)
            communication = asyncio.create_task(process.communicate())
            raw, err = await asyncio.wait_for(asyncio.shield(communication), timeout_s)
            return process.returncode or 0, raw.decode(errors='replace'), err.decode(errors='replace')
        except TimeoutError:
            raise RuntimeError('Task timed out') from None
        finally:
            if process is None:
                process = await starting
            try:
                # Killing by the worker-generated name also stops descendants.
                await super().__call__(kill, timeout_s=30)
            finally:
                if process.returncode is None:
                    try:
                        await asyncio.wait_for(process.wait(), 5)
                    except TimeoutError:
                        process.kill()
                        await process.wait()
                if communication:
                    await communication
