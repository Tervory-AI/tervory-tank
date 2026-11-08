import ast
import asyncio
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace, ModuleType
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from fastapi import FastAPI, HTTPException
import httpx
import pgserver
from pydantic import BaseModel, ConfigDict, ValidationError
import pytest

ROOT = Path(__file__).resolve().parents[1]
TENANT = UUID('00000000-0000-4000-8000-000000000101')
OTHER = UUID('00000000-0000-4000-8000-000000000102')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def functions(path, names, values):
    # Exercise imported production functions, without reconstructing/executing an AST proposal.
    name = 'gate6_actual_' + path.stem
    module = sys.modules.get(name) or load(path, name)
    module.__dict__.update(values)
    selected = {name: getattr(module, name) for name in names}
    assert set(selected) == set(names)
    values.update(selected)
    return values


@pytest.fixture(scope='module')
def tank(tmp_path_factory):
    return ROOT / "tank"


@pytest.fixture
def tool(monkeypatch, tank):
    if 'gate6_actual_mcp_server' not in sys.modules:
        load(tank / 'mcp_server.py', 'gate6_actual_mcp_server')
    mod = load(tank / 'command_tools/workspace.py', 'workspace_tools')
    declarations = load(tank / 'command_tools/__init__.py', 'workspace_registry')
    tools = declarations.build_set('TENANT_TOOLS', (mod,))
    assert set(tools) == set(mod.TENANT_TOOLS)
    actor = SimpleNamespace(tenant_id=TENANT, user_id='offline-client', founder=False,
                            tenant_admin=False, squads=frozenset(), mcp_tools={})
    checks = []
    receipts = []
    command = ModuleType('command')
    class Body(BaseModel):
        model_config = ConfigDict(extra='forbid')
    class PlannedAction(Body):
        tool: str
        arguments: dict[str, Any]
    from dataclasses import dataclass
    @dataclass
    class Adapter:
        method: str
        path: str
        arguments: Any
        label: str
        paid: bool = False
        kind: str = 'other'
        skill: str | None = None
    command.Actor = Any
    command.PlannedAction = PlannedAction
    command.Adapter = Adapter
    others = [SimpleNamespace(__name__='command_tools.'+name, adapters=lambda command:{})
              for name in dict(declarations.ADAPTER_ORDER)]
    command.ADAPTERS = declarations.build_adapters(vars(command), (*others, mod))
    async def authorized(actor, *args, **kwargs):
        checks.append((actor.tenant_id, actor.user_id))
        if getattr(actor, 'revoked', False):
            raise HTTPException(403, 'Access revoked')
        return actor
    command.authorized_actor = authorized
    globals_ = dict(vars(command), HTTPException=HTTPException, ValidationError=ValidationError,
        TOOLS={}, SQUADS=frozenset(), FOUNDER_TOOLS=[], TENANT_ADMIN_TOOLS=[],
        TENANT_TOOLS=tools, FOUNDER_ONLY_TOOLS=set(), ADMIN_ONLY_TOOLS=set(),
        REQUEST_BODY_TOOLS=mod.REQUEST_BODY_TOOLS, BuildArgs=Body, dump=json.dumps,
        MAX_ACTIONS=4, Any=Any, Actor=Any, current_actor=lambda a:a, require_founder=lambda a:None)
    functions(tank / 'command.py', ('allowed_tools', 'require_tool', 'validate_action', 'action_adapter', 'adapter_request', 'verified_memory_actor'), globals_)
    for name in ('allowed_tools', 'require_tool', 'validate_action', 'adapter_request', 'verified_memory_actor'):
        setattr(command, name, globals_[name])
    command.current_actor = lambda a:a
    async def identity():
        raise HTTPException(401, 'Workspace authentication required')
    command.identity = identity
    async def task_receipts(task, owner):
        assert owner.tenant_id == TENANT
        if task != UUID('00000000-0000-4000-8000-000000000201'):
            raise HTTPException(404, 'Task not found')
        return {'rows': [], 'totals': {'cost_usd': None, 'baseline_cost_usd': None}}
    command.task_receipts = task_receipts
    monkeypatch.setitem(sys.modules, 'command', command)
    encoding = functions(tank / 'agent_skills.py', ('input_encoding',),
        {'lru_cache':lru_cache, 'Path':Path, '__file__':str(tank / 'agent_skills.py')})['input_encoding']
    encoding = lru_cache(maxsize=1)(encoding)
    class Pool:
        async def fetchrow(self, sql, *args):
            if sql.startswith('UPDATE'):
                assert 'WHERE id=$1 AND tenant_id=$2' in sql
                assert args[1] in (TENANT,OTHER)
                row = next(row for _,row in receipts if row['id'] == args[0])
                return row
            assert 'comparison_tokens_in,comparison_tokens_out' in sql
            row = {'id': uuid4(), 'cost_usd':0, 'baseline_cost_usd':None, 'baseline_status':'unpriced'}
            receipts.append((args, row))
            return row
    main = ModuleType('main')
    main.pool = lambda:Pool()
    main.box_region = lambda:'us-east'
    main.TaskCreate = lambda **data:SimpleNamespace(**data)
    main.Feedback = main.TaskCreate
    main.Message = main.TaskCreate
    calls = []
    async def tasks(tenant, limit):
        calls.append(('tasks', tenant, limit))
        assert tenant == actor.tenant_id
        return []
    async def create(data):
        calls.append(('create', data))
        assert data.tenant_id == actor.tenant_id and data.created_by == actor.user_id
        assert data.messages[0].content
        return {'id':'new-job', 'status':'queued'}
    async def feedback(ledger, data):
        calls.append(('feedback', ledger, data))
        assert data.tenant_id == actor.tenant_id and data.by == actor.user_id
        return {'ok':True}
    async def base(operation, request):
        data = json.loads(await request.body()) if request.method == 'POST' else dict(request.query_params)
        assert data['tenant_id'] == str(actor.tenant_id)
        if request.method == 'POST':
            assert data['created_by'] == actor.user_id
        calls.append(('base', operation, data))
        return httpx.Response(200, json={'body':data, 'operation':operation})
    # Starlette Response is what the real room proxy returns.
    async def base_response(operation, request):
        from starlette.responses import JSONResponse
        response = await base(operation, request)
        return JSONResponse(response.json())
    main.list_tasks, main.create_task, main.ledger_feedback, main.base_proxy = tasks, create, feedback, base_response
    # Gates 7+8 fail closed without a memory client; offline FakeMemory keeps the bracket live.
    from integrations.workspace.gates_memory import FakeMemory
    main.memory = FakeMemory()
    monkeypatch.setitem(sys.modules, 'main', main)
    monkeypatch.setitem(sys.modules, 'agent_skills', SimpleNamespace(input_encoding=encoding))
    async def savings(tenant):
        calls.append(('savings', tenant))
        assert tenant == actor.tenant_id
        return {'total':None, 'daily':[]}
    monkeypatch.setitem(sys.modules, 'proof', SimpleNamespace(client_savings=savings))
    confirmations = []
    def confirmation(owner, name, args):
        if not confirmations or confirmations[-1] != (owner.tenant_id, owner.user_id, name, args):
            raise HTTPException(409, 'Confirmed action required')
        return uuid4()
    monkeypatch.setitem(sys.modules, 'trigger_commands', SimpleNamespace(confirmation=confirmation))
    return SimpleNamespace(module=mod, actor=actor, command=command, receipts=receipts, checks=checks,
                           calls=calls, encoding=encoding(), main=main, confirmations=confirmations)


