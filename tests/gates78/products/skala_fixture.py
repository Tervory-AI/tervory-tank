"""Skala's real ASGI path, local signed issuer, actual receipts and shared Hermes.

The only network substitutes are the signed test issuer, Hermes ASGI transport,
and the paid provider's HTTP response. No replacement auth, route or memory.
"""
import json
import os
import asyncpg
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest_asyncio

from trigger_signin_fakes import Provider, install_registry

USER_A = 'placeholder-skala-owner'
USER_B = 'placeholder-skala-other-user'
ORG_A = '10001'  # Existing issuer protocol requires numeric organisation IDs.
ORG_B = '10002'
WORKSPACE_KEY = 'placeholder-skala-workspace-key'
MODEL = 'placeholder-skala-model'
SKILL = 'tier0.summarize'
VERSION = '1.0.1'
TEXT = 'placeholder company report: orders grew and the next review is scheduled.'


class SkalaEntry:
    def __init__(self, stack, runtime, issuer, client, provider_calls, events):
        self.stack, self.runtime, self.issuer, self.client = stack, runtime, issuer, client
        self.provider_calls, self.events = provider_calls, events

    def headers(self, user=USER_A, tenant=None):
        return {'X-Tank-Key': WORKSPACE_KEY, **self.issuer.workspace_headers(user, tenant or self.stack.tenant)}

    async def run(self, text=TEXT, *, user=USER_A, tenant=None, headers=None, run_id=None, skill=SKILL, version=VERSION, extra=None, preview=False):
        body={'tenant_id':tenant or self.stack.tenant,'paid_run_id':str(run_id or uuid.uuid4()),
              'version':version,'preview':preview,'input':{'text':text, **(extra or {})}}
        return await self.client.post('/v1/skala/'+skill+'/run',json=body,
                                      headers=self.headers(user,tenant) if headers is None else headers)

    async def control(self, operation='view', *, user=USER_A, tenant=None, memory_id=None, text=None, headers=None):
        body={'tenant_id':tenant or self.stack.tenant,'user_id':user}
        if memory_id: body['memory_id']=memory_id
        if text is not None: body['text']=text
        path='/v1/skala/memory'+('' if operation=='view' else '/'+operation)
        headers=self.headers(user,tenant) if headers is None else headers
        return await self.client.get(path,params=body,headers=headers) if operation=='view' else await self.client.post(path,json=body,headers=headers)

    async def ledger(self, tenant=None):
        return [dict(row) for row in await self.stack.records.pool.fetch(
            'SELECT * FROM tank.ledger WHERE tenant_id=$1 ORDER BY ts,id',uuid.UUID(tenant or self.stack.tenant))]

    async def rows(self, tenant=None):
        schema=self.stack.records.schema('skala')
        return [dict(row) for row in await self.stack.records.pool.fetch(
            f'SELECT * FROM {schema}.memory_records WHERE tenant_id=$1 ORDER BY created_at,id',uuid.UUID(tenant or self.stack.tenant))]


