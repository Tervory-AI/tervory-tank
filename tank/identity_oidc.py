"""Optional ZA-only Zitadel OIDC client. No provider credentials are persisted/logged."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
import jwt

ISSUER = 'https://auth.za.tervory.com'
ORG_CLAIM = 'urn:zitadel:iam:user:resourceowner:id'
# Zitadel defines this reserved claim as roles for the requesting application's
# own project. Never combine it with project-specific claims from other projects.
ROLES_CLAIM = 'urn:zitadel:iam:org:project:roles'
SCOPE = 'openid urn:zitadel:iam:user:resourceowner urn:zitadel:iam:org:project:role:org_admin'
_cache: dict = {}
_lock = asyncio.Lock()


class IdentityError(ValueError):
    """Fixed refusal; never echo token claims, provider bodies or HTTP exceptions."""


def configured() -> bool:
    from main import box_region
    return box_region() == 'za' and bool(os.environ.get('IDENTITY_ISSUER', '').strip())


def settings() -> tuple[str, str]:
    issuer = os.environ.get('IDENTITY_ISSUER', '').strip()
    client = os.environ.get('IDENTITY_CLIENT_ID', '').strip()
    if issuer != ISSUER or not re.fullmatch(r'[A-Za-z0-9@._-]{1,200}', client):
        raise IdentityError('Identity configuration refused')
    return issuer, client


def endpoint(value: str) -> str:
    if not isinstance(value, str):
        raise IdentityError('Identity endpoint refused')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.netloc != 'auth.za.tervory.com'
            or parsed.username or parsed.password or parsed.fragment):
        raise IdentityError('Identity endpoint refused')
    return value


def http_client():
    return httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False)


async def fetch(method: str, url: str, **kwargs) -> dict:
    try:
        async with http_client() as client:
            response = await client.request(method, endpoint(url), **kwargs)
        if len(response.content) > 262144:
            raise IdentityError('Identity response refused')
        body = response.json()
        if not isinstance(body, dict) or response.is_redirect:
            raise IdentityError('Identity response refused')
        if not response.is_success and not (response.status_code == 400 and isinstance(body.get('error'), str)):
            raise IdentityError('Identity request refused')
        return body
    except (httpx.HTTPError, ValueError, TypeError):
        raise IdentityError('Identity request refused') from None


async def discovery() -> dict:
    issuer, _ = settings()
    async with _lock:
        if _cache.get('issuer') != issuer or _cache.get('expires', 0) <= time.monotonic():
            data = await fetch('GET', issuer + '/.well-known/openid-configuration')
            if data.get('issuer') != issuer:
                raise IdentityError('Identity discovery refused')
            for name in ('device_authorization_endpoint', 'token_endpoint', 'jwks_uri'):
                endpoint(data.get(name))
            _cache.clear()
            _cache.update(issuer=issuer, discovery=data, expires=time.monotonic() + 300)
        return dict(_cache['discovery'])


async def verify(token: str) -> dict:
    issuer, client = settings()
    data = await discovery()
    try:
        if not isinstance(token, str) or len(token) > 16384:
            raise IdentityError('Identity token refused')
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        if header.get('alg') != 'RS256' or not isinstance(kid, str) or not kid or len(kid) > 200:
            raise IdentityError('Identity token refused')
        async with _lock:
            keys = _cache.get('keys', [])
            matches = [key for key in keys if key.get('kid') == kid]
            if not matches:
                # Refresh once on an unknown kid, including the first token.
                jwks = await fetch('GET', data['jwks_uri'])
                keys = jwks.get('keys')
                if not isinstance(keys, list) or len(keys) > 100 or not all(isinstance(k, dict) for k in keys):
                    raise IdentityError('Identity keys refused')
                _cache['keys'] = keys
                matches = [key for key in keys if key.get('kid') == kid]
            if len(matches) != 1:
                raise IdentityError('Identity key refused')
            key = matches[0]
            if key.get('kty') != 'RSA' or key.get('use', 'sig') != 'sig' or key.get('alg', 'RS256') != 'RS256':
                raise IdentityError('Identity key refused')
            public = jwt.PyJWK.from_dict(key, algorithm='RS256').key
        claims = jwt.decode(token, public, algorithms=['RS256'], audience=client, issuer=issuer,
                            options={'require': ['iss', 'aud', 'sub', 'exp', 'iat']})
        aud = claims['aud']
        if isinstance(aud, list) and len(aud) > 1 and claims.get('azp') != client:
            raise IdentityError('Identity audience refused')
        if claims.get('azp', client) != client:
            raise IdentityError('Identity audience refused')
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise IdentityError('Identity token refused') from None


def principal(claims: dict) -> tuple[uuid.UUID, str, bool]:
    try:
        sub, org = claims['sub'], claims[ORG_CLAIM]
        if not isinstance(sub, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', sub):
            raise ValueError
        if not isinstance(org, str) or not re.fullmatch(r'[0-9]{1,30}', org):
            raise ValueError
        bindings = json.loads(os.environ.get('IDENTITY_ORG_TENANTS', '{}'))
        if not isinstance(bindings, dict) or org not in bindings:
            raise ValueError
        tenant = uuid.UUID(bindings[org])
        roles = claims.get(ROLES_CLAIM, {})
        admins = roles.get('org_admin', {}) if isinstance(roles, dict) else {}
        tenant_admin = isinstance(admins, dict) and org in admins
        return tenant, 'zitadel:' + sub, tenant_admin
    except (ValueError, TypeError, KeyError):
        raise IdentityError('Identity organisation refused') from None


async def start() -> dict:
    _, client = settings()
    data = await discovery()
    response = await fetch('POST', data['device_authorization_endpoint'],
                           data={'client_id': client, 'scope': SCOPE})
    endpoint(response.get('verification_uri'))
    if response.get('verification_uri_complete'):
        endpoint(response['verification_uri_complete'])
    if (not isinstance(response.get('device_code'), str) or not 1 <= len(response['device_code']) <= 128
            or not re.fullmatch(r'[A-Z0-9-]{4,40}', str(response.get('user_code', '')))
            or not isinstance(response.get('expires_in'), int) or not 1 <= response['expires_in'] <= 600):
        raise IdentityError('Identity device response refused')
    return response


async def poll(device_code: str) -> dict:
    _, client = settings()
    data = await discovery()
    return await fetch('POST', data['token_endpoint'], data={
        'client_id': client, 'device_code': device_code,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
    })