@pytest.mark.parametrize('index', range(9))
def test_code_first_fixture_never_calls_a_model(tool, index):
    fixture = json.loads((ROOT / 'tests/fixtures/gate6/commands.json').read_text())[index]
    async def run():
        for _ in range(2):
            plan = await tool.module.code_plan(tool.actor, [{'role':'user','content':fixture['text']}], uuid4())
            action = json.loads(plan.content)['actions'][0]
            assert action['tool'] == fixture['text'].split()[0]
            assert plan.ledger_id
        assert len(tool.receipts) == 2
        assert tool.receipts[0][1]['id'] != tool.receipts[1][1]['id']
        assert len(tool.checks) == 2
        assert tool.module.parse_command.cache_info().hits == 1
    asyncio.run(run())


@pytest.mark.parametrize('index', range(9))
def test_tools_share_command_dispatch_auth_confirmation_and_receipts(tool, index):
    text = json.loads((ROOT / 'tests/fixtures/gate6/commands.json').read_text())[index]['text']
    async def run():
        name, raw = tool.module.parse_command(str(TENANT), tool.actor.user_id, text)
        args = json.loads(raw)
        action = tool.command.validate_action(tool.command.PlannedAction(tool=name, arguments=args), tool.actor)
        method, path, query, body = tool.command.adapter_request(action, tool.actor)
        assert path == '/v1/command/workspace/' + name.removeprefix('workspace.')
        assert not ({'tenant_id','created_by','user_id'} & (query or body or {}).keys())
        if name in tool.module.CONFIRMED:
            with pytest.raises(HTTPException) as error:
                await tool.module.execute(name, args, tool.actor)
            assert error.value.status_code == 409
            assert tool.calls == [] and tool.receipts == []
            tool.confirmations.append((TENANT, tool.actor.user_id, name, args))
        result = await tool.module.execute(name, args, tool.actor)
        assert result['ledger_id'] == str(tool.receipts[-1][1]['id'])
        assert result['receipt'] == {'cost_usd':0, 'baseline_cost_usd':None, 'baseline_status':'unpriced'}
        assert tool.receipts[-1][0][0] == TENANT
        assert tool.receipts[-1][0][6] > 0
    asyncio.run(run())


