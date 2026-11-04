import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt

import identity_oidc as oidc

CLIENT = '123@tervory'
ORG = '10001'
SUB = '20001'


def set_founders(monkeypatch, subjects):
    from contextvars import ContextVar
    import trigger_signin_config as registry
    region = 'us-east'
    issuer = registry.ISSUERS[region]
    record = {**registry._records.get(region, {}), 'issuer': issuer,
              'founders': [subject.strip() for subject in subjects.split(',') if subject.strip()]}
    monkeypatch.setattr(registry, '_records', {**registry._records, region: record})
    monkeypatch.setattr(registry, '_issuer', ContextVar('offline_verified_issuer', default=issuer))
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', subjects)
    async def refresh(**kwargs):
        return None
    monkeypatch.setattr(registry, 'refresh', refresh)


def install_registry(monkeypatch, providers, bindings, *, workspace_client=None):
    import trigger_signin_config as registry
    records = {'us-east': {'region': 'us-east', 'issuer': provider.issuer, 'client_id': CLIENT,
               'workspace_client_id': workspace_client or CLIENT, 'project_id': '30001',
               'organisations': dict(bindings), 'founders': []} for provider in providers}
    monkeypatch.setattr(registry, '_records', records)
    async def refresh(**kwargs):
        return None
    monkeypatch.setattr(registry, 'refresh', refresh)


class Provider:
    def __init__(self, region='za'):
        self.region = region
        self.issuer = oidc.ISSUERS[region]
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = 'first-key'
        self.keys = [self.jwk()]
        self.calls = []
        self.claims = {'iss': self.issuer, 'aud': CLIENT, 'sub': SUB, 'exp': int(time.time()) + 600,
                       'iat': int(time.time()), oidc.ORG_CLAIM: ORG,
                       oidc.ROLES_CLAIM: {'org_admin': {ORG: 'tervory'}}}

    def jwk(self):
        return {**jwt.algorithms.RSAAlgorithm.to_jwk(self.private.public_key(), as_dict=True),
                'kid': self.kid, 'alg': 'RS256', 'use': 'sig'}

    def token(self, **claims):
        return jwt.encode({**self.claims, **claims}, self.private, algorithm='RS256', headers={'kid': self.kid})

    def __call__(self, request):
        assert request.url.host == urlsplit(self.issuer).hostname
        self.calls.append((request.method, request.url.path))
        if request.url.path == '/.well-known/openid-configuration':
            return httpx.Response(200, json={'issuer': self.issuer, 'jwks_uri': self.issuer + '/keys',
                'token_endpoint': self.issuer + '/oauth/v2/token',
                'device_authorization_endpoint': self.issuer + '/oauth/v2/device_authorization'})
        if request.url.path == '/keys':
            return httpx.Response(200, json={'keys': self.keys})
        form = parse_qs(request.content.decode())
        assert request.method == 'POST' and form['client_id'] == [CLIENT]
        if request.url.path == '/oauth/v2/device_authorization':
            assert form['scope'] == [oidc.SCOPE]
            return httpx.Response(200, json={'device_code': 'synthetic-provider-code', 'user_code': '1234-5678',
                'verification_uri': self.issuer + '/ui/v2/login/device',
                'verification_uri_complete': self.issuer + '/ui/v2/login/device?user_code=1234-5678',
                'expires_in': 600, 'interval': 5})
        assert request.url.path == '/oauth/v2/token'
        assert form['device_code'] == ['synthetic-provider-code']
        assert form['grant_type'] == ['urn:ietf:params:oauth:grant-type:device_code']
        return httpx.Response(200, json={'id_token': self.token(), 'access_token': 'unused-synthetic-upstream-token'})
