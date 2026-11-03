"""ML4 through the unchanged #410 founder path; fake encoder, disposable SQL."""
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from test_agent_memory_records import Encoder, memory as memory_fixture
from chassis.memory import MemoryClient
from chassis.tank import TankClient
from core.patterns import claim, listing, remember
from engines.ffl.warnings import plan
from hermes.deidentify import deidentify
from hermes.record_schema import PLATFORM_TENANT
from hermes.service import create_app
from hermes.store import InMemoryStore

memory = memory_fixture
INVENTORY = {'reviewed': True, 'names': ['placeholder privateperson'],
             'emails': [], 'phones': [], 'addresses': [], 'client_domains': []}
STATS = {'lag_min': 7, 'lag_max': 14, 'lag_median': 10,
         'episode_count': 3, 'hits': 2, 'hit_rate': 2/3}


@pytest.mark.parametrize('config', plan()['pairs'], ids=lambda row: row['id'])
def test_each_pattern_remains_parseable_after_existing_publication_scrubber(config):
    value = claim(config, STATS)
    published, evidence = deidentify(json.dumps(value), [str(uuid4())], str(uuid4()), INVENTORY)
    assert json.loads(published) == value
    assert evidence == []  # Existing #410 intentionally removes private document IDs.


@pytest.mark.asyncio
async def test_private_save_fake_encoder_founder_only_publish_and_other_tenant_sql_reads(memory, monkeypatch):
    import memory_routes
    m = memory
    gateway_calls = []
    async def no_model(*args, **kwargs):
        gateway_calls.append(args)
        raise AssertionError('no model gateway permitted')
    monkeypatch.setattr(TankClient, 'route', no_model)
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    monkeypatch.setenv('TANK_KEY_' + m.agent.upper(), 'placeholder-room')
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-hermes') as http:
        client = MemoryClient(base_url='http://placeholder-hermes', api_key='placeholder-room', agent=m.agent, http=http)
        config, document = plan()['pairs'][0], str(uuid4())
        assert await remember(client, m.tenant, config, STATS, document)
        assert await remember(client, m.tenant, config, STATS, document)
        own = await client.records(m.tenant)
        assert len(own) == 1 and own[0]['kind'] == 'warning_pattern'
        assert own[0]['evidence'] == [document]
        assert m.records.encoder.calls  # Only the injected four-number fake encoder ran.
        assert await client.records(m.other) == []
        assert await client.records(m.other, tier='platform') == []

        # The actual Tank route proxies into Hermes's existing founder routes.
        async def corridor(method, path, actor, **kwargs):
            response = await http.request(method, path, json=kwargs.get('body'), params=kwargs.get('params'),
                                          headers={'X-Tank-Key': 'placeholder-workspace', 'X-Tervory-Admin': actor})
            from fastapi import HTTPException
            if not response.is_success:
                raise HTTPException(response.status_code, response.json().get('detail'))
            return response.json()
        monkeypatch.setattr(memory_routes, 'hermes', corridor)
        tank = FastAPI()
        tank.include_router(memory_routes.router)
        headers = {'X-Tank-Key': 'placeholder-workspace', 'X-Tervory-Admin': 'placeholder-founder'}
        publication = {'agent': m.agent, 'tenant_id': m.tenant, 'source_row': own[0]['id']}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank), base_url='http://placeholder-tank') as gateway:
            assert (await gateway.post('/v1/memory/publish', json=publication, headers=headers)).status_code == 403
            assert await client.records(m.other, tier='platform') == []
            policy = {'agent': m.agent, 'tenant_id': m.tenant, 'enabled': True, 'identifiers': INVENTORY}
            assert (await gateway.post('/v1/memory/publish-policy', json=policy, headers=headers)).status_code == 200
            denied = {**headers, 'X-Tervory-Admin': 'placeholder-other'}
            assert (await gateway.post('/v1/memory/publish', json=publication, headers=denied)).status_code == 404
            assert await client.records(m.other, tier='platform') == []
            assert (await gateway.post('/v1/memory/publish', json=publication, headers=headers)).status_code == 200
        # Listing must never touch the vector index or invoke the encoder.
        before = list(m.records.encoder.calls)
        async def no_recall(*args, **kwargs): raise AssertionError('no embedding search')
        monkeypatch.setattr(client, 'recall', no_recall)
        published = await listing(client, m.other, plan())
        assert published['patterns'] == [] and len(published['published']) == 1
        row = published['published'][0]
        assert row['claim']['pair_id'] == config['id'] and row['tier'] == 'platform'
        records = await client.records(m.other, tier='platform')
        assert records[0]['tenant_id'] == PLATFORM_TENANT
        assert document not in json.dumps(records) and m.tenant not in json.dumps(records)
        assert m.records.encoder.calls == before
        assert gateway_calls == []
