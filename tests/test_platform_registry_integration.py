"""Real isolated PostgreSQL and the existing offline Tank gateway/router fixture."""
import json
from trigger_signin_fakes import set_founders, native_provider, ORG
from types import SimpleNamespace
import uuid

import pytest
import pytest_asyncio

import graduate
import routellm_shadow as routing
from test_tank_routellm import real_tank as real_tank

TASK = 'placeholder.route'
STRONG = 'placeholder-strong'
WEAK = 'placeholder-weak'
FOUNDER = {'X-Tervory-Admin': 'placeholder-founder'}


@pytest_asyncio.fixture
async def serving(real_tank, monkeypatch):
    real = real_tank
    set_founders(monkeypatch, 'placeholder-founder')
    signin = native_provider(monkeypatch, {ORG: str(real.tenants[0]), '10002': str(real.tenants[1])})
    real.native_headers = signin.workspace_headers
    signed = {'x-trigger-signin-org': ORG, 'x-trigger-signin-token': signin.token(sub='placeholder-founder')}
    monkeypatch.setitem(FOUNDER, 'x-trigger-signin-org', signed['x-trigger-signin-org'])
    monkeypatch.setitem(FOUNDER, 'x-trigger-signin-token', signed['x-trigger-signin-token'])
    # Keep the real startup/SQL, but stop this fixture's worker so explicitly
    # inserted revalidation jobs cannot race its deterministic eval assertions.
    for handler in real.tank.app.router.on_shutdown:
        if handler.__module__ == 'skala_revalidation':
            await handler()
    async with real.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy(task_type,model,routellm_weak_model,routellm_threshold,
            eval_threshold,min_shadow_samples,cache_scope)
            VALUES($1,$2,$3,0.5,0.99,200,'none')""", TASK, STRONG, WEAK)
        row = dict(await conn.fetchrow('SELECT * FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL', TASK))
        candidate = routing.configuration(row).candidate
        await conn.execute('UPDATE tank.policy SET candidate_model=$2 WHERE task_type=$1 AND tenant_id IS NULL', TASK, candidate)
    state = SimpleNamespace(evidence=graduate.Evidence(samples=200, agreement=1))
    async def evidence(_conn, _policy):
        return state.evidence
    monkeypatch.setattr(real.tank, '_load_evidence', evidence)
    return SimpleNamespace(real=real, tank=real.tank, state=state, candidate=candidate)


async def promote(serving):
    response = await serving.real.client.post('/v1/graduation/' + TASK + '/promote', json={}, headers=FOUNDER)
    assert response.status_code == 200, response.text
    return response.json()


async def request(serving, *, priority='standard'):
    response = await serving.real.client.post('/v1/route', json={
        'tenant_id': str(serving.real.tenants[0]), 'agent': 'placeholder', 'task_type': TASK,
        'priority': priority, 'messages': [{'role': 'user', 'content': 'placeholder question'}]})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_founder_gate_fingerprint_and_automatic_hold(serving):
    real = serving.real
    denied = await real.client.post('/v1/graduation/' + TASK + '/promote', json={})
    assert denied.status_code == 404
    move = await serving.tank._move_task(TASK, automatic=True)
    assert move.action == 'hold' and move.reason == 'proven, waiting for a person'
    for samples, agreement in [(199, 1), (200, .989)]:
        serving.state.evidence = graduate.Evidence(samples=samples, agreement=agreement)
        response = await real.client.post('/v1/graduation/' + TASK + '/promote', json={}, headers=FOUNDER)
        assert response.status_code == 409
    serving.state.evidence = graduate.Evidence(samples=200, agreement=.99)
    async with real.pool.acquire() as conn:
        await conn.execute('UPDATE tank.policy SET routellm_threshold=0.6 WHERE task_type=$1 AND tenant_id IS NULL', TASK)
    refused = await real.client.post('/v1/graduation/' + TASK + '/promote', json={}, headers=FOUNDER)
    assert refused.status_code == 400
    async with real.pool.acquire() as conn:
        await conn.execute('UPDATE tank.policy SET routellm_threshold=0.5 WHERE task_type=$1 AND tenant_id IS NULL', TASK)
    result = await promote(serving)
    assert result['model'] == serving.candidate and result['previous_model'] == STRONG


@pytest.mark.asyncio
async def test_live_choices_receipts_shadow_suppression_and_rollback(serving, monkeypatch):
    await promote(serving)
    real = serving.real
    shadows = []
    async def unexpected(*args, **kwargs):
        shadows.append('placeholder-unexpected-shadow')
    monkeypatch.setattr(serving.tank, '_shadow', unexpected)
    monkeypatch.setattr(routing, 'observe', unexpected)
    for score, expected in [(.2, WEAK), (.8, STRONG)]:
        real.state.score = score
        answer = await request(serving)
        assert answer['model'] == expected and answer['rung'] == 1
        async with real.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2',
                                      uuid.UUID(answer['ledger_id']), real.tenants[0])
        assert row['model'] == expected and row['routellm_model'] == expected
        assert row['routellm_status'] == 'served' and row['routellm_score'] == pytest.approx(score)
        assert row['routellm_weak_model'] == WEAK and float(row['routellm_threshold']) == .5
    assert not shadows
    changed = await real.client.put('/v1/policy/' + TASK + '/routellm', json={}, headers=FOUNDER)
    assert changed.status_code == 409
    real.state.score = .2
    calls = real.state.router_calls
    urgent = await request(serving, priority='urgent')
    assert urgent['model'] == STRONG and real.state.router_calls == calls
    response = await real.client.post('/v1/graduation/' + TASK + '/rollback', json={}, headers=FOUNDER)
    assert response.status_code == 200 and response.json()['model'] == STRONG
    assert (await request(serving))['model'] == STRONG


@pytest.mark.asyncio
async def test_drift_and_scorer_failure_deliver_and_record_strong(serving):
    await promote(serving)
    real = serving.real
    real.state.score = None
    answer = await request(serving)
    assert answer['model'] == STRONG
    async with real.pool.acquire() as conn:
        await conn.execute('UPDATE tank.policy SET routellm_threshold=0.6 WHERE task_type=$1 AND tenant_id IS NULL', TASK)
    real.state.score = .2
    answer = await request(serving)
    async with real.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2',
                                  uuid.UUID(answer['ledger_id']), real.tenants[0])
    assert row['model'] == STRONG and row['routellm_status'] == 'served' and row['routellm_score'] is None


@pytest.mark.asyncio
async def test_revalidation_evaluates_cases_and_records_real_result(serving):
    import skala_revalidation as revalidation
    from gold import PLATFORM_TENANT
    await promote(serving)
    real, tank = serving.real, serving.tank
    job_id = uuid.uuid4()
    async with real.pool.acquire() as conn:
        policy = dict(await conn.fetchrow('SELECT * FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL', TASK))
        await conn.execute("""INSERT INTO tank.skills(id,version,agent,task_type,state)
            VALUES($1,'1.0.0','placeholder',$2,'approved')""", 'placeholder.skill', TASK)
        await conn.execute("""INSERT INTO tank.skill_revalidations
            (id,tenant_id,task_type,old_model,model,policy,skill_id,version)
            VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,'1.0.0')""", job_id, PLATFORM_TENANT, TASK,
            STRONG, serving.candidate, json.dumps(policy, default=str), 'placeholder.skill')
        job = dict(await conn.fetchrow('SELECT * FROM tank.skill_revalidations WHERE id=$1', job_id))
    context = SimpleNamespace(calls=0, cost_usd=0)
    package = SimpleNamespace(agent='placeholder', ref='placeholder.skill@1.0.0')
    token = revalidation.ACTIVE.set(job)
    try:
        bound = revalidation.eval_context(tank, package, context)
        for score in (.2, .8):
            real.state.score = score
            result = await bound._model(task_type=TASK, messages=[{'role': 'user', 'content': 'placeholder-eval'}])
            assert result['content']
        await revalidation.record(tank, {'score': 1, 'threshold': .99, 'eligible': True,
            'passed': 2, 'total': 2, 'cost_usd': .002, 'details': []})
    finally:
        revalidation.ACTIVE.reset(token)
    async with real.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.skill_revalidations WHERE id=$1', job_id)
        evaluation = await conn.fetchrow('SELECT * FROM tank.skill_evals WHERE revalidation_id=$1', job_id)
        calls = await conn.fetch("SELECT model,routellm_status FROM tank.ledger WHERE skill=$1 ORDER BY ts", package.ref + '#preview')
    assert row['completed_at'] and row['error'] is None
    assert evaluation['model'] == serving.candidate and evaluation['passed'] == 2
    assert [(row['model'], row['routellm_status']) for row in calls] == [(WEAK, 'served'), (STRONG, 'served')]


@pytest.mark.asyncio
async def test_teachers_sources_counts_receipt_and_tenant_isolation(serving, monkeypatch):
    import command
    import training
    from command_tools.skala import TeachersArgs
    real, tenant, foreign = serving.real, serving.real.tenants[0], serving.real.tenants[1]
    ledger = {}
    async with real.pool.acquire() as conn:
        for version in ('1.0.0', '2.0.0'):
            await conn.execute("INSERT INTO tank.skills(id,version,agent,task_type) VALUES($1,$2,'placeholder',$3)",
                               'placeholder.skill', version, TASK)
        for rung in (1, 2, 3, 4):
            ledger[rung] = uuid.uuid4()
            model = 'placeholder-teacher-' + str(rung)
            await conn.execute("""INSERT INTO tank.ledger(id,tenant_id,agent,task_type,rung,model,feedback,feedback_by,accept_after)
                VALUES($1,$2,'placeholder',$3,$4,$5,'accepted','placeholder-founder',now()-interval '1 day')""",
                ledger[rung], tenant, TASK, rung, model)
            await conn.execute("""INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
                VALUES($1,$2,$3,$4::jsonb,$5)""", ledger[rung], tenant, TASK,
                json.dumps([{'role': 'user', 'content': 'placeholder-input'}]), 'placeholder-sensitive-output')
        foreign_ledger = uuid.uuid4()
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,rung,model) VALUES($1,$2,'placeholder',$3,1,$4)",
                           foreign_ledger, foreign, TASK, 'placeholder-foreign-teacher')
        await training.collect_ledger(conn, tenant)
        pairs = await conn.fetch("SELECT source_ref,teacher_model FROM tank.training_pairs WHERE tenant_id=$1 AND source='client_accepted'", tenant)
        assert {pair['source_ref']: pair['teacher_model'] for pair in pairs} == {
            str(ledger[rung]): 'placeholder-teacher-' + str(rung) if rung in (1, 2) else None for rung in ledger}
        sources = [('ledger', ledger[rung]) for rung in ledger] + [('package', ledger[1]), ('ledger', foreign_ledger)]
        for source, ref in sources:
            gold_id = uuid.uuid4()
            await conn.execute("""INSERT INTO tank.gold_examples
                (id,tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash)
                VALUES($1,$2,'us-east',$3,'placeholder',$4::jsonb,$5::jsonb,$6,$7,$8)""",
                gold_id, tenant, 'placeholder.skill', json.dumps({'placeholder': 'placeholder-input'}),
                json.dumps({'placeholder': 'placeholder-sensitive-output'}), source, str(ref), 'placeholder-' + str(gold_id))
            row = {'id': gold_id, 'tenant_id': tenant, 'agent': 'placeholder', 'skill_id': 'placeholder.skill',
                   'input': {'placeholder': 'placeholder-input'}, 'expected': {'placeholder': 'placeholder-sensitive-output'},
                   'checked_by': 'placeholder-founder', 'holdout': False, 'source': source, 'source_ref': str(ref)}
            await training.pair_from_gold(conn, row)
            teacher = await conn.fetchval('SELECT teacher_model FROM tank.training_pairs WHERE tenant_id=$1 AND gold_id=$2', tenant, gold_id)
            expected = ('placeholder-teacher-' + str(next(r for r in (1, 2) if ledger[r] == ref))
                        if source == 'ledger' and ref in (ledger[1], ledger[2]) else None)
            assert teacher == expected
        # Deliberately distinct inactive, negative, holdout and foreign rows
        # verify the public count query against the table, rather than a fake DB.
        for owner, active, polarity, holdout, teacher in [
            (tenant, False, 'positive', False, 'placeholder-inactive'),
            (tenant, True, 'negative', False, 'placeholder-negative'),
            (tenant, True, 'positive', True, 'placeholder-holdout'),
            (foreign, True, 'positive', False, 'placeholder-foreign')]:
            await conn.execute("""INSERT INTO tank.training_pairs
                (tenant_id,region,agent,task_type,input,output,approved_by,source,source_ref,active,polarity,holdout,teacher_model)
                VALUES($1,'us-east','placeholder',$2,'{}'::jsonb,'{}'::jsonb,'placeholder-founder',
                'placeholder-seed',$3,$4,$5,$6,$7)""", owner, TASK, str(uuid.uuid4()), active, polarity, holdout, teacher)
        truth = await conn.fetch("""SELECT teacher_model,count(*) AS count,max(created_at) AS newest_created_at
            FROM tank.training_pairs WHERE tenant_id=$1 AND active AND polarity='positive'
            GROUP BY teacher_model""", tenant)
    headers = {**FOUNDER, 'X-Tervory-User': 'placeholder-founder', 'X-Tervory-Tenant': str(tenant)}
    response = await real.client.get('/v1/training/teachers', headers=headers,
        params={'skill_id': 'placeholder.skill', 'tenant_id': str(foreign)})
    assert response.status_code == 200, response.text
    for invalid_skill in ('placeholder', 'placeholder.' + 'x' * 188, ''):
        invalid = await real.client.get('/v1/training/teachers', headers=headers,
                                       params={'skill_id': invalid_skill})
        assert invalid.status_code == 422, invalid.text
    result = response.json()
    assert result['count'] == len(result['items']) == len(truth) * 2
    for version in ('1.0.0', '2.0.0'):
        actual = {row['teacher_model']: (row['count'], row['newest_created_at'])
                  for row in result['items'] if row['name'] == version}
        assert actual == {row['teacher_model']: (row['count'], row['newest_created_at'].isoformat()) for row in truth}
    assert 'placeholder-input' not in response.text and 'placeholder-sensitive-output' not in response.text
    assert 'placeholder-foreign' not in response.text
    assert all(row['task_type'] == TASK for row in result['items'])
    assert all(('model' not in row if row['teacher_model'] is None else row['model'] == row['teacher_model'])
               for row in result['items'])
    assert any(row['teacher_model'] is None for row in result['items'])
    async with real.pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', uuid.UUID(result['ledger_id']))
    assert receipt['tenant_id'] == tenant and receipt['rung'] == 3 and receipt['model'] == 'code'
    assert receipt['cost_usd'] == 0 and receipt['task_type'] == 'skala.teachers'
    async with real.pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.skills(id,version,agent,task_type) VALUES($1,'3.0.0','placeholder',$2)",
                           'placeholder.skill', TASK)
        for version, owner, region in [('2.0.0', foreign, 'us-east'), ('3.0.0', tenant, 'za')]:
            await conn.execute("""INSERT INTO tank.agent_skill_submissions
                (skill_id,version,tenant_id,region,submitted_by_room,package,sha256)
                VALUES($1,$2,$3,$4,'placeholder','{}'::jsonb,'placeholder-sha')""",
                'placeholder.skill', version, owner, region)
    scoped = await real.client.get('/v1/training/teachers', headers=headers, params={'skill_id': 'placeholder.skill'})
    assert scoped.status_code == 200
    assert {row['name'] for row in scoped.json()['items']} == {'1.0.0'}
    other = await real.client.get('/v1/training/teachers', params={'skill_id': 'placeholder.skill'},
        headers=real.native_headers('placeholder-founder', foreign))
    assert other.status_code == 200 and {row['name'] for row in other.json()['items']} == {'1.0.0', '2.0.0'}
    assert 'placeholder-teacher-1' not in other.text and 'placeholder-teacher-2' not in other.text
    denied = await real.client.get('/v1/training/teachers', params={'skill_id': 'placeholder.skill'},
        headers={**real.native_headers('placeholder-reviewer', tenant, 'reviewer'), 'X-Tervory-Role': 'reviewer'})
    assert denied.status_code == 404
    with pytest.raises(ValueError):
        TeachersArgs(skill_id='placeholder.skill', tenant_id=str(foreign))
    async def unexpected(*args, **kwargs):
        pytest.fail('an explicit teachers read must not invoke a model planner')
    monkeypatch.setattr(serving.tank, 'run_route', unexpected)
    actor = command.Actor(tenant, 'placeholder-founder', True, frozenset(command.SQUADS))
    answer = await command.route_turn(actor, [{'role': 'user', 'content': 'skala.teachers placeholder.skill'}])
    assert json.loads(answer.content) == {'text': '', 'actions': [
        {'tool': 'skala.teachers', 'arguments': {'skill_id': 'placeholder.skill'}}]}
    assert 'skala.teachers' in command.FOUNDER_TOOLS
    assert 'skala.teachers' not in command.CONFIRMED and not command.ADAPTERS['skala.teachers'].paid
    assert 'skala.teachers' not in command.allowed_tools(command.Actor(tenant, 'placeholder-member', False, frozenset(command.SQUADS)))


@pytest.mark.asyncio
async def test_served_annotation_failure_keeps_delivered_answer(serving, monkeypatch, caplog):
    await promote(serving)
    async def failed(*args, **kwargs):
        raise RuntimeError('placeholder-private-update-error')
    monkeypatch.setattr(routing, 'record_served', failed)
    answer = await request(serving)
    assert answer['model'] in {WEAK, STRONG}
    assert 'RuntimeError' in caplog.text
    assert 'placeholder-private-update-error' not in caplog.text
    async with serving.real.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', uuid.UUID(answer['ledger_id']))
    assert row['outcome'] == 'delivered' and row['model'] == answer['model']
