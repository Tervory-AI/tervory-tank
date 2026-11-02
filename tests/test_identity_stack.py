"""No external network: upstream-API setup idempotency and deployment contract."""
import json
from pathlib import Path
import re
import runpy

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SETUP = runpy.run_path(str(ROOT / 'ops/identity/setup.py'))


def test_setup_creates_project_app_roles_policies_once_and_verifies_owner():
    state = {'project': None, 'roles': [], 'app': None,
             'login': {'allowRegister': True}, 'lockout': {}, 'writes': []}
    def api(request):
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else {}
        if method in {'POST', 'PUT'} and not path.endswith('/_search'):
            state['writes'].append((method, path, body))
        if path == '/management/v1/orgs/me':
            result = {'org': {'id': '10001'}}
        elif path == '/management/v1/projects/_search':
            assert body['queries'] == [{'nameQuery': {'name': 'Tervory', 'method': 'TEXT_QUERY_METHOD_EQUALS'}}]
            result = {'result': [state['project']] if state['project'] else []}
        elif path == '/management/v1/projects':
            assert body == {'name': 'Tervory', 'projectRoleAssertion': True, 'projectRoleCheck': False, 'hasProjectCheck': False}
            state['project'] = {'id': '20001', 'details': {'resourceOwner': '10001'}}
            result = {'id': '20001'}
        elif path.endswith('/roles/_search'):
            result = {'result': state['roles']}
        elif path.endswith('/roles'):
            assert body == {'roleKey': 'org_admin', 'displayName': 'org_admin'}
            state['roles'].append({'key': body['roleKey']})
            result = {}
        elif path.endswith('/apps/_search'):
            result = {'result': [state['app']] if state['app'] else []}
        elif path.endswith('/apps/oidc'):
            assert body == SETUP['APP']
            assert body['authMethodType'] == 'OIDC_AUTH_METHOD_TYPE_NONE'
            assert set(body['grantTypes']) == {'OIDC_GRANT_TYPE_AUTHORIZATION_CODE', 'OIDC_GRANT_TYPE_DEVICE_CODE'}
            state['app'] = {'oidcConfig': {**{k: v for k, v in body.items() if k != 'name'}, 'clientId': '30001@tervory'}}
            result = {'clientId': '30001@tervory'}
        elif '/policies/login/second_factors' in path or '/policies/login/multi_factors' in path:
            field = 'secondFactors' if path.endswith('second_factors') else 'multiFactors'
            state['login'].setdefault(field, []).append(body['type'])
            result = {}
        elif path.startswith('/admin/v1/policies/'):
            name = path.rsplit('/', 1)[1]
            if method == 'PUT':
                state[name].update(body)
                result = {}
            else:
                result = {'policy': state[name]}
        else:
            pytest.fail(f'Unexpected setup API call: {method} {path}')
        return httpx.Response(200, json=result)
    with httpx.Client(base_url='http://offline', transport=httpx.MockTransport(api)) as client:
        configure = SETUP['Configure'](client)
        first = configure.run()
        assert first == {'client_id': '30001@tervory', 'project_id': '20001', 'owner_org_id': '10001'}
        before = list(state['writes'])
        assert configure.run() == first and state['writes'] == before
        assert state['login']['allowRegister'] is False
        assert state['login']['passwordlessType'] == 'PASSWORDLESS_TYPE_ALLOWED'
        assert set(state['login']['secondFactors']) == {'SECOND_FACTOR_TYPE_OTP', 'SECOND_FACTOR_TYPE_U2F'}
        assert state['login']['multiFactors'] == ['MULTI_FACTOR_TYPE_U2F_WITH_VERIFICATION']
        assert state['lockout'] == {'maxPasswordAttempts': '5', 'maxOtpAttempts': '5'}
        state['project']['details']['resourceOwner'] = '99999'
        with pytest.raises(SETUP['SetupError'], match='owner refused'):
            configure.run()


def test_stack_is_isolated_pinned_and_uses_only_existing_proxy():
    text = (ROOT / 'ops/identity/docker-compose.yml').read_text()
    stack = yaml.safe_load(text)
    services = stack['services']
    for name in ['zitadel-init', 'zitadel-setup', 'zitadel-api']:
        assert re.fullmatch(r'ghcr.io/zitadel/zitadel:v4\.20\.0@sha256:[a-f0-9]{64}', services[name]['image'])
    assert re.fullmatch(r'ghcr.io/zitadel/zitadel-login:v4\.20\.0@sha256:[a-f0-9]{64}', services['zitadel-login']['image'])
    assert re.fullmatch(r'postgres:16\.15@sha256:[a-f0-9]{64}', services['identity-postgres']['image'])
    assert stack['volumes']['identity_database']['name'] == 'identity-za-postgres'
    assert services['identity-postgres']['networks'] == ['database']
    assert stack['networks']['database']['internal'] is True
    assert not any('traefik' in service.get('image', '') for service in services.values())
    assert services['zitadel-api']['labels']['traefik.http.services.identity-za-api.loadbalancer.server.scheme'] == 'h2c'
    assert services['zitadel-init']['command'] == ['init']
    assert services['zitadel-setup']['command'] == ['setup', '--masterkeyFromEnv']
    assert services['zitadel-api']['command'] == ['start', '--masterkeyFromEnv']
    assert services['zitadel-setup']['depends_on']['zitadel-init']['condition'] == 'service_completed_successfully'
    env = services['zitadel-setup']['environment']
    assert env['ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORDCHANGEREQUIRED'] == 'true'
    assert env['ZITADEL_DEFAULTINSTANCE_LOGINPOLICY_ALLOWREGISTER'] == 'false'
    assert env['ZITADEL_FIRSTINSTANCE_MACHINEKEYPATH'] == '/bootstrap/machine-key.json'
    assert services['zitadel-login']['volumes'] == ['identity_login_token:/login:ro']
    assert 'identity_bootstrap:/bootstrap' in services['tervory-setup']['volumes']
    for service in services.values():
        assert 'ports' not in service
        assert not any('SMTP' in name for name in service.get('environment', {}))
    assert services['identity-backup']['build']['target'] == 'backup'
    assert services['identity-backup']['environment']['TANK_REGION'] == 'za'
    assert 'DATABASE_URL' not in services['identity-backup']['environment']
    za = yaml.safe_load((ROOT / 'docker-compose.za.yml').read_text())
    assert za['services']['tank']['environment']['IDENTITY_ISSUER'] == '${IDENTITY_ISSUER:-}'
