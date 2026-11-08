"""Gates 7+8: memory and brain. Offline fakes only; costs/tokens are FAKE
fixture values, not real billing, and no paid or live service is called."""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
import yaml

from agents.ghost import brain as brain_mod
from agents.ghost.brain import Brain, UserMemory, classify_alert_code
from agents.ghost.brain_service import create_app as brain_app
from agents.ghost import brain_service as private_brain

ROOT = Path(__file__).resolve().parents[1]
T1, T2 = str(uuid.uuid4()), str(uuid.uuid4())
FAKE_COST, FAKE_IN, FAKE_OUT = 0.0042, 310, 95  # FAKE fixture numbers


class FakeHermes:
    """Tenant-partitioned fake of the Tank /v1/ghost/autumbra/memory corridor."""

    def __init__(self):
        self.rows: dict[str, dict[str, dict]] = {}

    async def remember(self, tenant_id, text, kind, source, *, record_id=None, meta=None, **_):
        rid = record_id or str(uuid.uuid4())
        self.rows.setdefault(str(tenant_id), {})[rid] = {"id": rid, "text": text, "kind": kind,
                                                          "source": source, "meta": dict(meta or {})}
        return {"id": rid}

    async def recall(self, tenant_id, query, *, limit=None, **_):
        return list(self.rows.get(str(tenant_id), {}).values())[: limit or 50]

    async def records(self, tenant_id, **_):
        return list(self.rows.get(str(tenant_id), {}).values())

    async def forget(self, memory_id, tenant_id, **_):
        self.rows.get(str(tenant_id), {}).pop(str(memory_id), None)


@pytest.fixture
def rig(monkeypatch, tmp_path):
    monkeypatch.setenv("TANK_KEY", "ghost-test")
    monkeypatch.setenv("GHOST_BRAIN_ENABLED", "true")
    calls = []
    route_cache: dict[tuple, str] = {}
    route_cache_on = {"on": False}  # only the route-cache test turns the fake Tank cache on

    def fake_tank(request: httpx.Request) -> httpx.Response:
        """FAKE Tank /v1/route. Mirrors Tank's documented cache identity: tenant,
        task type, case_ref (with matter_matching: no case_ref, no cache) and input."""
        import json
        body = json.loads(request.content)
        assert request.url.path == "/v1/route" and body["agent"] == "ghost"
        key = (body["tenant_id"], body["task_type"], body.get("case_ref"), body["messages"][-1]["content"])
        # Policy per tank-patches/gates-7-8.patch: only safe types, only with case_ref.
        cacheable = route_cache_on["on"] and body["task_type"] in brain_mod.CACHE_ELIGIBLE and bool(body.get("case_ref"))
        if cacheable and key in route_cache:
            return httpx.Response(200, json={"ledger_id": str(uuid.uuid4()), "model": "cache", "rung": 0,
                                             "content": route_cache[key], "tokens_in": 0, "tokens_out": 0,
                                             "cost_usd": 0, "latency_ms": 1, "execution": None})
        calls.append(body)
        answer = f"Answer #{len(calls)}: rotate the WAF rule."
        if cacheable:
            route_cache[key] = answer
        return httpx.Response(200, json={"ledger_id": str(uuid.uuid4()), "model": "fake-luna", "rung": 1,
                                         "content": answer, "tokens_in": FAKE_IN, "tokens_out": FAKE_OUT,
                                         "cost_usd": FAKE_COST, "latency_ms": 1, "execution": {"fake": True}})

    tank_http = httpx.AsyncClient(transport=httpx.MockTransport(fake_tank))
    # Unit-only typed Tank boundary. The canonical suite exercises the shipped
    # client, signed actor, private service, Tank admission and real SQL receipts.
    from types import SimpleNamespace
    from agents.ghost.app import _brain_service
    inputs = {}
    async def unit_actor(request, tenant, user=None):
        return SimpleNamespace(tenant_id=str(tenant), user_id=user, role="member")
    monkeypatch.setattr(private_brain, 'verified_actor', unit_actor)
    class UnitTankClient:
        async def delegate_task(self, actor, run, task, payload, recall):
            inputs[run] = payload
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service_app), base_url="http://placeholder") as c:
                response = await c.post("/tasks", params={"tenant_id":actor.tenant_id,"user_id":actor.user_id},
                    json={"run_id":run,"task_key":task,"input":payload,"recall":recall})
                assert response.status_code == 200, response.text
                return response.json()
        async def room_task(self, actor, run, messages):
            task, text = messages[-1]['content'].split(': ',1)
            response = await tank_http.post('http://tank/v1/route',json={
                'tenant_id':actor.tenant_id,'agent':'ghost','task_type':task,'case_ref':inputs[run]['case_ref'],
                'messages':[*messages[:-1],{'role':'user','content':text}]})
            data=response.json()
            return {'choices':[{'message':{'content':data['content']}}],
                'receipt':{**data,'tenant_id':actor.tenant_id,'room':'ghost','task_type':'agent.ghost.think',
                           'task_id':str(uuid.uuid5(uuid.UUID(actor.tenant_id),actor.user_id+':'+run))}}
    monkeypatch.setattr(private_brain,'tank_client',lambda http:UnitTankClient())
    service_app = brain_app(tank_http)
    async def service(body, actor=None):
        actor = actor or SimpleNamespace(tenant_id=body['tenant_id'],user_id=body['user_id'],role='member')
        return await _brain_service(tank_http)(body,actor)

    hermes = FakeHermes()
    from agents.ghost.store import Store
    memory = UserMemory(hermes, Store(tmp_path / "brain.sqlite3"))
    calls_view = calls
    rig_brain = Brain(memory, service, [classify_alert_code])
    rig_brain.route_cache_on = route_cache_on
    return rig_brain, hermes, memory, calls_view


