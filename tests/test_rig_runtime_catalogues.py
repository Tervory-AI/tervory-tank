"""Runtime demo-data exclusion and founder-approved shop migration."""
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/rig'))
from rigbox.service import Service
from rigbox.store import MemoryStore
from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database


@pytest.mark.asyncio
async def test_shop_migration_is_idempotent_and_preserves_existing_settings():
    admin, name = _admin_url(), 'rig_shop_' + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        conn = await asyncpg.connect(_database_url(admin, name))
        try:
            schema = (ROOT / 'agents/rig/schema.sql').read_text()
            # Start with the old table, so the migration must add its column.
            await conn.execute('CREATE SCHEMA agent_rig; CREATE TABLE agent_rig.retailers (tenant_id uuid PRIMARY KEY, slug text NOT NULL, email text, webhook text, name text NOT NULL DEFAULT \'\');')
            tenants = {slug: uuid4() for slug in ('archon', 'customnation', 'example', 'second')}
            for slug, tenant in tenants.items():
                await conn.execute('INSERT INTO agent_rig.retailers (tenant_id,slug) VALUES ($1,$2)', tenant, slug)
            await conn.execute(schema)
            await conn.execute(schema)
            expected = json.loads((ROOT / 'tests/fixtures/rig_catalogues/archon/publish.json').read_text())['shop']
            for slug, tenant in tenants.items():
                raw = await conn.fetchval('SELECT shop FROM agent_rig.retailers WHERE tenant_id=$1', tenant)
                assert json.loads(raw) == (expected if slug == 'archon' else {})
            changed = {'search': False}
            await conn.execute('UPDATE agent_rig.retailers SET shop=$2::jsonb WHERE tenant_id=$1', tenants['archon'], json.dumps(changed))
            await conn.execute(schema)
            assert json.loads(await conn.fetchval('SELECT shop FROM agent_rig.retailers WHERE tenant_id=$1', tenants['archon'])) == changed
        finally:
            await conn.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_shop_uses_only_the_store_column_and_survives_other_setting_updates(monkeypatch):
    store = MemoryStore()
    tenant = str(uuid4())
    await store.put_retailer(tenant, 'archon', None, None)
    service = Service(store)
    monkeypatch.setenv('CATALOGUE_DIR', str(ROOT / 'tests/fixtures/rig_catalogues'))
    assert await service._shop(tenant) == {}
    store.retailers[tenant]['shop'] = {'search': False, 'centre_sku': 'owned-product'}
    await store.put_retailer(tenant, 'archon', None, None, 'Updated store')
    assert await service._shop(tenant) == {'search': False, 'centre_sku': 'owned-product'}
    assert await service._shop(str(uuid4())) == {}


def test_no_catalogues_or_test_keys_can_ship_in_rig():
    runtime = ROOT / 'agents/rig'
    for path in runtime.rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        assert path.suffix.lower() != '.csv', path
        assert path.name != 'publish.json', path
        data = path.read_bytes()
        assert b'Staccato' not in data, path
        assert re.search(rb'rk_pub_[A-Za-z0-9][A-Za-z0-9_-]*', data) is None, path
    assert not (runtime / 'catalogues').exists()
    for name in ('sample.py', 'demo.py'):
        assert not (runtime / 'rigbox/three_d' / name).exists()
    assert not hasattr(Service, 'load_folder')
    assert not hasattr(Service, 'load_catalogues')
    assert not hasattr(Service, 'import_catalogue')
    assert not hasattr(Service, '_apply_publish')
    dockerfile = (runtime / 'Dockerfile').read_text()
    assert 'catalogues' not in dockerfile
    assert 'tests' not in dockerfile
    assert 'CATALOGUE_DIR' not in (runtime / 'docker-compose.yml').read_text()
    assert 'publish.json' not in (runtime / 'rigbox/catalogue.py').read_text()
    assert 'CATALOGUE_DIR' not in (runtime / 'app.py').read_text()
