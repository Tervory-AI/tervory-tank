"""Room startup and operation prerequisites, without exposing setting values."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import os
import hmac
from pathlib import Path
from uuid import UUID

import asyncpg
from fastapi.responses import JSONResponse
from chassis.db import schema_for

try:
    from agents.tisan.storage import durable_root
except ModuleNotFoundError:
    from storage import durable_root

CORE = ('DATABASE_URL', 'TANK_KEY', 'DATA_DIR')
R2 = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TISAN', 'R2_SECRET_ACCESS_KEY_TISAN')
FIGMA = ('FIGMA_TOKEN', 'TISAN_FIGMA_FILES')
COOLIFY = ('TISAN_COOLIFY_URL', 'TISAN_COOLIFY_TOKEN')
CAPABILITIES = {
    'heartbeat': ('HERMES_URL', 'TANK_KEY'),
    'figma_live': FIGMA,
    'build': (*FIGMA, 'TANK_URL', 'TANK_KEY', 'HERMES_URL'),
    'pipeline': (*FIGMA, *COOLIFY, 'TANK_URL', 'TANK_KEY', 'TERVORY_ADMIN_USER_IDS', 'HERMES_URL'),
    'publish': (*COOLIFY, 'TANK_URL', 'TANK_KEY', 'TERVORY_ADMIN_USER_IDS'),
    'promotion': (*COOLIFY, 'TANK_URL', 'TANK_KEY', 'TERVORY_ADMIN_USER_IDS'),
    'archive': ('DATA_DIR', *R2),
    'storage': R2,
    'founder': ('TANK_KEY', 'TERVORY_ADMIN_USER_IDS'),
}


def missing(names):
    return [name for name in dict.fromkeys(names) if not os.environ.get(name, '').strip()]


def blocked(names=(), *, unavailable=()):
    absent = list(dict.fromkeys(names))
    failed = list(unavailable)
    detail = ('Missing settings: ' + ', '.join(absent)) if absent else 'Tisan dependencies are unavailable'
    if failed:
        detail += '; unavailable settings: ' + ', '.join(failed)
    return {'ok': False, 'refused': True, 'detail': detail,
            'missing_settings': absent, 'unavailable_settings': failed}


def job_settings(kind, payload):
    if kind == 'ping':
        return CAPABILITIES['heartbeat'] if payload.get('heartbeat') else ()
    if kind in {'build', 'scaffold'}:
        return CAPABILITIES['build']
    return CAPABILITIES.get(kind, ())


async def saved_figma(ctx, loader):
    """Unversioned jobs read real saved evidence; fixture evals stay separate."""
    try:
        reader = loader('tisan_figma', 'figma.py')
        tenant = str(UUID(str(ctx.tenant_id)))
        if not ctx.input.get('file_key') or not ctx.input.get('node_id'):
            raise ValueError('approved page required')
        file_id = reader.normalise_file_key(ctx.input['file_key'])
        node_id = reader.normalise_node_id(ctx.input['node_id'])
        root = Path(os.environ['DATA_DIR']).resolve()
        path = root / 'readings' / tenant / file_id / (node_id.replace(':', '-') + '.json')
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
            raise ValueError('invalid artifact path')
        reading = json.loads(path.read_text())
        if (reading.get('source') != 'figma' or reading.get('file_key') != file_id
                or reading.get('node', {}).get('id') != node_id):
            raise ValueError('approved page required')
        return {**reading, 'stored': str(path.relative_to(root))}
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        return {'ok': False, 'refused': True, 'detail': 'approved page required'}


async def missing_admin(agent):
    """Inspect the existing RLS marker before chassis opens its worker pools."""
    absent = missing(('CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE'))
    if not absent:
        return []
    connection = await asyncpg.connect(os.environ['DATABASE_URL'], timeout=5)
    try:
        enforced = await connection.fetchval(
            'SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            'WHERE c.relrowsecurity AND n.nspname=$1)', schema_for(agent))
    finally:
        await connection.close()
    return absent if enforced else []


def secure_routes(app):
    @app.middleware('http')
    async def room_boundary(request, call_next):
        if request.url.path in {'/health', '/readiness'}:
            return await call_next(request)
        expected = os.environ.get('TANK_KEY', '')
        keys = request.headers.getlist('x-tank-key')
        supplied = keys[0] if len(keys) == 1 else ''
        if not expected or not supplied or not hmac.compare_digest(expected.encode(), supplied.encode()):
            return JSONResponse({'detail': 'room key required'}, status_code=401)
        # The existing gateway remains the identity provider. Bind any tenant
        # assertion it forwarded to the UUID the route will actually consume.
        headers = request.headers.getlist('x-tervory-tenant')
        if headers:
            try:
                tenants = {str(UUID(value)) for value in headers}
                claims = list(request.query_params.getlist('tenant_id'))
                if request.method in {'POST', 'PUT', 'PATCH'} and not request.url.path.startswith('/storage/'):
                    try:
                        body = await request.json()
                    except ValueError:
                        body = None
                    if isinstance(body, dict) and body.get('tenant_id') is not None:
                        claims.append(body['tenant_id'])
                if len(tenants) != 1 or any(str(UUID(str(value))) not in tenants for value in claims):
                    return JSONResponse({'detail': 'not found'}, status_code=404)
            except (ValueError, TypeError, AttributeError):
                return JSONResponse({'detail': 'A workspace is required.'}, status_code=422)
        return await call_next(request)


def install(app, loader, *, preflight=None, secure=False):
    prior = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        instance.state.tisan_active = True
        instance.state.tisan_problem = blocked(missing(CORE)) if missing(CORE) else None
        original = dict(instance.state.handlers)
        entered = False
        try:
            if instance.state.tisan_problem is None:
                try:
                    durable_root()
                except (OSError, ValueError):
                    instance.state.tisan_problem = blocked(unavailable=('DATA_DIR',))
            if instance.state.tisan_problem:
                instance.state.pool = None
                logging.getLogger('agent').warning(instance.state.tisan_problem['detail'])
                yield
                return

            for kind, handler in original.items():
                async def guarded(ctx, _kind=kind, _handler=handler):
                    async def execute(owned):
                        absent = missing((*CORE, *job_settings(_kind, owned.input)))
                        if absent:
                            return blocked(absent)
                        if _kind == 'figma':
                            return await saved_figma(owned, loader)
                        return await _handler(owned)
                    if secure:
                        try:
                            from agents.tisan import savings
                        except ModuleNotFoundError:
                            import savings
                        return await savings.run(execute, ctx, instance.state.pool, _kind, recorder=savings.remote)
                    return await execute(ctx)
                instance.state.handlers[kind] = guarded
            try:
                absent_admin = await (preflight or missing_admin)(instance.state.agent)
                if absent_admin:
                    instance.state.tisan_problem = blocked(absent_admin)
                    instance.state.pool = None
                    logging.getLogger('agent').warning(instance.state.tisan_problem['detail'])
                    entered = True
                    yield
                    return
                async with prior(instance):
                    entered = True
                    yield
            except Exception as exc:
                if entered:
                    raise
                # A missing RLS/admin binding must leave a diagnosable process,
                # with no worker or request able to use a partially opened pool.
                admin = ('CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE')
                rls = isinstance(exc, RuntimeError) and str(exc) in {
                    'RLS requires a non-bypass room role and a separate admin pool',
                    'CHASSIS_ADMIN_DATABASE_URL must use the configured BYPASSRLS role',
                }
                instance.state.tisan_problem = blocked(missing(admin) if rls else (),
                    unavailable=admin if rls else ('DATABASE_URL',))
                instance.state.pool = None
                logging.getLogger('agent').warning('Tisan startup unavailable (%s)', type(exc).__name__)
                yield
        finally:
            instance.state.handlers.update(original)
            instance.state.tisan_active = False

    app.router.lifespan_context = lifespan

    @app.get('/readiness')
    async def readiness():
        problem = getattr(app.state, 'tisan_problem', None) if getattr(app.state, 'tisan_active', False) else None
        absent = missing(CORE)
        return {'ok': not (problem or absent), 'agent': app.state.agent,
                'missing_settings': (problem or {}).get('missing_settings', absent),
                'unavailable_settings': (problem or {}).get('unavailable_settings', []),
                'capabilities': {name: {'ready': not (problem or absent or missing(names)), 'missing_settings': missing(names)}
                                 for name, names in CAPABILITIES.items()}}

    if secure:
        secure_routes(app)

    @app.middleware('http')
    async def prerequisites(request, call_next):
        if not getattr(app.state, 'tisan_active', False) or request.url.path == '/readiness':
            return await call_next(request)
        problem = getattr(app.state, 'tisan_problem', None)
        if problem or missing(CORE):
            return JSONResponse(problem or blocked(missing(CORE)), status_code=503)
        path = request.url.path
        needed = ()
        if path.startswith('/storage/'):
            needed = CAPABILITIES['storage']
        elif path == '/pipeline/start':
            needed = CAPABILITIES['pipeline']
        elif path in {'/publish/build', '/publish/status'}:
            needed = CAPABILITIES['publish']
        elif path in {'/promotion/promote', '/promotion/rollback', '/promotion/status'}:
            needed = CAPABILITIES['promotion']
        elif path.startswith(('/quotes', '/promotion/')) or path in {'/gold/pages', '/gold/approve'}:
            needed = CAPABILITIES['founder']
        elif request.method == 'POST' and path == '/jobs':
            try:
                body = await request.json()
                if isinstance(body, dict):
                    needed = job_settings(body.get('kind', body.get('skill')), body.get('input') or {})
            except (ValueError, TypeError, KeyError, AttributeError):
                pass  # The existing HTTP model still reports malformed input.
        absent = missing(needed)
        if absent:
            return JSONResponse(blocked(absent), status_code=503)
        return await call_next(request)