def test_csv_cache_is_scoped_and_never_reuses_a_receipt(tool):
    async def run():
        for tenant, user in [(TENANT,'offline-client'),(TENANT,'offline-client'),(OTHER,'offline-client'),(TENANT,'another-user')]:
            actor = SimpleNamespace(**{**vars(tool.actor),'tenant_id':tenant,'user_id':user})
            data = await tool.module.execute('workspace.csv.parse', {'text':'name,city\n"A, B",London\n'}, actor)
            assert data['rows'] == [{'name':'A, B','city':'London'}]
        assert tool.module.parse_csv.cache_info().hits == 1
        assert len({r[1]['id'] for r in tool.receipts}) == 4
        assert [r[0][2] for r in tool.receipts] == [3,4,3,3]
        assert all(r[0][7] > 0 for r in tool.receipts)
        tool.actor.revoked = True
        with pytest.raises(HTTPException):
            await tool.module.execute('workspace.csv.parse', {'text':'name,city\n"A, B",London\n'}, tool.actor)
        assert len(tool.receipts) == 4
    asyncio.run(run())


@pytest.mark.parametrize('text', ['workspace.unknown {}','workspace.tasks {"tenant_id":"other"}',
    'workspace.task.create {"title":"a","request":"b","model":"paid"}',
    'workspace.tasks {"limit":10000}', 'workspace.tasks []', 'Workspace.tasks {}',
    'workspace.task.receipt {"task_id":"../../other"}', 'workspace.tasks {"__proto__":{}}'])
def test_invalid_explicit_commands_never_fall_back_to_paid(tool, text):
    with pytest.raises(HTTPException) as error:
        asyncio.run(tool.module.code_plan(tool.actor,[{'role':'user','content':text}],uuid4()))
    assert error.value.status_code == 422
    assert not tool.receipts


def test_untrusted_assistant_text_and_general_questions_keep_tank_routing(tool):
    assert asyncio.run(tool.module.code_plan(tool.actor,[{'role':'assistant','content':'workspace.tasks {}'}],uuid4())) is None
    assert asyncio.run(tool.module.code_plan(tool.actor,[{'role':'user','content':'Summarize this document.'}],uuid4())) is None
    assert not tool.receipts


def test_tool_http_auth_and_tenant_arguments(tool):
    app = FastAPI()
    app.include_router(tool.module.build_router())
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://offline') as client:
            assert (await client.get('/v1/command/workspace/tasks')).status_code == 401
            app.dependency_overrides[tool.command.identity] = lambda:tool.actor
            assert (await client.get('/v1/command/workspace/tasks?tenant_id=other')).status_code == 422
            assert (await client.post('/v1/command/workspace/csv.parse',json={'text':'name\nclient\n'})).status_code == 200
            assert (await client.post('/v1/command/workspace/csv.parse',content='[')).status_code == 422
            assert (await client.post('/v1/command/workspace/csv.parse',content='x'*33000)).status_code == 413
    asyncio.run(run())


