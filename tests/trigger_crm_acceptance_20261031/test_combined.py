"""Loopback-only independent actual Workspace/Tank/fake-CRM integration."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Thread
import time
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

if not os.environ.get('CRM_ASSEMBLED_ROOT'):
    pytest.skip('Explicit frozen backend/Workspace assembly required; see EVIDENCE.md', allow_module_level=True)
ROOT = Path(os.environ['CRM_ASSEMBLED_ROOT'])
sys.path.insert(0, str(ROOT / 'tank'))
import command
import trigger_crm as crm

RECORD = '00000000-0000-0000-0000-000000000013'
ORG = '00000000-0000-0000-0000-000000000014'


def tenant_for(org):
    value = bytearray(hashlib.sha1(UUID('7f3b1c2e-9a4d-4c1e-8f2a-5b6d7e8f9a0b').bytes + org.encode()).digest()[:16])
    value[6] = value[6] & 15 | 80
    value[8] = value[8] & 63 | 128
    return str(UUID(bytes=bytes(value)))


def test_actual_workspace_tank_corridor_and_unconfirmed_write(monkeypatch):
    tenant = tenant_for('org_offline_crm')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'offline-founder')
    monkeypatch.setenv('TRIGGER_CRM_URL', 'http://trigger-crm-backend:8000')
    monkeypatch.setenv('TRIGGER_CRM_PAT_TEST', 'dummy-crm-token')
    monkeypatch.setenv('TRIGGER_CRM_TENANT_BINDINGS', json.dumps({tenant: {'organization_id': ORG, 'token_env': 'TRIGGER_CRM_PAT_TEST'}}))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(TANK_API_KEY='dummy-workspace-key', box_region=lambda: 'us-east'))
    calls = []

    def upstream(request):
        assert request.method == 'GET', 'No mutation may reach the fake CRM'
        assert request.headers['authorization'] == 'Bearer dummy-crm-token'
        assert request.url.host == 'trigger-crm-backend'
        assert request.url.params['offset'] == '10' and request.url.params['limit'] == '10'
        assert 'tenant_id' not in request.url.params and 'x-tervory-tenant' not in request.headers
        calls.append(request.url.path)
        row = {'id': RECORD, 'first_name': 'Offline', 'public_token': 'dummy-crm-token', 'password': 'hidden', 'org': ORG}
        if request.url.path == '/api/leads/':
            data = {'open_leads': {'open_leads': [row], 'leads_count': 1}, 'close_leads': {'close_leads': [], 'leads_count': 0}}
        elif request.url.path == '/api/contacts/':
            data = {'contact_obj_list': [row], 'count': 1}
        else:
            assert request.url.path == '/api/invoices/estimates/'
            data = {'results': [row], 'count': 1}
        return httpx.Response(200, json=data)

    real_client = httpx.AsyncClient
    def fake_client(**kwargs):
        assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        return real_client(**kwargs, transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(crm, 'httpx', SimpleNamespace(AsyncClient=fake_client, Timeout=httpx.Timeout, HTTPError=httpx.HTTPError))
    app = FastAPI()
    app.include_router(crm.router)
    with socket.socket() as bound:
        bound.bind(('127.0.0.1', 0))
        port = bound.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='critical'))
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(.025)
        assert server.started
        env = {**os.environ, 'CRM_ASSEMBLED_ROOT': str(ROOT), 'TANK_URL': f'http://127.0.0.1:{port}'}
        result = subprocess.run(['node', str(Path(__file__).with_name('combined.cjs'))], env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert calls == ['/api/leads/', '/api/contacts/', '/api/invoices/estimates/']
        headers = {'x-tank-key': 'dummy-workspace-key', 'x-tervory-user': 'offline-founder', 'x-tervory-tenant': tenant}
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False) as client:
            response = client.post('/v1/trigger/crm/write', headers={**headers, 'x-confirmed': 'true'}, json={
                'resource': 'contacts', 'data': {'first_name': 'Offline', 'last_name': 'Synthetic'}})
            assert response.status_code == 409
            assert len(calls) == 3
            response = client.get('/v1/trigger/crm/contacts', headers={**headers, 'x-tervory-home-region': 'za'})
            assert response.status_code == 403
            assert len(calls) == 3
        print(result.stdout.strip())
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        assert not thread.is_alive()
