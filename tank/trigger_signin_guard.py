"""Verify Workspace user assertions with the shared Trigger sign-in verifier."""
import hmac
import os
import uuid

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.requests import Request
from fastapi import HTTPException

import identity_oidc as oidc
import trigger_signin_config as registry


class TriggerSigninMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        issuer_context = registry._issuer.set('')
        proof_context = registry.proof.set({name: value for name, value in Headers(scope=scope).items()
                                            if name in {'authorization', 'x-trigger-signin-token', 'x-trigger-signin-org'}})
        try:
            return await self.dispatch(scope, receive, send)
        finally:
            registry._issuer.reset(issuer_context)
            registry.proof.reset(proof_context)

    async def dispatch(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        from main import TANK_API_KEY
        keys = [TANK_API_KEY, *(os.environ.get(name, '') for name in (
            'TANK_HOMES_KEY', 'TRIGGER_SIGNIN_SESSIONS_KEY', 'TANK_CONTENT_API_KEY_US', 'TANK_CONTENT_API_KEY_ZA', 'TANK_KEY_TISAN'))]
        presented = headers.get('x-tank-key', '')
        trusted_service = bool(presented) and any(key and hmac.compare_digest(presented.encode(), key.encode()) for key in keys)
        identity_headers = ['x-tervory-user', 'x-tervory-admin', 'x-tervory-role', 'x-trigger-signin-token']
        if not trusted_service or not any(headers.get(name) for name in identity_headers):
            return await self.app(scope, receive, send)
        token = headers.get('x-trigger-signin-token', '')
        if not token and headers.get('authorization'):
            import personal_tokens
            try:
                actor, _ = await personal_tokens.bearer_identity(Request(scope), audience='cli')
                if any(headers.get(name) and headers[name] != actor.user_id for name in ['x-tervory-user', 'x-tervory-admin']):
                    raise ValueError
                if headers.get('x-tervory-tenant') and uuid.UUID(headers['x-tervory-tenant']) != actor.tenant_id:
                    raise ValueError
                if (headers.get('x-tervory-admin') or headers.get('x-tervory-role') == 'org:admin') and not actor.tenant_admin:
                    raise ValueError
                if headers.get('x-tervory-role', '') not in {'', 'org:admin'}:
                    raise ValueError
            except (HTTPException, ValueError):
                return await JSONResponse({'detail': 'Trigger sign-in required'}, status_code=401,
                                          headers={'Cache-Control': 'no-store'})(scope, receive, send)
            scope.setdefault('state', {})['trigger_signin'] = {'tenant_id': actor.tenant_id, 'user_id': actor.user_id, 'tenant_admin': actor.tenant_admin}
            return await self.app(scope, receive, send)
        try:
            if not token:
                raise oidc.IdentityError('Trigger sign-in required')
            await registry.refresh()
            claims = await oidc.verify(token, workspace=True)
        except oidc.IdentityError:
            return await JSONResponse({'detail': 'Trigger sign-in required'}, status_code=401,
                                      headers={'Cache-Control': 'no-store'})(scope, receive, send)
        try:
            org = headers.get('x-trigger-signin-org') or claims.get(oidc.ORG_CLAIM)
            tenant, subject, administrator = oidc.principal(claims, org_id=org, workspace=True)
            for name in ['x-tervory-user', 'x-tervory-admin']:
                if headers.get(name) and headers[name].strip() != subject:
                    raise ValueError
            if headers.get('x-tervory-tenant') and uuid.UUID(headers['x-tervory-tenant']) != tenant:
                raise ValueError
            if headers.get('x-tervory-admin') and not administrator:
                raise ValueError
            role = headers.get('x-tervory-role', '')
            role_key = 'org_admin' if role == 'org:admin' else role.removeprefix('org:')
            grants = claims.get(oidc.ROLES_CLAIM, {}).get(role_key, {})
            if role and (not isinstance(grants, dict) or org not in grants):
                raise ValueError
        except (oidc.IdentityError, ValueError, TypeError, AttributeError):
            return await JSONResponse({'detail': 'Trigger sign-in context refused'}, status_code=403,
                                      headers={'Cache-Control': 'no-store'})(scope, receive, send)
        scope.setdefault('state', {})['trigger_signin'] = {'tenant_id': tenant, 'user_id': subject, 'tenant_admin': administrator}
        sanitized = [(name, value) for name, value in scope['headers'] if name.lower() != b'x-tervory-role']
        sanitized.append((b'x-tervory-role', b'org:admin' if administrator else role.encode()))
        scope['headers'] = sanitized
        issuer_context = registry._issuer.set(claims['iss'])
        try:
            return await self.app(scope, receive, send)
        finally:
            registry._issuer.reset(issuer_context)