TASK = ("ghost.brain.explain_incident", "Spike of 403s on /login at 02:00 during deploy")


@pytest.mark.asyncio
async def test_1_request_brain_tank_route_receipt_memory(rig):
    brain, hermes, _memory, calls = rig
    out = await brain.run(T1, "alice", *TASK)
    assert out["status"] == "done" and out["source"] == "brain" and len(calls) == 1
    assert calls[0]["task_type"] == TASK[0] and calls[0]["tenant_id"] == T1
    assert out["model_receipts"][0]["ledger_id"] and out["cost_usd"] == FAKE_COST
    assert [s["action"] for s in out["steps"]] == ["recall", "tank_route", "remember"]
    stored = list(hermes.rows[T1].values())
    assert stored[0]["kind"] == "outcome" and stored[0]["meta"]["user_id"] == "alice"
    assert stored[0]["meta"]["task_key"] == brain_mod.task_key(*TASK)


@pytest.mark.asyncio
async def test_2_correction_applies_next_time_without_paid_call(rig):
    brain, _hermes, _memory, calls = rig
    await brain.run(T1, "alice", *TASK)
    assert await brain.correct(T1, "alice", *TASK, "Not an attack: planned maintenance window.")
    again = await brain.run(T1, "alice", *TASK)
    assert again["source"] == "memory_correction" and len(calls) == 1
    assert again["answer"] == "Not an attack: planned maintenance window."
    assert again["cost_usd"] == 0 and again["paid_calls"] == 0


@pytest.mark.asyncio
async def test_3_other_user_and_other_tenant_see_nothing(rig):
    brain, _hermes, memory, calls = rig
    await brain.run(T1, "alice", *TASK)
    assert await memory.list(T1, "bob") == [] and await memory.recall(T1, "bob", TASK[1]) == []
    assert await memory.list(T2, "alice") == [] and await memory.recall(T2, "alice", TASK[1]) == []
    bob = await brain.run(T1, "bob", *TASK)
    other = await brain.run(T2, "alice", *TASK)
    assert bob["source"] == other["source"] == "brain" and len(calls) == 3


