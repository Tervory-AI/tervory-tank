"""Configure unmodified Zitadel through its public API; success prints client ID only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import httpx
import jwt

ISSUER = 'https://auth.za.tervory.com'
APP = {
    'name': 'Tervory CLI', 'redirectUris': ['http://127.0.0.1/callback'],
    'responseTypes': ['OIDC_RESPONSE_TYPE_CODE'],
    'grantTypes': ['OIDC_GRANT_TYPE_AUTHORIZATION_CODE', 'OIDC_GRANT_TYPE_DEVICE_CODE'],
    'appType': 'OIDC_APP_TYPE_NATIVE', 'authMethodType': 'OIDC_AUTH_METHOD_TYPE_NONE',
    'version': 'OIDC_VERSION_1_0', 'idTokenRoleAssertion': True, 'idTokenUserinfoAssertion': True,
}
LOGIN = {'allowUsernamePassword': True, 'allowRegister': False, 'allowExternalIdp': False,
         'forceMfa': False, 'passwordlessType': 'PASSWORDLESS_TYPE_ALLOWED'}
LOCKOUT = {'maxPasswordAttempts': '5', 'maxOtpAttempts': '5'}


class SetupError(ValueError):
    pass


class Configure:
    def __init__(self, client):
        self.client = client

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if not response.is_success:
            raise SetupError('Identity setup refused')
        result = response.json()
        if not isinstance(result, dict):
            raise SetupError('Identity setup refused')
        return result

    def search(self, path, name, field='nameQuery'):
        result = self.request('POST', path, json={
            'query': {'limit': 2}, 'queries': [{field: {'name': name, 'method': 'TEXT_QUERY_METHOD_EQUALS'}}],
        }).get('result', [])
        if not isinstance(result, list) or len(result) > 1:
            raise SetupError('Identity setup found ambiguous resources')
        return result[0] if result else None

    def run(self):
        org = self.request('GET', '/management/v1/orgs/me')['org']['id']
        project = self.search('/management/v1/projects/_search', 'Tervory')
        if project:
            if project.get('details', {}).get('resourceOwner') != org:
                raise SetupError('Tervory project owner refused')
            project_id = project['id']
        else:
            project_id = self.request('POST', '/management/v1/projects', json={
                'name': 'Tervory', 'projectRoleAssertion': True,
                'projectRoleCheck': False, 'hasProjectCheck': False,
            })['id']
        root = '/management/v1/projects/' + project_id
        roles = self.request('POST', root + '/roles/_search', json={}).get('result', [])
        if not any(r.get('key') == 'org_admin' for r in roles):
            self.request('POST', root + '/roles', json={'roleKey': 'org_admin', 'displayName': 'org_admin'})
        app = self.search(root + '/apps/_search', APP['name'])
        if app:
            config = app.get('oidcConfig', {})
            if any(config.get(k) != v for k, v in APP.items() if k != 'name'):
                raise SetupError('Existing CLI application configuration differs')
            client_id = config['clientId']
        else:
            client_id = self.request('POST', root + '/apps/oidc', json=APP)['clientId']
        for name, desired in [('login', LOGIN), ('lockout', LOCKOUT)]:
            path = '/admin/v1/policies/' + name
            current = self.request('GET', path).get('policy', {})
            if any(current.get(k) != v for k, v in desired.items()):
                self.request('PUT', path, json=desired)
        # Bootstrap volume contains resource identifiers only in this file.
        return {'client_id': client_id, 'project_id': project_id, 'owner_org_id': org}


def main():
    os.umask(0o077)
    key_path = Path('/bootstrap/machine-key.json')
    key_path.chmod(0o600)
    key = json.loads(key_path.read_text())
    now = int(time.time())
    assertion = jwt.encode({'iss': key['userId'], 'sub': key['userId'], 'aud': ISSUER,
                            'iat': now, 'exp': now + 60}, key['key'], algorithm='RS256',
                           headers={'kid': key['keyId']})
    with httpx.Client(base_url='http://zitadel-api:8080', headers={'Host': 'auth.za.tervory.com'},
                      timeout=30, trust_env=False, follow_redirects=False) as client:
        response = client.post('/oauth/v2/token', data={
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion,
            'scope': 'openid urn:zitadel:iam:org:project:id:zitadel:aud',
        })
        if not response.is_success:
            raise SetupError('Bootstrap authentication refused')
        client.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
        result = Configure(client).run()
    Path('/bootstrap/tervory.json').write_text(json.dumps(result) + '\n')
    print(result['client_id'])


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Identity setup failed', file=sys.stderr)
        raise SystemExit(1) from None
