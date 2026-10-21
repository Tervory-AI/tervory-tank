"""Base-only sibling exec API. No Docker socket, daemon, capabilities or keys.

Only Base's brain and this service join its internal network. Each command gets
one WASI-restricted tmpfs run directory. Files cross the API explicitly;
Base memory, sessions and other run volumes are never mounted in this service.
"""
from __future__ import annotations

import asyncio
import base64
import os
import signal
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()
gate = asyncio.Semaphore(1)
ROOT = Path(os.environ.get("SANDBOX_WORK_DIR", "/work"))


class Execute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    task_id: uuid.UUID
    command: str = Field(min_length=1, max_length=64000)
    files: dict[str, str] = Field(default_factory=dict, max_length=32)


def file_path(work: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or any(part in {"..", ".tmp"} for part in relative.parts):
        raise HTTPException(422, "Invalid run file path")
    path = work / relative
    if not path.resolve().is_relative_to(work.resolve()) or path.is_symlink():
        raise HTTPException(422, "Run files cannot escape the work directory")
    return path


@app.get("/health")
async def health():
    return {"ok": True, "room": "base", "backend": "sibling-exec", "runtime": "cpython-wasi"}


@app.post("/exec")
async def execute(body: Execute):
    async with gate:
        work = ROOT / str(body.tenant_id) / str(body.task_id)
        if work.is_symlink() or work.parent.is_symlink():
            raise HTTPException(422, "Invalid run directory")
        work.mkdir(parents=True, exist_ok=True, mode=0o700)
        (work / ".tmp").mkdir(exist_ok=True, mode=0o700)
        total = 0
        for name, value in body.files.items():
            path = file_path(work, name)
            try:
                content = base64.b64decode(value, validate=True)
            except ValueError:
                raise HTTPException(422, "Invalid run file encoding") from None
            total += len(content)
            if total > 2_000_000:
                raise HTTPException(413, "Run files too large")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        process = await asyncio.create_subprocess_exec(sys.executable, "-m", "brain.sandbox_exec", str(work),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": "/app", "LANG": "C.UTF-8"},
            start_new_session=True)
        output = bytearray()
        truncated = False
        async def collect():
            nonlocal truncated
            process.stdin.write(body.command.encode())
            await process.stdin.drain()
            process.stdin.close()
            while chunk := await process.stdout.read(8192):
                output.extend(chunk)
                if len(output) > 64000:
                    truncated = True
                    break
            if not truncated:
                await process.wait()
        try:
            await asyncio.wait_for(collect(), 30)
        except asyncio.TimeoutError:
            output.extend(b"\nCommand timed out.")
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
        files = {}
        total = 0
        for index, path in enumerate(work.rglob("*")):
            if index > 512:
                break
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(work.resolve()):
                continue
            if ".tmp" in path.relative_to(work).parts or path.stat().st_size > 256000:
                continue
            total += path.stat().st_size
            if total > 2_000_000 or len(files) >= 32:
                break
            files[str(path.relative_to(work))] = base64.b64encode(path.read_bytes()).decode()
        shutil.rmtree(work)
        return {"exit_code": process.returncode, "output": output[:64000].decode(errors="replace"),
                "truncated": truncated, "files": files, "network": "none", "backend": "sibling-exec", "runtime": "cpython-wasi"}