@pytest.mark.asyncio
async def test_4_same_task_twice_reports_cost_and_tokens_each_run(rig):
    brain, _hermes, _memory, calls = rig
    # Uncorrected, exactly identical repeat. FAKE_COST is a fixed per-call price.
    before = len(calls)
    first = await brain.run(T1, "alice", *TASK)
    first_calls = len(calls) - before
    second = await brain.run(T1, "alice", *TASK)
    second_calls = len(calls) - before - first_calls
    assert not any(r["kind"] == "correction" for r in await brain.memory.list(T1, "alice"))
    assert (first_calls, first["paid_calls"]) == (1, 1) and (second_calls, second["paid_calls"]) == (0, 0)
    print(f"FAKE-FIXTURE fixed per-call price={FAKE_COST} USD; per-run paid_calls first={first['paid_calls']} "
          f"repeat={second['paid_calls']}")
    print(f"FAKE-FIXTURE first cost_usd={first['cost_usd']} tokens_in={first['tokens_in']} "
          f"tokens_out={first['tokens_out']}; repeat cost_usd={second['cost_usd']} "
          f"tokens_in={second['tokens_in']} tokens_out={second['tokens_out']} (not actual billing)")
    assert (first["cost_usd"], first["tokens_in"], first["tokens_out"]) == (FAKE_COST, FAKE_IN, FAKE_OUT)
    assert (second["cost_usd"], second["tokens_in"], second["tokens_out"]) == (0, 0, 0)
    assert second["source"] == "memory_repeat" and second["cache_eligible"] and len(calls) == 1


@pytest.mark.asyncio
async def test_memory_view_edit_forget_off_and_no_secrets(rig):
    brain, hermes, memory, calls = rig
    await brain.run(T1, "alice", *TASK)
    [row] = await memory.list(T1, "alice")
    await memory.edit(T1, "alice", row["id"], "Edited baseline note")
    assert (await memory.list(T1, "alice"))[0]["text"] == "Edited baseline note"
    with pytest.raises(KeyError):
        await memory.forget(T1, "bob", row["id"])
    await memory.forget(T1, "alice", row["id"])
    assert await memory.list(T1, "alice") == []
    memory.set_off(T1, "alice", True)
    assert await memory.remember(T1, "alice", "incident", "x") is None
    out = await brain.run(T1, "alice", *TASK)
    assert out["source"] == "brain" and await memory.list(T1, "alice") == []
    memory.set_off(T1, "alice", False)
    # Benign, obviously fake fixture (no credential): the shape alone is refused.
    benign = "fixed it; password: EXAMPLE"
    assert brain_mod.contains_secret(benign)
    assert await memory.remember(T1, "alice", "worked_fix", benign) is None
    with pytest.raises(ValueError):
        await memory.edit(T1, "alice", "x", benign)
    assert not any("EXAMPLE" in r["text"] for r in hermes.rows.get(T1, {}).values())


@pytest.mark.asyncio
async def test_code_pass_runs_before_brain_and_plan_fix_is_not_repeated(rig):
    brain, _hermes, _memory, calls = rig
    out = await brain.run(T1, "alice", "ghost.brain.classify_alert", "Workspace is slow")
    assert out["source"] == "code" and out["cost_usd"] == 0 and calls == []
    await brain.run(T1, "alice", "ghost.brain.plan_fix", "Plan fix for login 403s")
    await brain.run(T1, "alice", "ghost.brain.plan_fix", "Plan fix for login 403s")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_brain_switch_defaults_on_and_off_pauses_without_paid_call(rig, monkeypatch):
    brain, _hermes, _memory, calls = rig
    assert brain_mod.brain_enabled()
    monkeypatch.delenv("GHOST_BRAIN_ENABLED")
    assert not brain_mod.brain_enabled()
    monkeypatch.setenv("GHOST_BRAIN_ENABLED", "false")
    out = await brain.run(T1, "alice", *TASK)
    assert out["status"] == "paused" and calls == []


