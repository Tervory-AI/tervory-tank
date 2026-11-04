import copy
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROVISION = runpy.run_path(str(ROOT / 'ops/trigger-signin/provision.py'))
FIRST = '00000000-0000-4000-8000-000000000011'
SECOND = '00000000-0000-4000-8000-000000000012'


class Reply:
    is_success = True

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


class Tank:
    def __init__(self):
        self.clients = [FIRST]
        self.regions = {}

    def request(self, method, path, **kwargs):
        if path == '/v1/case-studies/clients':
            assert method == 'GET'
            offset = kwargs['params']['offset']
            return Reply({'clients': [{'tenant_id': tenant} for tenant in self.clients[offset:offset + 500]], 'has_more': False})
        assert path == '/v1/trigger-signin/config'
        if method == 'GET':
            return Reply({'regions': copy.deepcopy(self.regions)})
        assert method == 'PUT'
        body = kwargs['json']
        self.regions[body['region']] = {**body, 'founders': [body['founder_subject']],
                                      'organisations': {binding['org_id']: binding['tenant_id'] for binding in body['organisations']}}
        return Reply({'configured': True})


class Native:
    def __init__(self):
        self.organisations = {}
        self.grants = {}
        self.assignments = {}
        self.writes = []
        self.lose_org_response = False

    def search(self, path, name):
        assert path == '/admin/v1/orgs/_search'
        org = self.organisations.get(name)
        return {'id': org} if org else None

    def request(self, method, path, **kwargs):
        body = kwargs.get('json', {})
        org = kwargs.get('headers', {}).get('x-zitadel-orgid')
        if method in {'POST', 'PUT'} and not path.endswith('/_search'):
            self.writes.append((method, path))
        if path == '/admin/v1/members/_search':
            return {'result': [{'userId': '50001', 'roles': ['IAM_OWNER']}, {'userId': '50002', 'roles': ['IAM_OWNER']}]}
        if path.startswith('/management/v1/users/5000') and method == 'GET':
            subject = path.rsplit('/', 1)[-1]
            return {'user': {'id': subject, 'details': {'resourceOwner': '10001'},
                             **({'human': {'email': {'email': 'display-only@example.test'}}} if subject == '50001' else {'machine': {}})}}
        if path == '/management/v1/orgs':
            ident = str(60001 + len(self.organisations))
            self.organisations[body['name']] = ident
            if self.lose_org_response:
                self.lose_org_response = False
                raise PROVISION['ProvisionError']('Synthetic response lost')
            return {'id': ident}
        if path.endswith('/grants/_search') and '/projects/' in path:
            target = body['queries'][0]['grantedOrgIdQuery']['grantedOrgId']
            return {'result': [self.grants[target]] if target in self.grants else []}
        if path == '/management/v1/projects/20001/grants':
            ident = str(70001 + len(self.grants))
            self.grants[body['grantedOrgId']] = {'id': ident, 'roleKeys': body['roleKeys']}
            return {'grantId': ident}
        if path == '/management/v1/users/grants/_search':
            assert body['queries'] == [{'projectIdQuery': {'projectId': '20001'}}, {'userIdQuery': {'userId': '50001'}}]
            return {'result': [self.assignments[org]] if org in self.assignments else []}
        if path == '/management/v1/users/50001/grants':
            assert body['roleKeys'] == ['org_admin']
            assert 'email' not in body
            self.assignments[org] = {'id': '80001', 'roleKeys': body['roleKeys'], 'details': {'resourceOwner': org}}
            return {'userGrantId': '80001'}
        raise AssertionError((method, path, kwargs))


def configure(api, tank):
    record = {'owner_org_id': '10001', 'project_id': '20001', 'client_id': '30001@tervory', 'workspace_client_id': '30002@tervory'}
    return PROVISION['provision'](api, tank, record, 'us-east', 'https://auth.tervory.com')


def test_setup_redeploy_is_idempotent_and_new_tenant_is_next_run_only():
    api, tank = Native(), Tank()
    first = configure(api, tank)
    writes = list(api.writes)
    assert first['founder_subject'] == '50001'
    assert first['organisations'] == [{'org_id': '60001', 'tenant_id': FIRST}]
    assert configure(api, tank) == first
    assert api.writes == writes
    tank.clients.append(SECOND)
    result = configure(api, tank)
    assert len(result['organisations']) == len(api.organisations) == 2
    assert result['organisations'][0] == first['organisations'][0]
    assert len(api.writes) == len(writes) + 3


def test_setup_recovers_created_org_without_response_and_never_relinks_email():
    api, tank = Native(), Tank()
    api.lose_org_response = True
    with pytest.raises(PROVISION['ProvisionError'], match='response lost'):
        configure(api, tank)
    assert configure(api, tank)['founder_subject'] == '50001'
    assert len(api.organisations) == 1
    api.assignments['60001']['roleKeys'] = ['member']
    before = list(api.writes)
    with pytest.raises(PROVISION['ProvisionError'], match='grant was changed'):
        configure(api, tank)
    assert api.writes == before


def test_workspace_publication_only_links_tenants_already_on_destination():
    payload = configure(Native(), Tank())
    destination = Tank()
    destination.clients = [SECOND]
    PROVISION['publish_workspace'](destination, payload)
    assert destination.regions['us-east']['organisations'] == {}
    assert destination.regions['us-east']['founders'] == ['50001']
