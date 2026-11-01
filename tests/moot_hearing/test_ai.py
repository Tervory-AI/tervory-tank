"""Existing Tank boundary is mocked; not one external/model call is made."""
import asyncio
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from agents.zenas.core.moot import hearing
from agents.zenas.core.moot.hearing_ai import AIExecutor
from agents.zenas.core.moot.hearing_store import Mutation
from .test_hearing import HUMANS, OWNER, started
from .test_reasoning import trace


class Store:
    def __init__(self, state):
        self.state = state
        self.requests = {}
        self.lock = asyncio.Lock()

    async def load(self, actor, ident):
        hearing.authorize(self.state, actor)
        return deepcopy(self.state)

    async def commit(self, actor, ident, req, revision, action, payload, transition):
        async with self.lock:
            hearing.authorize(self.state, actor)
            if req in self.requests:
                return Mutation(deepcopy(self.state), True)
            self.state = transition(self.state, actor, revision, payload)
            self.requests[req] = True
            return Mutation(deepcopy(self.state), False)

    async def mutate(self, *args):
        return (await self.commit(*args)).state


class Tank:
    def __init__(self, *, wait=False, malformed=False):
        self.calls = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False
        self.wait, self.malformed = wait, malformed

    async def route(self, tenant, task, messages):
        self.calls.append((tenant, task, messages))
        self.started.set()
        try:
            if self.wait: await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return {"ledger_id": str(uuid4()), "cost_usd": 0.002, "model": "offline-only-test-double",
            "content": "bad-json" if self.malformed else json.dumps({"kind": "submission", "text": "Supported argument", "authority_ids": ["case-1"], "reasoning": trace()})}


@pytest.mark.asyncio
async def test_duplicate_run_invokes_once_and_transcript_commits_once():
    s = started({seat: "ai" for seat in HUMANS}); store = Store(s); tank = Tank(wait=True)
    executor = AIExecutor(store, tank, poll_seconds=0.001)
    request = str(uuid4())
    first = asyncio.create_task(executor.run(OWNER, s["id"], request, s["revision"]))
    await tank.started.wait()
    retry = await executor.run(OWNER, s["id"], request, s["revision"])
    assert retry["pending_ai"]["status"] == "started" and len(tank.calls) == 1
    tank.release.set(); result = await first
    assert len(result["transcript"]) == len(result["receipts"]) == 1
    assert result["transcript"][0]["reasoning"]["uncertainty"]


@pytest.mark.asyncio
async def test_handover_cancels_active_call_and_human_continues_exact_context():
    s = started({seat: "ai" for seat in HUMANS}); store = Store(s); tank = Tank(wait=True)
    executor = AIExecutor(store, tank, poll_seconds=0.001)
    run = asyncio.create_task(executor.run(OWNER, s["id"], str(uuid4()), s["revision"]))
    await tank.started.wait()
    await store.mutate(OWNER, s["id"], str(uuid4()), store.state["revision"], "handover",
        {"seat": "applicant", "controller": {"kind": "human", "user_id": HUMANS["applicant"].user_id}},
        lambda s, a, r, p: hearing.change(s, a, r, "handover", p))
    result = await run
    assert tank.cancelled and not result["transcript"] and result["floor"] == "applicant"
    assert result["ai_attempts"][-1]["resolution"] == "revoked_call_cancelled"
    assert "real holding hidden" not in str(tank.calls[0])


@pytest.mark.asyncio
async def test_uncertain_started_call_is_not_replayed_on_restart():
    s = started({seat: "ai" for seat in HUMANS}); store = Store(s); tank = Tank(wait=True)
    request = str(uuid4()); executor = AIExecutor(store, tank)
    run = asyncio.create_task(executor.run(OWNER, s["id"], request, s["revision"]))
    await tank.started.wait(); run.cancel()
    with pytest.raises(asyncio.CancelledError): await run
    after_restart = await AIExecutor(store, Tank()).run(OWNER, s["id"], request, s["revision"])
    assert after_restart["pending_ai"]["status"] == "started" and len(tank.calls) == 1


@pytest.mark.asyncio
async def test_malformed_result_keeps_real_receipt_but_never_invents_ruling_or_turn():
    s = started({seat: "ai" for seat in HUMANS}); store = Store(s); tank = Tank(malformed=True)
    result = await AIExecutor(store, tank).run(OWNER, s["id"], str(uuid4()), s["revision"])
    assert not result["transcript"] and result["ruling"] is None
    assert result["receipts"][0]["discarded"] is True and result["receipts"][0]["cost_usd"] == 0.002