def test_compose_brain_service_without_profile_and_default_on():
    room = yaml.safe_load((ROOT / "agents/ghost/docker-compose.yml").read_text())
    assert room["services"]["ghost-brain"]["profiles"] == ["brain"]
    assert room["services"]["ghost-sandbox"]["profiles"] == ["brain"]
    assert room["services"]["ghost-brain"]["command"][1] == "ghost.brain_service:app"
    assert room["services"]["ghost-brain"]["networks"] == ["gw", "sandbox"]
    assert room["services"]["ghost-sandbox"]["networks"] == ["sandbox"]
    env = room["services"]["agent-ghost"]["environment"]
    assert env["GHOST_BRAIN_ENABLED"] == "${GHOST_BRAIN_ENABLED:-false}"


def test_shipped_tank_runtime_keeps_brain_default_off_without_policy_seed(monkeypatch):
    from command_tools.autumbra import brain_refusal
    monkeypatch.delenv("GHOST_BRAIN_ENABLED", raising=False)
    for task in ("ghost.brain.explain_incident", "ghost.brain.summarise_baseline",
                 "ghost.brain.classify_alert", "ghost.brain.plan_fix"):
        assert brain_refusal(task) == "GHOST_BRAIN_ENABLED is off."
    assert "GHOST_BRAIN_ENABLED:-false" in (ROOT / "docker-compose.yml").read_text()
    assert "ghost.brain." not in (ROOT / "tank/schema.sql").read_text()


@pytest.mark.asyncio
async def test_same_tenant_other_user_memory_view_edit_forget_and_corrections(rig):
    brain, hermes, memory, calls = rig
    await brain.run(T1, "alice", *TASK)
    [row] = await memory.list(T1, "alice")
    assert await memory.list(T1, "bob") == []
    with pytest.raises(KeyError):
        await memory.edit(T1, "bob", row["id"], "bob overwrites")
    with pytest.raises(KeyError):
        await memory.forget(T1, "bob", row["id"])
    assert (await memory.list(T1, "alice"))[0]["text"] == row["text"]
    await brain.correct(T1, "bob", *TASK, "Bob's private correction")
    alice = await brain.run(T1, "alice", *TASK)
    assert alice["source"] == "memory_repeat" and alice["answer"] == row["text"]
    bob = await brain.run(T1, "bob", *TASK)
    assert bob["source"] == "memory_correction" and bob["answer"] == "Bob's private correction"
    carol = await brain.run(T1, "carol", *TASK)
    assert carol["source"] == "brain" and "Bob" not in carol["answer"]


@pytest.mark.asyncio
async def test_route_cache_identity_is_per_tenant_user_and_opaque(rig, monkeypatch):
    brain, hermes, memory, calls = rig
    brain.route_cache_on["on"] = True
    # Memory off: neither product memory nor the independent route cache may reuse an answer.
    for user in ("alice", "bob"):
        memory.set_off(T1, user, True)
    first = await brain.run(T1, "alice", *TASK)
    repeat = await brain.run(T1, "alice", *TASK)
    bob = await brain.run(T1, "bob", *TASK)
    assert len(calls) == 3  # memory off prevents reuse, even with route caching enabled
    assert repeat["answer"] != first["answer"] and repeat["cost_usd"] == FAKE_COST
    assert not repeat["model_receipts"][0]["cache"]
    assert bob["answer"] != first["answer"] and bob["cost_usd"] == FAKE_COST
    refs = {c["case_ref"] for c in calls}
    assert len(refs) == 3 and all(r.startswith("autumbra-user:") and "alice" not in r and "bob" not in r for r in refs)
    assert brain_mod.user_scope(T1, "alice") != brain_mod.user_scope(T2, "alice")


