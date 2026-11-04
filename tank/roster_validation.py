"""B3/A31: durable, cached eval proof before a roster or serving-policy change."""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import HTTPException
from gold import PLATFORM_TENANT, encoded, input_hash
from tenant_db import tenant_scope

log = logging.getLogger(__name__)
FIELDS = ('model', 'rung', 'system_prompt', 'max_tokens_out')


async def prepare(tank, proposed=None, *, remove=False):
    """Persist the entire eval batch before returning pending; no paid work here."""
    roster = await tank._roster_models(all_deployments=True)
    with tenant_scope(None, administrative=True):
        async with tank.admin_pool().acquire() as conn, conn.transaction():
            await conn.execute('SELECT pg_advisory_xact_lock(73202104)')
            skills = await conn.fetch("""SELECT s.id,s.version,s.task_type,s.rung,a.tenant_id AS owner
                FROM tank.skills s LEFT JOIN tank.agent_skill_submissions a ON a.skill_id=s.id AND a.version=s.version
                WHERE s.state='approved' AND s.present AND (a.region IS NULL OR a.region=$1)
                ORDER BY s.id,s.version""", tank.box_region())
            if skills and not roster:
                raise HTTPException(503, 'The served model roster is unavailable')
            policies = [dict(r) for r in await conn.fetch('SELECT * FROM tank.policy ORDER BY task_type,tenant_id NULLS FIRST')]
            if proposed:
                previous = next((p for p in policies if (p['task_type'], p.get('tenant_id')) ==
                    (proposed['task_type'], proposed.get('tenant_id'))), {})
                proposed = {**previous, **proposed}
                policies = [p for p in policies if (p['task_type'], p['tenant_id']) != (proposed['task_type'], proposed.get('tenant_id'))]
                if not remove:
                    policies.append(proposed)
            jobs, manifest = [], []
            for skill in skills:
                pkg = tank.get_package(skill['id'], skill['version'])
                manifest.append([pkg.id, pkg.version, tank.skala.package_hash(pkg), str(skill['owner'])])
                choices = [p for p in policies if p['task_type'] == pkg.task_type]
                if skill['owner']:
                    own = [p for p in choices if p.get('tenant_id') == skill['owner']]
                    choices = own or [dict(p, tenant_id=skill['owner']) for p in choices if p.get('tenant_id') is None]
                if pkg.task_type and not choices:
                    raise HTTPException(409, 'Approved skill has no evaluation policy: '+pkg.id)
                if not choices:
                    choices = [{'task_type': pkg.id, 'tenant_id': None, 'model': 'skill:'+pkg.ref,
                                    'rung': 3, 'system_prompt': '', 'max_tokens_out': 1024}]
                for policy in choices:
                    config = {key: policy.get(key) for key in FIELDS}
                    config['task_type'] = policy['task_type']
                    config['tenant_id'] = str(policy['tenant_id']) if policy.get('tenant_id') else None
                    jobs.append((pkg, config))
            roster_hash = input_hash(sorted(roster, key=encoded))
            previous = await conn.fetchrow('''SELECT roster_hash,epoch FROM tank.roster_checks
                WHERE tenant_id=$1 AND region=$2 ORDER BY created_at DESC LIMIT 1''', PLATFORM_TENANT, tank.box_region())
            epoch = previous['epoch'] if previous and previous['roster_hash'] == roster_hash else uuid.uuid4()
            signature = input_hash([tank.box_region(), roster_hash, str(epoch), manifest,
                                    sorted([p for _, p in jobs], key=encoded)])
            await conn.execute('''INSERT INTO tank.roster_checks(tenant_id,region,fingerprint,roster_hash,epoch)
                VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING''', PLATFORM_TENANT, tank.box_region(), signature, roster_hash, epoch)
            package_hashes = {(row[0], row[1]): row[2] for row in manifest}
            for pkg, policy in jobs:
                proof_key = input_hash([str(epoch), roster_hash, package_hashes[pkg.id, pkg.version], policy])
                source = await conn.fetchrow("""SELECT id,completed_at,eval_id,error FROM tank.skill_revalidations
                    WHERE tenant_id=$1 AND proof_key=$2 AND source_job_id IS NULL LIMIT 1 FOR SHARE""", PLATFORM_TENANT, proof_key)
                await conn.execute('''INSERT INTO tank.skill_revalidations
                    (tenant_id,policy_tenant_id,task_type,old_model,model,policy,skill_id,version,preflight_hash,
                     proof_key,source_job_id,completed_at,eval_id,error)
                    VALUES($1,$2,$3,$4,$4,$5::jsonb,$6,$7,$8,$9,$10,$11,$12,$13) ON CONFLICT DO NOTHING''',
                    PLATFORM_TENANT, policy['tenant_id'], policy['task_type'], policy['model'],
                    encoded(policy), pkg.id, pkg.version, signature, proof_key,
                    source['id'] if source else None, source['completed_at'] if source else None,
                    source['eval_id'] if source else None, source['error'] if source else None)
            result = await conn.fetchrow('''SELECT count(*) FILTER(WHERE completed_at IS NULL) AS pending,
                count(*) FILTER(WHERE error IS NOT NULL) AS failed FROM tank.skill_revalidations
                WHERE tenant_id=$1 AND preflight_hash=$2''', PLATFORM_TENANT, signature)
            if proposed is None:
                await conn.execute('''INSERT INTO tank.roster_heads(tenant_id,region,fingerprint,roster_hash,unavailable)
                    VALUES($1,$2,$3,$4,false) ON CONFLICT(tenant_id,region) DO UPDATE
                    SET fingerprint=EXCLUDED.fingerprint,roster_hash=EXCLUDED.roster_hash,unavailable=false''',
                    PLATFORM_TENANT, tank.box_region(), signature, roster_hash)
            return {'fingerprint': signature, 'pending': result['pending'], 'failed': result['failed']}