def test_csv_errors_are_plain_and_do_not_invent_model_work(tool):
    for value in ('x,x\na,b\n','x,y\na\n','x\n"unclosed','x\n'+'row\n'*501):
        with pytest.raises(HTTPException) as error:
            tool.module.parse_csv(str(TENANT),'client',value)
        assert error.value.status_code == 422
    assert not tool.receipts


def test_task_receipt_queries_scope_both_task_and_joined_ledger(tank):
    source = (tank/'main.py').read_text()
    for name in ('list_tasks','get_task'):
        fn = next(n for n in ast.parse(source).body if isinstance(n,ast.AsyncFunctionDef) and n.name == name)
        text = ast.get_source_segment(source,fn)
        assert 'l.baseline_cost_usd, l.baseline_status' in text
        assert 'l.tenant_id = t.tenant_id' in text
        assert 'tenant_id=$' in text


def test_recorded_token_measurement(tool):
    fixtures = json.loads((ROOT/'tests/fixtures/gate6/commands.json').read_text())
    before = sum(len(tool.encoding.encode(row['text'])) for row in fixtures)
    measured = json.loads((ROOT/'tests/fixtures/gate6/tokens.json').read_text())
    assert measured == {'encoding':'cl100k_base', 'basis':'planner user input only; excludes system prompt and output',
                        'fixtures':len(fixtures), 'before':before, 'after':0}
    print(f'Tokens {before} -> 0 across {len(fixtures)} recorded code-first commands')


