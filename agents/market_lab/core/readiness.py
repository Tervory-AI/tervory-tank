"""Setting names only; unavailable capabilities never start background work."""
from contextlib import asynccontextmanager
import os

from starlette.responses import JSONResponse
from fastapi import Header, HTTPException
import hmac
import asyncio
import logging

from feeds.keys import KEY_NAMES

REQUIRED = ('DATABASE_URL', 'TANK_KEY')
UPLOADS = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_MARKET_LAB', 'R2_SECRET_ACCESS_KEY_MARKET_LAB')
MAIL = ('MARKET_LAB_SMTP_HOST', 'MARKET_LAB_SMTP_FROM', 'MARKET_LAB_SMTP_ALERT_ADDRESSES')


def missing(names, environ=None):
    env = os.environ if environ is None else environ
    return [name for name in names if not env.get(name, '').strip()]


def status():
    return {'missing_settings': missing(REQUIRED), 'features': {
        'uploads': missing(UPLOADS), 'email': missing(MAIL), 'feeds': missing(KEY_NAMES)}}


def install(app):
    original = app.router.lifespan_context
    app.router.routes[:] = [route for route in app.router.routes
                           if getattr(route, 'path', '') not in {'/docs', '/redoc', '/docs/oauth2-redirect', '/openapi.json'}]

    @asynccontextmanager
    async def lifespan(application):
        application.state.configuration_checked = True
        if missing(REQUIRED):
            # Serve diagnostics without creating a pool, worker, scheduler or client.
            yield
        else:
            async with original(application):
                yield

    app.router.lifespan_context = lifespan

    @app.middleware('http')
    async def settings_guard(request, call_next):
        if getattr(app.state, 'configuration_checked', False):
            needed = missing(REQUIRED)
            if request.url.path.startswith('/market/files/'):
                needed += missing(UPLOADS)
            if needed:
                return JSONResponse({'ok': False, 'missing_settings': needed,
                                     'detail': 'Missing settings: ' + ', '.join(needed)}, status_code=503)
        if request.url.path.startswith(('/jobs', '/files', '/storage')):
            key = os.environ.get('TANK_KEY', '')
            supplied = request.headers.get('x-tank-key', '')
            if not key or not hmac.compare_digest(key.encode(), supplied.encode()):
                return JSONResponse({'detail': 'Room key required'}, status_code=401)
        try:
            async with asyncio.timeout(210):
                response = await call_next(request)
                if request.url.path != '/health':
                    response.headers['Cache-Control'] = 'private, no-store'
                return response
        except Exception as exc:
            logging.getLogger('agent').warning('Market Lab request unavailable (%s)', type(exc).__name__)
            return JSONResponse({'detail': 'Market Lab could not read its stored sources. Try again shortly.'}, status_code=503)

    @app.get('/market/settings')
    async def settings(x_tank_key: str = Header(default='')):
        # Names and availability only, never a value or customer record.
        key = os.environ.get('TANK_KEY', '')
        if not key or not hmac.compare_digest(key.encode(), x_tank_key.encode()):
            raise HTTPException(401, 'Room key required')
        return status()
