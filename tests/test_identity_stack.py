"""No external network: upstream-API setup idempotency and deployment contract."""
import json
from pathlib import Path
import re
import runpy

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SETUP = runpy.run_path(str(ROOT / 'ops/trigger-signin/setup.py'))


@pytest.mark.parametrize('omit_defaults', [False, True])
def test_setup_creates_project_app_roles_policies_once_and_verifies_owner(omit_defaults):
    state = {'project': None, 'roles': [], 'apps': {},
             'login': {'allowRegister': True, 'passwordCheckLifetime': '86400s', 'allowDomainDiscovery': True}, 'lockout': {}, 'writes': []}
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
            assert body['roleKey'] in {'org_admin', 'member', 'reviewer'}
            assert body['displayName'] == body['roleKey']
            state['roles'].append({'key': body['roleKey']})
            result = {}
        elif path.endswith('/apps/_search'):
            app = state['apps'].get(body['queries'][0]['nameQuery']['name'])
            if app and omit_defaults:
                app = {'oidcConfig': {k: v for k, v in app['oidcConfig'].items()
                                      if k != 'version' and not (k == 'appType' and v == 'OIDC_APP_TYPE_WEB')}}
            result = {'result': [app] if app else []}
        elif path.endswith('/apps/oidc'):
            assert body == (SETUP['APP'] if body['name'] == 'Tervory CLI' else SETUP['WORKSPACE_APP'])
            assert body['authMethodType'] == 'OIDC_AUTH_METHOD_TYPE_NONE'
            assert 'OIDC_GRANT_TYPE_AUTHORIZATION_CODE' in body['grantTypes']
            client_id = '30001@tervory' if body['name'] == 'Tervory CLI' else '30002@tervory'
            state['apps'][body['name']] = {'oidcConfig': {**{key: value for key, value in body.items() if key != 'name'}, 'clientId': client_id}}
            result = {'clientId': client_id}
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
                policy = {k: v for k, v in state[name].items() if not omit_defaults or v is not False}
                result = {'policy': policy}
        else:
            pytest.fail(f'Unexpected setup API call: {method} {path}')
        return httpx.Response(200, json=result)
    with httpx.Client(base_url='http://offline', transport=httpx.MockTransport(api)) as client:
        configure = SETUP['Configure'](client)
        first = configure.run()
        assert first == {'client_id': '30001@tervory', 'workspace_client_id': '30002@tervory', 'project_id': '20001', 'owner_org_id': '10001'}
        before = list(state['writes'])
        assert configure.run() == first and state['writes'] == before
        assert state['login']['allowRegister'] is True
        assert state['login']['passwordCheckLifetime'] == '86400s'
        assert state['login']['allowDomainDiscovery'] is True
        assert state['login']['passwordlessType'] == 'PASSWORDLESS_TYPE_ALLOWED'
        assert set(state['login']['secondFactors']) == {'SECOND_FACTOR_TYPE_OTP', 'SECOND_FACTOR_TYPE_U2F'}
        assert state['login']['multiFactors'] == ['MULTI_FACTOR_TYPE_U2F_WITH_VERIFICATION']
        assert state['lockout'] == {'maxPasswordAttempts': '5', 'maxOtpAttempts': '5'}
        # Defaults must not turn a missing native type or authentication mismatch
        # into permission to reuse an incompatible application.
        for app_name, field, replacement in [
            ('Tervory CLI', 'appType', None),
            ('Tervory Workspace', 'appType', 'OIDC_APP_TYPE_NATIVE'),
            ('Tervory Workspace', 'authMethodType', None),
        ]:
            original = dict(state['apps'][app_name]['oidcConfig'])
            if replacement is None:
                state['apps'][app_name]['oidcConfig'].pop(field)
            else:
                state['apps'][app_name]['oidcConfig'][field] = replacement
            with pytest.raises(SETUP['SetupError'], match='configuration differs'):
                configure.run()
            state['apps'][app_name]['oidcConfig'] = original
            assert state['writes'] == before
        state['project']['details']['resourceOwner'] = '99999'
        with pytest.raises(SETUP['SetupError'], match='owner refused'):
            configure.run()