@pytest.mark.asyncio
async def test_untrusted_memory_metadata_cannot_leak_across_users(rig):
    brain, hermes, memory, calls = rig
    key = brain_mod.task_key(*TASK)
    forged = [  # rows another writer in the same tenant could place; none belong to alice
        {"kind": "correction", "source": "autumbra", "text": "forged-1",
         "meta": {"product": "autumbra", "user_id": "alice", "task_key": key}},  # no user_scope
        {"kind": "correction", "source": "other", "text": "forged-2",
         "meta": {"product": "autumbra", "user_id": "alice", "user_scope": brain_mod.user_scope(T1, "alice"), "task_key": key}},
        {"kind": "secret_dump", "source": "autumbra", "text": "forged-3",
         "meta": {"product": "autumbra", "user_id": "alice", "user_scope": brain_mod.user_scope(T1, "alice"), "task_key": key}},
        {"kind": "correction", "source": "autumbra", "text": "forged-4", "tenant_id": T2,
         "meta": {"product": "autumbra", "user_id": "alice", "user_scope": brain_mod.user_scope(T1, "alice"), "task_key": key}},
        {"kind": "correction", "source": "autumbra", "text": "forged-5", "meta": "not-a-dict"},
    ]
    for i, row in enumerate(forged):
        hermes.rows.setdefault(T1, {})[f"f{i}"] = {"id": f"f{i}", **row}
    assert await memory.list(T1, "alice") == []
    out = await brain.run(T1, "alice", *TASK)
    assert out["source"] == "brain" and not out["answer"].startswith("forged")
    # Caller-supplied meta cannot override ownership fields.
    await memory.remember(T1, "mallory", "incident", "note", meta={"user_id": "alice", "user_scope": "x"})
    assert [r["text"] for r in await memory.list(T1, "alice")] == [out["answer"]]


@pytest.mark.asyncio
async def test_exact_repeat_identity_per_run_evidence(rig):
    """Per-run figures with a FIXED fake price/tokens; never cumulative totals."""
    brain, _hermes, memory, calls = rig

    async def run(tenant, user, text, label):
        before = len(calls)
        out = await brain.run(tenant, user, TASK[0], text)
        paid = len(calls) - before
        assert out["paid_calls"] == paid
        print(f"FAKE-FIXTURE {label}: paid_calls={paid} cost_usd={out['cost_usd']} "
              f"tokens_in={out['tokens_in']} tokens_out={out['tokens_out']} source={out['source']}")
        return paid, out

    def is_paid(result):
        paid, out = result
        return paid == 1 and (out["cost_usd"], out["tokens_in"], out["tokens_out"]) == (FAKE_COST, FAKE_IN, FAKE_OUT)

    def is_free(result):
        paid, out = result
        return paid == 0 and (out["cost_usd"], out["tokens_in"], out["tokens_out"]) == (0, 0, 0)

    text = TASK[1]
    assert is_paid(await run(T1, "alice", text, "first"))
    repeat = await run(T1, "alice", text, "exact_repeat")
    assert is_free(repeat) and repeat[1]["source"] == "memory_repeat"
    assert is_paid(await run(T1, "alice", text + " ", "changed_input"))
    assert is_paid(await run(T1, "dave", text, "different_user"))
    assert is_paid(await run(T2, "alice", text, "different_tenant"))
    # Correction overrides the stale stored result, at $0.
    await brain.correct(T1, "alice", TASK[0], text, "Corrected: maintenance window.")
    corrected = await run(T1, "alice", text, "after_correction")
    assert is_free(corrected) and corrected[1]["answer"] == "Corrected: maintenance window."
    # Off: no reuse.
    memory.set_off(T1, "alice", True)
    assert is_paid(await run(T1, "alice", text, "memory_off"))
    memory.set_off(T1, "alice", False)
    # Forget everything for this user: no reuse.
    for row in await memory.list(T1, "alice"):
        await memory.forget(T1, "alice", row["id"])
    assert is_paid(await run(T1, "alice", text, "after_forget"))


