"""Keep an unconfigured room available for diagnostics, without starting work."""
from contextlib import asynccontextmanager
import logging
import os
from urllib.parse import urlsplit

import asyncpg
from starlette.responses import JSONResponse

log = logging.getLogger('agent')
STORAGE = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_RADIX', 'R2_SECRET_ACCESS_KEY_RADIX', 'RADIX_EGRESS_PROXY')


def missing_settings(service='room', environ=None):
    env = os.environ if environ is None else environ
    required = ['DATABASE_URL'] + (['TANK_KEY'] if service == 'room' else [])
    prefix = 'CHASSIS' if service == 'room' else 'RADIX_GATEWAY'
    pair = (prefix + '_ADMIN_DATABASE_URL', prefix + '_RLS_ADMIN_ROLE')
    if any(env.get(name, '').strip() for name in pair):
        required.extend(pair)
    missing = [name for name in required if not env.get(name, '').strip()]
    if env.get('DATABASE_URL', '').strip():
        try:
            parsed = urlsplit(env['DATABASE_URL'])
            if parsed.scheme not in {'postgres', 'postgresql'} or not parsed.hostname:
                missing.append('DATABASE_URL')
            elif parsed.hostname not in {'localhost', '127.0.0.1', '::1'} and not parsed.password:
                missing.append('AGENT_DB_PASSWORD_RADIX')
        except ValueError:
            missing.append('DATABASE_URL')
    return sorted(set(missing))


async def database_settings(service):
    """Detect a missing RLS admin binding before the chassis starts any pools."""
    conn = None
    try:
        conn = await asyncpg.connect(os.environ['DATABASE_URL'], timeout=5)
        enforced = await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM pg_class c
          JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='agent_radix' AND c.relrowsecurity)""")
        if enforced:
            prefix = 'CHASSIS' if service == 'room' else 'RADIX_GATEWAY'
            return [name for name in (prefix + '_ADMIN_DATABASE_URL', prefix + '_RLS_ADMIN_ROLE')
                    if not os.environ.get(name, '').strip()]
        return []
    except (OSError, asyncpg.PostgresError, ValueError, TimeoutError):
        return ['DATABASE_URL']
    finally:
        if conn is not None:
            await conn.close()


def install(app, *, service='room'):
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        missing = missing_settings(service)
        if not missing:
            missing = await database_settings(service)
        application.state.missing_settings = missing
        try:
            if missing:
                log.warning('Radix paused; configure settings: %s', ', '.join(missing))
                yield
            else:
                async with inner(application):
                    yield
        finally:
            del application.state.missing_settings

    @app.middleware('http')
    async def configured(request, call_next):
        missing = getattr(app.state, 'missing_settings', [])
        if not missing and request.url.path.startswith('/storage/'):
            missing = [name for name in STORAGE if not os.environ.get(name, '').strip()]
        if missing:
            return JSONResponse({'ok': False, 'status': 'blocked', 'missing_settings': missing,
                                 'detail': 'Configure settings: ' + ', '.join(missing)},
                                status_code=200 if request.url.path == '/health' else 503,
                                headers={'Cache-Control': 'no-store'})
        return await call_next(request)

    app.router.lifespan_context = lifespan
