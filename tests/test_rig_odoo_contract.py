"""Replay a recorded fake Odoo ASGI server; no external network or real keys."""
import copy
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/rig"))

from rigbox.quotes.senders import DeliveryError, OdooHandoff, RetailerHandoff  # noqa: E402

RECORDING = Path(__file__).parent / 'fixtures/rig_odoo/quotation.json'
TENANT = '11111111-1111-4111-8111-111111111111'
QUOTE = {'id': 'quote-offline', 'contact': {'name': 'Offline Shopper', 'email': 'shopper@example.invalid'},
         'payload': {'kind': 'product', 'product': {'id': 'MODEL-1', 'name': 'Approved product',
                                                 'price': {'amount': 120.0, 'currency': 'ZAR'}}}}
SETTINGS = {'URL': 'https://odoo.example.invalid', 'DATABASE': 'fixture-db',
            'USER': 'fixture-user', 'API_KEY': 'fixture-key'}


class RecordedOdoo:
    """Independent, exact request/response recording served through ASGI HTTP.

    Unexpected calls fail, including confirmation, invoices, payment and refunds.
    The trace is retained for inspection; this is not an Odoo implementation.
    """
    def __init__(self, exchanges):
        self.exchanges = copy.deepcopy(exchanges)
        self.recorded = []
        self.app = FastAPI()
        self.app.post('/jsonrpc')(self.call)

    async def call(self, request: Request):
        body = await request.json()
        index = len(self.recorded)
        assert request.headers['content-type'] == 'application/json'
        assert index < len(self.exchanges), 'Unexpected extra Odoo call'
        exchange = self.exchanges[index]
        assert body == exchange['request']
        self.recorded.append({'request': body, 'response': exchange['response']})
        if exchange.get('lost_response'):
            # The fake committed its create, but the caller did not receive it.
            raise httpx.ReadTimeout('Synthetic lost response')
        return JSONResponse(exchange['response'])


def exchanges(version=17):
    rows = json.loads(RECORDING.read_text())['exchanges']
    rows[0]['response']['result'] = {'server_version_info': [version, 0, 0], 'server_version': f'{version}.0'}
    return rows


def adapter(http):
    return OdooHandoff(http, **{name.lower(): value for name, value in SETTINGS.items()})


@pytest.mark.asyncio
@pytest.mark.parametrize('version', [16, 17, 18])
@pytest.mark.parametrize('lost_response', [False, True])
async def test_recorded_quotation_contract_and_uncertain_create(version, lost_response, tmp_path):
    rows = exchanges(version)
    if lost_response:
        rows[-1]['lost_response'] = True
        retry = copy.deepcopy(rows[:3])
        retry[-1]['response']['result'] = [5]
        rows.extend(retry)
    server = RecordedOdoo(rows)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app)) as http:
        sender = adapter(http)
        args = dict(tenant_id=TENANT, email=None, webhook=None, quote=QUOTE)
        if lost_response:
            with pytest.raises(DeliveryError, match='^odoo_unavailable$'):
                await sender.send(**args)
        await sender.send(**args)
    assert len(server.recorded) == len(rows)
    # Persist the observed HTTP exchange for local evidence without live credentials.
    (tmp_path / 'observed.json').write_text(json.dumps(server.recorded, indent=2))
    creates = [r['request']['params']['args'] for r in server.recorded
               if r['request']['params']['service'] == 'object'
               and r['request']['params']['args'][3:5] == ['sale.order', 'create']]
    assert len(creates) == 1
    assert 'state' not in creates[0][5][0]  # Default draft; never confirm it.


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', list(SETTINGS))
async def test_every_odoo_setting_required_before_any_request(monkeypatch, missing):
    monkeypatch.setenv('RIG_QUOTE_FLOWS', json.dumps({TENANT: {'sender': 'odoo'}}))
    for name, value in SETTINGS.items():
        monkeypatch.setenv('RIG_ODOO_' + name, '' if name == missing else value)
    server = RecordedOdoo([])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app)) as http:
        with pytest.raises(DeliveryError, match='^not_configured$'):
            await RetailerHandoff(http).send(tenant_id=TENANT, email=None, webhook=None, quote=QUOTE)
    assert server.recorded == []


@pytest.mark.asyncio
@pytest.mark.parametrize('fault,code', [('version', 'odoo_version_unsupported'),
                                      ('auth', 'odoo_authentication'), ('error', 'odoo_rejected')])
async def test_recorded_protocol_failures_stop_before_writes(fault, code):
    rows = exchanges(19 if fault == 'version' else 17)[:1 if fault != 'auth' else 2]
    if fault == 'auth':
        rows[-1]['response']['result'] = False
    if fault == 'error':
        rows[-1]['response'] = {'jsonrpc': '2.0', 'id': 1,
                               'error': {'code': 200, 'message': 'Synthetic private upstream detail'}}
    server = RecordedOdoo(rows)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app)) as http:
        with pytest.raises(DeliveryError, match='^' + code + '$'):
            await adapter(http).send(tenant_id=TENANT, email=None, webhook=None, quote=QUOTE)
    assert len(server.recorded) == len(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize('prefix', ['RIG_ODOO', 'RIG_ODOO_CUSTOM_NATION'])
async def test_fully_configured_tenant_dispatch_and_foreign_tenant_stays_off(monkeypatch, prefix):
    monkeypatch.setenv('RIG_QUOTE_FLOWS', json.dumps({TENANT: {'sender': 'odoo', 'env_prefix': prefix}}))
    for name, value in SETTINGS.items():
        monkeypatch.setenv(prefix + '_' + name, value)
    server = RecordedOdoo(exchanges())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app)) as http:
        sender = RetailerHandoff(http)
        await sender.send(tenant_id=TENANT, email=None, webhook=None, quote=QUOTE)
        assert len(server.recorded) == 9
        with pytest.raises(DeliveryError, match='^not_configured$'):
            await sender.send(tenant_id='22222222-2222-4222-8222-222222222222',
                              email=None, webhook=None, quote=QUOTE)
    assert len(server.recorded) == 9