@pytest.mark.asyncio
async def test_default_off_has_no_memory_or_checkpoint_side_effects(rig, monkeypatch):
    brain, hermes, memory, calls = rig
    monkeypatch.delenv('GHOST_BRAIN_ENABLED')
    out = await brain.run(T1, 'alice', *TASK)
    assert out['source'] == 'brain_off' and calls == [] and hermes.rows == {}
    assert memory.store.db.execute('SELECT count(*) FROM ghost_brain_runs').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_paid_checkpoint_survives_memory_failure_retry_concurrency_and_restart(rig, monkeypatch):
    import asyncio
    brain, hermes, memory, calls = rig
    async def unavailable(*args, **kwargs):
        raise RuntimeError('hermes answered 503')
    monkeypatch.setattr(hermes, 'remember', unavailable)
    run_id = str(uuid.uuid4())
    first, repeat = await asyncio.gather(brain.run(T1, 'alice', *TASK, run_id), brain.run(T1, 'alice', *TASK, run_id))
    assert len(calls) == 1 and first['cost_usd'] == FAKE_COST
    assert first['memory_status'] == 'unavailable' and repeat['replayed']
    from agents.ghost.store import Store
    filename = memory.store.db.execute('PRAGMA database_list').fetchone()[2]
    restarted = Brain(UserMemory(hermes, Store(Path(filename))), brain.service)
    replay = await restarted.run(T1, 'alice', *TASK, run_id)
    assert replay['answer'] == first['answer'] and len(calls) == 1
    with pytest.raises(ValueError):
        await restarted.run(T1, 'alice', TASK[0], TASK[1] + ' changed', run_id)


@pytest.mark.asyncio
async def test_forget_and_off_invalidate_paid_checkpoint_and_derived_answers(rig):
    brain, _, memory, calls = rig
    run_id = str(uuid.uuid4())
    first = await brain.run(T1, 'alice', *TASK, run_id)
    [row] = await memory.list(T1, 'alice')
    await memory.forget(T1, 'alice', row['id'])
    replay = await brain.run(T1, 'alice', *TASK, run_id)
    assert replay['answer'] is None and replay['status'] == 'invalidated' and len(calls) == 1
    fresh = await brain.run(T1, 'alice', *TASK)
    assert fresh['answer'] != first['answer'] and len(calls) == 2
    memory.set_off(T1, 'alice', True)
    await brain.run(T1, 'alice', *TASK)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_auth_failure_is_not_storage_outage_or_paid_fallback(rig, monkeypatch):
    brain, hermes, _, calls = rig
    async def refused(*args, **kwargs):
        raise RuntimeError('hermes answered 403')
    monkeypatch.setattr(hermes, 'recall', refused)
    with pytest.raises(PermissionError):
        await brain.run(T1, 'alice', *TASK)
    assert calls == []


@pytest.mark.asyncio
async def test_watch_nonces_are_atomic_and_survive_restart(rig):
    import asyncio
    import time
    from agents.ghost.brain_state import BrainState
    from agents.ghost.store import Store
    _, _, memory, _ = rig
    filename = memory.store.db.execute('PRAGMA database_list').fetchone()[2]
    other = BrainState(Store(Path(filename)))
    claims = await asyncio.gather(memory.state.claim(T1, 'placeholder-unique-nonce', int(time.time()) + 60),
                                  other.claim(T1, 'placeholder-unique-nonce', int(time.time()) + 60))
    assert sorted(claims) == [False, True]
    assert not await BrainState(Store(Path(filename))).claim(T1, 'placeholder-unique-nonce', int(time.time()) + 60)


@pytest.mark.asyncio
async def test_memory_client_receives_owner_before_recall_limit_and_edit_is_replace(rig, monkeypatch):
    brain, hermes, memory, _ = rig
    from unittest.mock import AsyncMock
    recall = AsyncMock(wraps=hermes.recall)
    remember = AsyncMock(wraps=hermes.remember)
    monkeypatch.setattr(hermes, 'recall', recall)
    monkeypatch.setattr(hermes, 'remember', remember)
    await brain.run(T1, 'alice', *TASK)
    assert recall.call_args.kwargs['user_id'] == 'alice'
    [row] = await memory.list(T1, 'alice')
    await memory.edit(T1, 'alice', row['id'], 'Owner verified correction')
    assert remember.call_args.kwargs['user_id'] == 'alice'
    assert remember.call_args.kwargs['replace'] is True


