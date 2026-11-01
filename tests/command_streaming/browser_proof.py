"""Explicit Chromium proof command; not part of the default no-browser suite."""
import asyncio
import os
from pathlib import Path

import pytest

import test_command_streaming as command_tests
from test_command import TENANT

command_pool = command_tests.command_pool
streaming = command_tests.streaming


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["complete", "broken", "broken_refresh", "disconnect"])
async def test_browser_streaming_through_workspace_and_tank(streaming, mode):
    b = streaming
    b.gateway.gated = True
    if mode in {"broken", "broken_refresh"}:
        b.gateway.mode = "eof"
    thread = await command_tests.thread(b)
    process = await asyncio.create_subprocess_exec("node", "tests/command_streaming/browser.cjs", env={
        **os.environ, "TANK_URL": str(b.api.base_url), "COMMAND_STREAMING_THREAD": thread,
        "COMMAND_STREAMING_MODE": mode,
    }, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    lines = []
    try:
        async with asyncio.timeout(45):
            while line := await process.stdout.readline():
                text = line.decode().strip()
                lines.append(text)
                if text == "PROVISIONAL":
                    assert not b.gateway.finished
                    state = (await b.api.get(f"/v1/command/threads/{thread}")).json()
                    assert [m["role"] for m in state["messages"]] == ["user"]
                    assert state["receipts"] == []
                    if mode != "disconnect":
                        b.gateway.release.set()
            assert await process.wait() == 0, "\n".join(lines)
        assert "PROVISIONAL" in lines
        if mode == "disconnect":
            await asyncio.wait_for(b.gateway.closed.wait(), 3)
        async with asyncio.timeout(3):
            while True:
                state = (await b.api.get(f"/v1/command/threads/{thread}")).json()
                if state["steps"][-1]["status"] in {"done", "failed"}:
                    break
                await asyncio.sleep(0.01)
        assert state["steps"][-1]["status"] == ("done" if mode == "complete" else "failed")
        if mode == "complete":
            assert state["messages"][-1]["content"] == command_tests.TEXT
        else:
            assert len(state["messages"]) == 1
            async with b.pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM tank.route_cache WHERE tenant_id=$1", TENANT) == 0
        assert len(b.gateway.calls) == 1
        print("\n".join(lines))
        Path(f"tests/command_streaming/browser-{mode}.txt").write_text("\n".join(lines) + "\n")
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