async def ensure(tank, proposed=None, *, remove=False):
    try:
        result = await prepare(tank, proposed, remove=remove)
    except HTTPException as exc:
        if exc.status_code == 503:
            await mark_unavailable(tank)
        raise
    if result['pending'] or result['failed']:
        raise HTTPException(409, {'code': 'models_validation_required', **result})
    return result


async def mark_unavailable(tank):
    with tenant_scope(None, administrative=True):
        async with tank.admin_pool().acquire() as conn:
            await conn.execute("""INSERT INTO tank.roster_heads(tenant_id,region,fingerprint,roster_hash,unavailable)
                VALUES($1,$2,'unavailable','unavailable',true) ON CONFLICT(tenant_id,region)
                DO UPDATE SET unavailable=true""", PLATFORM_TENANT, tank.box_region())


def install(app, tank):
    import asyncpg
    from fastapi.responses import JSONResponse

    @app.exception_handler(asyncpg.PostgresError)
    async def policy_barrier_error(_request, exc):
        if exc.sqlstate == 'P0409':
            return JSONResponse(status_code=409, content={'detail': 'models_validation_required'})
        log.error('Database operation: %s', type(exc).__name__)
        return JSONResponse(status_code=500, content={'detail': 'database operation failed'})

    task = None

    async def work():
        while True:
            try:
                await prepare(tank)
            except Exception as exc:  # noqa: BLE001 -- retain the previous barrier if the roster is unavailable
                await mark_unavailable(tank)
                log.warning('Roster observation: %s', type(exc).__name__)
            await asyncio.sleep(60)

    @app.on_event('startup')
    async def start():
        nonlocal task
        with tenant_scope(None, administrative=True):
            # Establish the barrier before accepting any policy mutation.
            try:
                await prepare(tank)
            except Exception as exc:  # noqa: BLE001 -- keep free paths available, with policy writes held
                await mark_unavailable(tank)
                log.warning('Roster startup: %s', type(exc).__name__)
            task = asyncio.create_task(work())

    async def stop():
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app.router.on_shutdown.insert(0, stop)