@pytest.mark.asyncio
async def test_unsigned_control_cannot_use_body_identity_and_plain_task_is_memoryless(tmp_path, monkeypatch):
    from agents.ghost.app import create_app
    from agents.ghost.store import Store
    monkeypatch.setenv('TANK_KEY', 'placeholder-watch-key')
    monkeypatch.setenv('GHOST_BRAIN_ENABLED', 'true')
    app = create_app()
    store = Store(tmp_path / 'watch.sqlite3')
    memory = UserMemory(FakeHermes(), store)
    async def forbidden_service(body, actor=None):
        pytest.fail('Plain deterministic task should not call a model')
    app.state.store = store
    app.state.user_memory = memory
    app.state.brain = Brain(memory, forbidden_service, [classify_alert_code])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://watch',
                                 headers={'X-Tank-Key':'placeholder-watch-key'}) as client:
        for method, url, payload in [
            ('GET', f'/memory?tenant_id={T1}&user_id=alice', None),
            ('PUT', '/memory/settings', {'tenant_id':T1,'user_id':'alice','off':True}),
            ('POST', '/brain/corrections', {'tenant_id':T1,'user_id':'alice','task_type':TASK[0],
                                           'text':TASK[1],'corrected':'forged'})]:
            response = await client.request(method, url, **({'json':payload} if payload else {}))
            assert response.status_code in (401, 503)
        plain = await client.post('/brain/tasks', json={'tenant_id':T1,'user_id':'alice',
                   'task_type':'ghost.brain.classify_alert','text':'Workspace is slow'})
        assert plain.status_code == 200 and plain.json()['user_id'] is None
        assert plain.json()['source'] == 'code' and memory.memory.rows == {}


@pytest.mark.asyncio
async def test_real_hermes_sql_listing_shape_keeps_owned_rows_and_exact_repeats(rig, monkeypatch):
    brain, hermes, memory, calls = rig
    records = hermes.records
    async def sql_shape(*args, **kwargs):
        return [{**{k:v for k,v in row.items() if k not in {'text','source'}},
                 'claim':row['text'],'evidence':[row['source'],'urn:fixture:ledger']}
                for row in await records(*args,**kwargs)]
    monkeypatch.setattr(hermes,'records',sql_shape)
    first = await brain.run(T1,'alice',*TASK)
    assert (await memory.list(T1,'alice'))[0]['text'] == first['answer']
    repeated = await brain.run(T1,'alice',*TASK)
    assert repeated['source'] == 'memory_repeat' and len(calls) == 1


@pytest.mark.asyncio
async def test_forget_during_model_call_does_not_restore_deleted_context(rig):
    import asyncio
    brain, _, memory, calls = rig
    await memory.remember(T1,'alice','incident','Private context')
    [row] = await memory.list(T1,'alice')
    entered, resume = asyncio.Event(), asyncio.Event()
    service = brain.service
    async def delayed(body, actor=None):
        entered.set()
        await resume.wait()
        return await service(body, actor)
    brain.service = delayed
    task = asyncio.create_task(brain.run(T1,'alice',*TASK))
    await entered.wait()
    await memory.forget(T1,'alice',row['id'])
    resume.set()
    receipt = await task
    assert receipt['status'] == 'invalidated' and receipt['answer'] is None
    assert receipt['cost_usd'] == FAKE_COST and len(calls) == 1
    assert await memory.list(T1,'alice') == []


@pytest.mark.asyncio
async def test_provider_secret_is_not_returned_or_checkpointed(rig):
    brain, _, memory, calls = rig
    original = brain.service
    async def secret(body, actor=None):
        result = await original(body, actor)
        result['answer'] = 'password: EXAMPLE'
        return result
    brain.service = secret
    result = await brain.run(T1,'alice',*TASK)
    assert result['status'] == 'refused' and result['answer'] is None and len(calls) == 1
    assert await memory.list(T1,'alice') == []
    assert 'EXAMPLE' not in str([tuple(r) for r in memory.store.db.execute('SELECT * FROM ghost_brain_runs')])