def test_stack_is_isolated_pinned_and_uses_only_existing_proxy():
    text = (ROOT / 'ops/trigger-signin/docker-compose.yml').read_text()
    stack = yaml.safe_load(text)
    services = stack['services']
    for name in ['trigger-signin-init', 'trigger-signin-setup', 'trigger-signin-api']:
        assert re.fullmatch(r'ghcr.io/zitadel/zitadel:v4\.20\.0@sha256:[a-f0-9]{64}', services[name]['image'])
    assert re.fullmatch(r'ghcr.io/zitadel/zitadel-login:v4\.20\.0@sha256:[a-f0-9]{64}', services['trigger-signin-login']['image'])
    assert re.fullmatch(r'postgres:16\.15@sha256:[a-f0-9]{64}', services['identity-postgres']['image'])
    assert stack['volumes']['identity_database']['name'] == 'trigger-signin-us-postgres'
    assert services['identity-postgres']['networks'] == ['database']
    assert stack['networks']['database']['internal'] is True
    assert not any('traefik' in service.get('image', '') for service in services.values())
    assert services['trigger-signin-api']['labels']['traefik.http.services.trigger-signin-api.loadbalancer.server.scheme'] == 'h2c'
    assert services['trigger-signin-init']['command'] == ['init']
    assert services['trigger-signin-setup']['command'] == ['setup', '--masterkeyFromEnv']
    assert services['trigger-signin-api']['command'] == ['start', '--masterkeyFromEnv']
    assert services['trigger-signin-setup']['depends_on']['trigger-signin-init']['condition'] == 'service_completed_successfully'
    env = services['trigger-signin-setup']['environment']
    assert env['ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORDCHANGEREQUIRED'] == 'true'
    # Open sign-up matches setup's login policy; a new account has no tenant access until invited.
    assert env['ZITADEL_DEFAULTINSTANCE_LOGINPOLICY_ALLOWREGISTER'] == 'true'
    assert env['ZITADEL_FIRSTINSTANCE_MACHINEKEYPATH'] == '/bootstrap/machine-key.json'
    assert services['trigger-signin-login']['volumes'] == ['identity_login_token:/login:ro']
    assert 'identity_bootstrap:/bootstrap' in services['tervory-setup']['volumes']
    for name, service in services.items():
        assert 'ports' not in service
        # Only the one-shot setup job sees mail settings; it turns email on and sends the setup email.
        if name != 'tervory-setup':
            assert not any('SMTP' in key for key in service.get('environment', {}))
    assert services['tervory-setup']['environment']['TRIGGER_SIGNIN_SMTP_PASSWORD'].startswith('${TRIGGER_SIGNIN_SMTP_PASSWORD:?')
    assert services['identity-backup']['depends_on'] == {'identity-postgres': {'condition': 'service_healthy'}}
    assert 'TRIGGER_SIGNIN_BOOTSTRAP_KEY_EXPIRATION' in services['tervory-setup']['environment']
    # Existing main backup has no route to this separate private database.
    za = yaml.safe_load((ROOT / 'docker-compose.za.yml').read_text())
    assert za['services']['r2-backup-za']['networks'] == ['default']
    assert stack['networks']['database'].get('external', False) is False
    assert services['identity-backup']['build']['target'] == 'backup'
    assert services['identity-backup']['environment']['TANK_REGION'] == 'us-east'
    assert 'DATABASE_URL' not in services['identity-backup']['environment']
    za = yaml.safe_load((ROOT / 'docker-compose.za.yml').read_text())
    assert 'TRIGGER_SIGNIN_ISSUER' not in za['services']['tank']['environment']
    assert 'TRIGGER_SIGNIN_SETUP_TOKEN' not in za['services']['tank']['environment']
    assert 'TRIGGER_SIGNIN_CONFIG_TOKEN' in za['services']['tank']['environment']


def test_expired_bootstrap_skips_only_successfully_completed_setup(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('TRIGGER_SIGNIN_ISSUER', 'https://auth.tervory.com')
    monkeypatch.setenv('TRIGGER_SIGNIN_BOOTSTRAP_KEY_EXPIRATION', '2000-01-01T00:00:00Z')
    def no_network(*args, **kwargs):
        pytest.fail('Expired completed bootstrap must not authenticate or call an API')
    monkeypatch.setattr(httpx, 'Client', no_network)
    with pytest.raises(SETUP['SetupError'], match='without completed setup'):
        SETUP['main'](tmp_path)
    result = {'client_id': '30001@tervory', 'workspace_client_id': '30002@tervory', 'project_id': '20001', 'owner_org_id': '10001'}
    marker = tmp_path / 'tervory.json'
    marker.write_text(json.dumps(result))
    # No machine-key file exists: even reading/signing it would fail this test.
    with pytest.raises(SETUP['SetupError'], match='credential needs renewal'):
        SETUP['main'](tmp_path)
    output = capsys.readouterr()
    assert output.out == output.err == ''
    assert json.loads(marker.read_text()) == result
    marker.write_text(json.dumps({'client_id': result['client_id']}))
    with pytest.raises(SETUP['SetupError'], match='record refused'):
        SETUP['main'](tmp_path)
    monkeypatch.setenv('TRIGGER_SIGNIN_BOOTSTRAP_KEY_EXPIRATION', '2999-01-01T00:00:00Z')
    assert SETUP['completed_setup'](tmp_path) is None


@pytest.mark.parametrize('host', ['auth.tervory.com'])
def test_setup_accepts_only_global_signin_host(monkeypatch, host):
    monkeypatch.setenv('TRIGGER_SIGNIN_ISSUER', 'https://' + host)
    assert SETUP['issuer_settings']() == ('https://' + host, host)
    monkeypatch.setenv('TRIGGER_SIGNIN_ISSUER', 'https://trigger.tervory.com')
    with pytest.raises(SETUP['SetupError']):
        SETUP['issuer_settings']()


def test_only_successful_asset_upload_accepts_empty_response():
    def uploaded(request):
        return httpx.Response(200)
    with httpx.Client(base_url='http://offline', transport=httpx.MockTransport(uploaded)) as client:
        api = SETUP['Configure'](client)
        assert api.request('POST', '/assets/v1/instance/policy/label/logo') == {}
        with pytest.raises(ValueError):
            api.request('GET', '/management/v1/orgs/me')
        with pytest.raises(ValueError):
            api.request('GET', '/assets/v1/instance/policy/label/logo')
    with httpx.Client(base_url='http://offline', transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={'code': 9}))) as client:
        with pytest.raises(SETUP['SetupError']):
            SETUP['Configure'](client).request('POST', '/assets/v1/instance/policy/label/logo')