def test_frontend_receipts_tools_and_provider_boundary():
    result = subprocess.run(['node','tests/gate6_contract.cjs'],cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr


def test_zero_actual_tokens_still_price_paid_default_comparison(tmp_path):
    async def run(uri):
        conn = await asyncpg.connect(uri)
        try:
            await conn.execute('''
                CREATE SCHEMA tank;
                CREATE TABLE tank.baseline_settings(task_type text PRIMARY KEY, revision integer, override_model text);
                CREATE TABLE tank.proof_prices(model text PRIMARY KEY, family text, input_usd numeric, output_usd numeric, active boolean);
                CREATE TABLE tank.policy(task_type text, tenant_id uuid, model text);
                CREATE TABLE tank.provider_standards(provider text PRIMARY KEY, model text);
                CREATE FUNCTION tank.standard_model_for(family text) RETURNS text LANGUAGE sql STABLE AS $$
                  SELECT model FROM tank.provider_standards WHERE provider=split_part(family,'/',1)
                $$;
                CREATE TABLE tank.comparison_history(ledger_id uuid,tenant_id uuid,region text,valid_from timestamptz,valid_until timestamptz,comparison jsonb,reason text);
                CREATE TABLE tank.ledger(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),ts timestamptz DEFAULT now(),
                    tenant_id uuid,region text DEFAULT 'us-east',task_type text,model text,rung integer,
                    cache_hit boolean DEFAULT false,cost_usd numeric,tokens_in integer,tokens_out integer,
                    standard_model text,standard_cost_usd numeric,top_model text,top_cost_usd numeric,
                    baseline_model text,baseline_cost_usd numeric,baseline_status text,
                    baseline_priced_at timestamptz,comparison_revision integer DEFAULT 0);
                INSERT INTO tank.proof_prices VALUES('paid-default','provider/family',0.000002,0.000008,true);
                INSERT INTO tank.provider_standards VALUES('provider','paid-default');
                INSERT INTO tank.policy VALUES('command.turn',NULL,'paid-default');
            ''')
            migration = (ROOT/'integrations/tank/workspace.sql').read_text()
            await conn.execute(migration)
            await conn.execute(migration)  # Safe on every Tank start.
            await conn.execute('''CREATE TRIGGER priced BEFORE INSERT OR UPDATE OF comparison_revision ON tank.ledger
                                  FOR EACH ROW EXECUTE FUNCTION tank.price_receipt()''')
            async def insert(task='command.turn', model='code', tokens=(0,0), comparison=(100,50), tenant=TENANT, rung=3, cached=False):
                return await conn.fetchrow('''INSERT INTO tank.ledger(tenant_id,task_type,model,rung,cache_hit,cost_usd,
                    tokens_in,tokens_out,comparison_tokens_in,comparison_tokens_out)
                    VALUES($1,$2,$3,$4,$5,0,$6,$7,$8,$9) RETURNING *''',
                    tenant,task,model,rung,cached,*tokens,*comparison)
            code = await insert()
            assert code['tokens_in'] == code['tokens_out'] == code['cost_usd'] == 0
            assert float(code['baseline_cost_usd']) == pytest.approx(0.0006)
            assert code['baseline_status'] == 'estimated'
            cached = await insert(rung=4,cached=True)
            assert cached['baseline_cost_usd'] == code['baseline_cost_usd']
            await conn.execute('UPDATE tank.ledger SET comparison_tokens_out=75 WHERE id=$1 AND tenant_id=$2',code['id'],TENANT)
            completed = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1',code['id'])
            assert float(completed['baseline_cost_usd']) == pytest.approx(0.0008)
            assert completed['tokens_in'] == completed['tokens_out'] == completed['cost_usd'] == 0
            pending = await insert(task='no-configured-paid-default')
            assert pending['baseline_cost_usd'] is None and pending['baseline_status'] == 'unpriced'
            await conn.execute("INSERT INTO tank.proof_prices VALUES('override','provider/family',0.000003,0.000009,true)")
            await conn.execute("INSERT INTO tank.baseline_settings VALUES('command.turn',2,'override')")
            override = await insert()
            assert override['baseline_model'] == 'override' and float(override['baseline_cost_usd']) == pytest.approx(0.00075)
            await conn.execute("UPDATE tank.ledger SET comparison_revision=2 WHERE id=$1",code['id'])
            assert await conn.fetchval('SELECT count(*) FROM tank.comparison_history WHERE ledger_id=$1',code['id']) == 2
            other = await insert(tenant=OTHER)
            assert other['tenant_id'] != code['tenant_id']
            # Existing paid and legacy code receipts keep their original math.
            paid = await insert(model='paid-default',rung=1,tokens=(100,50),comparison=(None,None))
            assert float(paid['baseline_cost_usd']) == pytest.approx(0.00075)
            legacy = await insert(comparison=(None,None))
            assert legacy['baseline_cost_usd'] == 0 and legacy['baseline_status'] == 'measured'
            with pytest.raises(asyncpg.CheckViolationError):
                await insert(comparison=(-1,0))
        finally:
            await conn.close()
    # Unix socket only; no external database or service is contacted.
    server = pgserver.get_server(str(tmp_path/'pg'), cleanup_mode='delete')
    try:
        asyncio.run(run(server.get_uri()))
    finally:
        server.cleanup()


def test_recorded_before_after_uses_existing_tank_router(tool, tank, monkeypatch):
    async def no_plan(*args, **kwargs):
        return None
    for name, attribute in [('market_lab_ml3','code_plan'),('tisan_requests','code_plan'),
        ('memory_routes','remember_turn'),('radix_watch','code_plan'),('radix_repo','code_plan'),
        ('trigger_bot_api','plan'),('trigger_routes','code_plan')]:
        monkeypatch.setitem(sys.modules,name,SimpleNamespace(**{attribute:no_plan}))
    paid_inputs = []
    async def fake_router(request, **kwargs):
        assert request.tenant_id == TENANT and request.task_type == 'command.turn'
        paid_inputs.append(request.messages[-1].content)
        return SimpleNamespace(content='',ledger_id=uuid4())
    tool.main.RouteRequest = lambda **data:SimpleNamespace(**data)
    tool.main.run_route = fake_router
    baseline_registry = SimpleNamespace(plan_products=no_plan)
    monkeypatch.setitem(sys.modules,'command_tools',baseline_registry)
    import uuid
    values = {'Actor':Any,'TokenSink':Any,'Any':Any,'uuid':uuid,
              'autumbra_enforce_code_plan':no_plan,'policy_code_plan':no_plan,'tiger_code_plan':no_plan}
    route = functions(tank/'command.py',('route_turn',),values)['route_turn']
    fixtures = json.loads((ROOT/'tests/fixtures/gate6/commands.json').read_text())
    async def run():
        for fixture in fixtures:
            await route(tool.actor,[{'role':'user','content':fixture['text']}],model='auto')
        assert len(paid_inputs) == len(fixtures)
        before = sum(len(tool.encoding.encode(text)) for text in paid_inputs)
        paid_inputs.clear()
        registry = load(tank/'command_tools/__init__.py','gate6_planners')
        async def code_planners(actor,messages,task_id):
            return await registry.plan_products(actor,messages,task_id,products=(tool.module,))
        baseline_registry.plan_products = code_planners
        for fixture in fixtures:
            await route(tool.actor,[{'role':'user','content':fixture['text']}],model='auto')
        after = sum(len(tool.encoding.encode(text)) for text in paid_inputs)
        measured = json.loads((ROOT/'tests/fixtures/gate6/tokens.json').read_text())
        assert before == measured['before'] and after == measured['after']
        assert len(tool.receipts) == len(fixtures)
    asyncio.run(run())


def test_mcp_catalog_and_command_tools_share_strict_arguments_and_confirm(tool, tank):
    mcp = functions(tank/'mcp_server.py',('readonly','tools'),{'command':tool.command})
    names = {entry['name']:entry for entry in mcp['tools'](tool.actor)['tools']}
    assert set(names) == set(tool.module.TENANT_TOOLS)
    for name, schema in tool.module.SCHEMAS.items():
        assert names[name]['inputSchema'] == schema.model_json_schema()
        assert names[name]['inputSchema']['additionalProperties'] is False
        assert names[name]['annotations']['readOnlyHint'] == (name not in tool.module.POST)
    # MCP's actual entrypoint always validates and proposes the very same card;
    # writes cannot directly invoke the backend or bypass human confirmation.
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def editing(thread, actor):
        assert actor.tenant_id == TENANT
        yield None,{},{}
    proposed = []
    async def propose(conn, owned, state, action, actor):
        proposed.append(action)
        return {'card_id':str(uuid4())}
    tool.command.editing = editing
    tool.command.propose_action = propose
    tool.command.dump = json.dumps
    values = {'command':tool.command,'HTTPException':HTTPException,'ISSUER':'https://app.tervory.com','readonly':mcp['readonly']}
    call = functions(tank/'mcp_server.py',('call_tool',),values)['call_tool']
    async def run():
        result = await call({'name':'workspace.task.create','arguments':{'title':'Own task','request':'Own action'}},
                          tool.actor,{'thread_id':uuid4()})
        assert json.loads(result['content'][0]['text'])['status'] == 'pending'
        assert len(proposed) == 1 and not tool.calls and not tool.receipts
        with pytest.raises(HTTPException):
            await call({'name':'workspace.task.create','arguments':{'title':'Own','request':'Action','tenant_id':str(OTHER)}},
                       tool.actor,{'thread_id':uuid4()})
        assert len(proposed) == 1
    asyncio.run(run())


def test_tool_timeout_has_one_attempt_and_reconcilable_receipt(tool, monkeypatch):
    attempts = []
    async def stalled(tenant, limit):
        attempts.append(tenant)
        await asyncio.sleep(1)
    tool.main.list_tasks = stalled
    monkeypatch.setattr(tool.module,'asyncio',SimpleNamespace(timeout=lambda seconds:asyncio.timeout(0.01)))
    async def run():
        with pytest.raises(HTTPException) as error:
            await tool.module.execute('workspace.tasks',{},tool.actor)
        assert error.value.status_code == 503
        assert error.value.detail['ledger_id'] == str(tool.receipts[0][1]['id'])
        assert 'Check its receipt' in error.value.detail['message']
        assert attempts == [TENANT]
    asyncio.run(run())


def test_missing_room_setting_is_plain_and_does_not_requeue(tool):
    async def missing(*args):
        raise HTTPException(503,'Missing setting: TANK_KEY_BASE')
    tool.main.base_proxy = missing
    async def run():
        with pytest.raises(HTTPException) as error:
            await tool.module.execute('workspace.files',{},tool.actor)
        assert error.value.status_code == 503
        assert error.value.detail['message'] == 'Missing setting: TANK_KEY_BASE'
        assert error.value.detail['ledger_id'] == str(tool.receipts[0][1]['id'])
        assert len(tool.receipts) == 1
    asyncio.run(run())
