"""Configure native organisations and publish public resource IDs through Tank APIs."""
from __future__ import annotations

import uuid


class ProvisionError(ValueError):
    pass


def tank_request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if not response.is_success:
        raise ProvisionError('Trigger sign-in Tank configuration refused')
    return response.json()


def tenants(client):
    result = []
    for offset in range(0, 100000, 500):
        page = tank_request(client, 'GET', '/v1/case-studies/clients', params={'offset': offset, 'limit': 500})
        for tenant in page['clients']:
            result.append(str(uuid.UUID(tenant['tenant_id'])))
        if not page['has_more']:
            if len(result) != len(set(result)):
                raise ProvisionError('Trigger sign-in tenant list changed')
            return sorted(result)
    raise ProvisionError('Trigger sign-in tenant list is incomplete')


def initial_founder(api, owner, previous):
    if previous:
        subject = previous['founders'][0]
        user = api.request('GET', '/management/v1/users/' + subject)['user']
        if user.get('human') is None or user['details']['resourceOwner'] != owner:
            raise ProvisionError('Trigger sign-in founder subject refused')
        return subject
    members = api.request('POST', '/admin/v1/members/_search', json={'query': {'limit': 100}})
    if int(members.get('details', {}).get('totalResult', len(members.get('result', [])))) > 100:
        raise ProvisionError('Trigger sign-in bootstrap owners are ambiguous')
    subjects = set()
    for member in members.get('result', []):
        if 'IAM_OWNER' not in member.get('roles', []):
            continue
        user = api.request('GET', '/management/v1/users/' + member['userId'])['user']
        if user.get('human') is not None and user['details']['resourceOwner'] == owner:
            subjects.add(user['id'])
    if len(subjects) != 1:
        raise ProvisionError('Trigger sign-in requires the initial native founder owner')
    return subjects.pop()


def provision(api, tank, record, region, issuer):
    previous = tank_request(tank, 'GET', '/v1/trigger-signin/config')['regions'].get(region)
    subject = initial_founder(api, record['owner_org_id'], previous)
    existing = previous['organisations'] if previous else {}
    by_tenant = {tenant: org for org, tenant in existing.items()}
    project = '/management/v1/projects/' + record['project_id']
    bindings = []
    for tenant in tenants(tank):
        org = by_tenant.get(tenant)
        if not org:
            name = 'Tervory tenant ' + tenant
            found = api.search('/admin/v1/orgs/_search', name)
            org = found['id'] if found else api.request('POST', '/management/v1/orgs', json={'name': name})['id']
        grants = api.request('POST', project + '/grants/_search', json={
            'query': {'limit': 2}, 'queries': [{'grantedOrgIdQuery': {'grantedOrgId': org}}],
        }).get('result', [])
        if len(grants) > 1:
            raise ProvisionError('Trigger sign-in project grant is ambiguous')
        roles = ['org_admin', 'member', 'reviewer']
        if grants:
            grant = grants[0]
            if not set(roles).issubset(grant.get('roleKeys', [])):
                api.request('PUT', project + '/grants/' + grant['id'], json={'roleKeys': sorted(set(roles + grant.get('roleKeys', [])))})
            grant_id = grant['id']
        else:
            grant_id = api.request('POST', project + '/grants', json={'grantedOrgId': org, 'roleKeys': roles})['grantId']
        headers = {'x-zitadel-orgid': org}
        assigned = api.request('POST', '/management/v1/users/grants/_search', headers=headers, json={
            'query': {'limit': 2}, 'queries': [{'projectIdQuery': {'projectId': record['project_id']}}, {'userIdQuery': {'userId': subject}}],
        }).get('result', [])
        if len(assigned) > 1:
            raise ProvisionError('Trigger sign-in founder grant is ambiguous')
        if assigned:
            grant = assigned[0]
            if grant['details']['resourceOwner'] != org:
                raise ProvisionError('Trigger sign-in founder organisation refused')
            if 'org_admin' not in grant.get('roleKeys', []):
                if tenant in by_tenant:
                    raise ProvisionError('Trigger sign-in founder grant was changed')
                api.request('PUT', '/management/v1/users/' + subject + '/grants/' + grant['id'], headers=headers,
                            json={'roleKeys': sorted(set(['org_admin', *grant.get('roleKeys', [])]))})
        else:
            if tenant in by_tenant:
                raise ProvisionError('Trigger sign-in founder grant was removed')
            api.request('POST', '/management/v1/users/' + subject + '/grants', headers=headers,
                        json={'projectId': record['project_id'], 'projectGrantId': grant_id, 'roleKeys': ['org_admin']})
        bindings.append({'org_id': org, 'tenant_id': tenant})
    payload = {key: record[key] for key in ('client_id', 'workspace_client_id', 'project_id')}
    payload.update(region=region, issuer=issuer, founder_subject=subject, organisations=bindings)
    tank_request(tank, 'PUT', '/v1/trigger-signin/config', json=payload)
    return payload


def publish_workspace(tank, payload):
    allowed = set(tenants(tank))
    restricted = {**payload, 'organisations': [binding for binding in payload['organisations'] if binding['tenant_id'] in allowed]}
    tank_request(tank, 'PUT', '/v1/trigger-signin/config', json=restricted)
