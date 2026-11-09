"""Verified personal research; cache authority never comes from client input."""
from __future__ import annotations

import base64
import json
import os
from uuid import UUID

from fastapi import HTTPException


def memory_enabled():
    return os.environ.get('MARKET_LAB_MEMORY_ENABLED', '').lower() in {'true', '1', 'on', 'yes'}


async def verified_actor(request, tenant=None, *, required=False):
    from chassis.user_assertion import HEADER, signed_user
    token = request.headers.get(HEADER, '')
    if not token and not required:
        return None
    if tenant is None:
        try:
            if len(token) > 8192:
                raise ValueError
            encoded = token.split('.')[0]
            # Routing candidate only. signed_user verifies signature, audience,
            # body, target, expiry and durable nonce before this becomes identity.
            tenant = str(UUID(json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))['tenant_id']))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(401, 'Signed user required for memory') from None
    actor = await signed_user(request, tenant_id=str(tenant), product='market_lab', required=required)
    if token and actor is None:
        raise HTTPException(401, 'Signed user required for memory')
    if actor is not None:
        if request.headers.get('X-Tervory-Tenant',actor.tenant_id) != actor.tenant_id or request.headers.get('X-Tervory-User',actor.user_id) != actor.user_id:
            raise HTTPException(401,'Signed user required for memory')
    return actor


async def research_result(memory, tenant, user, question, *, paid_run_id=None, on_result=None, actor=None, tank_client=None):
    from core.research_adapter import research_web
    if not (memory_enabled() and user and memory is not None):
        result = await research_web(tenant, question, **({'paid_run_id': paid_run_id} if paid_run_id else {}))
        if result and result.get('facts') and on_result:
            result = await on_result(result)
        # None is returned only for an explicit pre-send refusal or absent
        # configuration. No provider attempt means a known zero actual cost;
        # failures after dispatch still propagate and cannot become free runs.
        return result if result is not None else {'cost_usd': 0, 'status': 'unavailable'}
    from market_lab_memory_runtime import research_via_memory
    measured = await research_via_memory(memory, tenant_id=tenant, user_id=user, question=question,
                                          paid_run_id=paid_run_id, persist=True, on_result=on_result, actor=actor, tank_client=tank_client)
    result = dict(measured.get('result') or {})
    for key in ('cost_usd','tokens_in','tokens_out','answered_from_memory','would_have_cost','memory_unavailable','paid_calls'):
        if key in measured:
            result[key] = measured[key]
    if measured.get('answered_from_memory'):
        result['receipts'] = []
    return result


async def ask(request, body, connection, *, engine=None, answer_fn=None):
    from core import answer_cache, savings
    from core.evidence import answer
    answer_fn = answer_fn or answer
    tenant = str(body.tenant_id)
    actor = await verified_actor(request, tenant)
    if actor is not None and body.user_id and body.user_id != actor.user_id:
        raise HTTPException(403, 'Memory scope refused')
    user = actor.user_id if actor else None
    # Tenant-only paid-answer caching is deliberately not consulted. Public
    # stored evidence still follows the original deterministic answer path.
    async with answer_cache.flight(tenant + ':' + (user or ''), body.question, engine):
        async with connection() as ledger:
            # A separate namespace may reuse deterministic public-source facts.
            # Paid/personal answers are never written to or read from this cache.
            namespace = 'public-code-v1:' + str(engine)
            result = await answer_cache.get(ledger, tenant, body.question, namespace) if memory_enabled() else None
            public_hit = result is not None
            if result is None:
                result = await answer_fn(ledger, tenant, body.question, engine=engine)
                public = result.get('facts') and all(str(f.get('href','')).startswith((
                    'https://www.census.gov/', 'https://www.bls.gov/', 'https://api.census.gov/')) for f in result['facts'])
                if public and memory_enabled():
                    await answer_cache.put(ledger, tenant, body.question, namespace, result)
            memory = getattr(ledger, 'memory', None)
        if not result.get('facts'):
            async def persist(researched):
                from core.research_records import save
                async with connection() as ledger:
                    report = await save(ledger, tenant, body.question, researched)
                return {**researched,'report_id':report['id']}
            researched = await research_result(memory, tenant, user, body.question, paid_run_id=body.paid_run_id, on_result=persist, actor=actor, tank_client=getattr(request.app.state,"tank",None))
            if researched.get('facts'):
                result = dict(researched)
            else:
                result = {**result, **{key: value for key,value in researched.items() if key not in {'facts','sources'} and (key != 'content' or researched.get('answered_from_memory'))}}
        cached = public_hit or bool(result.get('answered_from_memory'))
        receipt = await savings.record(connection, tenant, 'ask', {'question': body.question}, result, cached=cached)
        if result.get('would_have_cost') is not None and receipt.get('would_have_cost') is None:
            receipt['would_have_cost'] = result['would_have_cost']
        return {**result, 'run_receipt': receipt, 'cache_hit': cached, 'cost': receipt['cost'],
                'cost_usd': receipt['cost'], 'would_have_cost': receipt['would_have_cost']}


async def job_actor(request, body):
    """Chassis hook: verify original enqueue bytes, never input.user_id."""
    return await verified_actor(request, str(body.tenant_id))


async def persist_job_actor(conn, row, actor):
    if actor is not None:
        await conn.execute('''INSERT INTO agent_market_lab.job_actors(tenant_id,job_id,user_id,role)
            VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING''',UUID(actor.tenant_id),row['id'],actor.user_id,actor.role)


async def job_user(ledger, ctx):
    if not getattr(ctx, 'job_id', None):
        return None
    return await ledger.conn.fetchval('SELECT user_id FROM agent_market_lab.job_actors WHERE tenant_id=$1 AND job_id=$2',
                                      UUID(ctx.tenant_id),UUID(ctx.job_id))


async def stored_job_actor(ledger, ctx):
    """Only verified enqueue rows supply a durable worker actor."""
    from chassis.user_assertion import SignedUser
    if not getattr(ctx, 'job_id', None):
        return None
    row = await ledger.conn.fetchrow('SELECT user_id,role FROM agent_market_lab.job_actors WHERE tenant_id=$1 AND job_id=$2',
                                    UUID(ctx.tenant_id), UUID(ctx.job_id))
    return SignedUser(str(ctx.tenant_id), row['user_id'], row['role']) if row else None