@pytest_asyncio.fixture
async def skala_entry(gate78_memory, monkeypatch):
    import main
    import paid_steps
    import engine_ladder
    import skala
    import identity_oidc as oidc
    import trigger_signin_config as registry
    stack=await gate78_memory('skala')
    pool=stack.records.pool
    async with pool.acquire() as conn:
        await conn.execute((Path(__file__).resolve().parents[3]/'tank/schema.sql').read_text())
        for tenant in (stack.tenant,stack.other_tenant,str(skala.PLATFORM_TENANT)):
            await conn.execute("INSERT INTO tank.tenants(tenant_id,home_region,onboarded_by) VALUES($1,'us-east','placeholder-fixture') ON CONFLICT DO NOTHING",uuid.UUID(tenant))
            for task in ('tier0.answer','tier0.summarize','route.request'):
                await conn.execute("""INSERT INTO tank.policy(task_type,tenant_id,model,rung,priority,cache_scope)
                    VALUES($1,$2,$3,1,'standard','none') ON CONFLICT DO NOTHING""",task,uuid.UUID(tenant),MODEL)
                for model in engine_ladder.order({'model': MODEL}):
                    step=paid_steps.model_step(task,model)
                    await paid_steps.register(conn,step,'model','model','placeholder-fixture',task=task,model=model)
                    await conn.execute("""INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by)
                        VALUES($1,$2,'auto','placeholder-admin') ON CONFLICT(tenant_id,step_id) DO UPDATE SET mode='auto'""",uuid.UUID(tenant),step)
        packages=skala.load_packages()
        for ident,version in ((SKILL,VERSION),('tier0.classify','1.0.0')):
            pkg=packages[ident,version]
            await conn.execute("""INSERT INTO tank.skills(id,version,agent,state,approved_at)
                VALUES($1,$2,$3,'approved',now()) ON CONFLICT(id,version) DO UPDATE SET state='approved'""",ident,version,pkg.agent)
    monkeypatch.setattr(main,'_packages',packages)
    monkeypatch.setattr(main,'TANK_API_KEY',WORKSPACE_KEY)
    monkeypatch.setattr(main,'LITELLM_URL','http://placeholder-litellm')
    monkeypatch.setenv('TANK_API_KEY',WORKSPACE_KEY)
    monkeypatch.setenv('HERMES_URL','http://hermes')
    monkeypatch.setenv('SKALA_MEMORY_ENABLED','true')
    monkeypatch.delenv('SKALA_BRAIN_ENABLED',raising=False)
    issuer=Provider('us-east')
    install_registry(monkeypatch,[issuer],{ORG_A:stack.tenant,ORG_B:stack.other_tenant})
    monkeypatch.setattr(oidc,'http_client',lambda:httpx.AsyncClient(transport=httpx.MockTransport(issuer)))
    oidc._cache.clear()
    # Real middleware verifies issuer signatures and binds the actual request state.
    assert any(m.cls.__name__=='TriggerSigninMiddleware' for m in main.app.user_middleware)
    registry._records['us-east']['founders']=[USER_A,USER_B]
    calls,events=[],[]
    context=SimpleNamespace(outage=None, status=503, mutate=None, captured=[], statuses=[])
    async def edge(request):
        if request.url.host=='hermes':
            events.append(('hermes',request.method,request.url.path))
            if request.url.path in {'/memories','/recall','/records'} or request.url.path.startswith('/memories/'):
                context.captured.append((request.method,request.url.raw_path.decode(),dict(request.headers),bytes(request.content)))
                if context.mutate:
                    context.mutate(request)
            if context.outage and context.outage==(request.method,request.url.path):
                context.statuses.append(context.status)
                return httpx.Response(context.status,json={'detail':'placeholder memory refusal'})
            response=await stack.http.send(request)
            context.statuses.append(response.status_code)
            return response
        if request.url.host=='placeholder-litellm' and request.url.path in {'/model/info','/router/settings'}:
            return httpx.Response(503,json={'detail':'placeholder offline metadata; use shipped roster'})
        if request.url.host=='placeholder-litellm' and request.url.path=='/v1/chat/completions':
            calls.append(json.loads(request.content))
            events.append(('provider','POST',request.url.path))
            return httpx.Response(200,headers={'x-litellm-response-cost':'0.05'},json={
                'id':'placeholder-completion','model':calls[-1]['model'],
                'choices':[{'message':{'content':'placeholder summary'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':10,'completion_tokens':3,'total_tokens':13}})
        raise AssertionError('Unexpected external call: '+request.url.host+request.url.path)
    # Shared HTTP is the actual Tank provider boundary. A new dedicated Hermes
    # client must use this boundary too; absence is a runtime integration blocker.
    original_init = httpx.AsyncClient.__init__
    def init_http(self, *args, **kwargs):
        kwargs.setdefault('transport',httpx.MockTransport(edge))
        original_init(self,*args,**kwargs)
    monkeypatch.setattr(httpx.AsyncClient,'__init__',init_http)
    from paid_http import Client
    # Evaluation serialization holds one connection while its route needs another.
    async with asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'],min_size=1,max_size=4,
                                   statement_cache_size=0,ssl=False) as runtime_pool, Client(transport=httpx.MockTransport(edge)) as outbound:
        monkeypatch.setattr(main,'_pool',runtime_pool)
        monkeypatch.setattr(main,'_http',outbound)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://placeholder-tank') as client:
            entry=SkalaEntry(stack,main,issuer,client,calls,events)
            entry.network=context
            yield entry
