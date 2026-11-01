"""Real local backup/restore round trip. No production endpoints or credentials."""
import asyncio
import os
import shutil

import pytest

from ops.restore_drill import command, drill, newest, sandbox
from r2_archive import PLATFORM_TENANT, archive_file


class ArchiveStore:
    """Offline R2 object contract; real archive writer/verifier, no cloud access."""
    def __init__(self, region):
        self.region = region
        self.owner = 'zenas' if region == 'za' else 'uploads'
        self.bucket = 'offline'
        self.data = {}

    def _prefix(self, tenant, category, *, public):
        assert public == (self.region == 'za')
        return f'{self.region}/{tenant}/{category}/'

    async def put(self, tenant, category, name, data, *, public):
        key = self._prefix(tenant, category, public=public) + name
        self.data[key] = data
        return key

    async def get(self, tenant, category, name, *, public):
        return self.data[self._prefix(tenant, category, public=public) + name]

    async def objects(self, tenant, category, *, public):
        prefix = self._prefix(tenant, category, public=public)
        return [{'key': k} for k in self.data if k.startswith(prefix)]


def test_newest_rejects_cross_region_and_missing_snapshots():
    with pytest.raises(RuntimeError, match='regional prefix'):
        newest([{'key': 'za/x'}], 'us-east/')
    with pytest.raises(RuntimeError, match='Postgres'):
        newest([], 'us-east/')


@pytest.mark.parametrize('region', ['us-east', 'za'])
def test_offline_encrypted_roundtrip(tmp_path, monkeypatch, region):
    if os.environ.get('RESTORE_DRILL_E2E') != '1':
        pytest.skip('Dedicated restore-drill CI enables real disposable stores')
    assert shutil.which('age') and shutil.which('age-keygen') and shutil.which('docker')
    monkeypatch.setenv('TANK_REGION', region)
    # Tool-generated ephemeral identity stays in its file, never read by Python/logged.
    identity = tmp_path / 'identity'
    command('age-keygen', '-o', str(identity))
    recipient = command('age-keygen', '-y', str(identity)).decode().strip()
    store = ArchiveStore(region)
    public = region == 'za'

    async def prepare():
        with sandbox() as source:
            schemas = ['tank', 'base', 'agent_tank', 'agent_template', 'agent_base',
                       'agent_ghost', 'agent_market_lab', 'agent_radix', 'agent_rig',
                       'agent_tiger', 'agent_tisan', 'agent_trigger', 'agent_zenas']
            for schema in schemas:
                source.sql(f'CREATE SCHEMA {schema}')
            source.sql("""CREATE TABLE tank.ledger (tenant_id uuid NOT NULL, id int);
                CREATE TABLE tank.tasks (tenant_id uuid NOT NULL, id int);
                CREATE TABLE base.records (tenant_id uuid NOT NULL, id int);
                INSERT INTO tank.ledger VALUES ('00000000-0000-0000-0000-000000000011',1),
                ('00000000-0000-0000-0000-000000000022',2);
                INSERT INTO tank.tasks SELECT * FROM tank.ledger;
                INSERT INTO base.records SELECT * FROM tank.ledger;""")
            plain = tmp_path / 'database.dump'
            plain.write_bytes(command('docker', 'exec', source.pg, 'pg_dump', '-Fc', '-U', 'postgres', 'postgres'))
            encrypted = tmp_path / 'database.dump.age'
            command('age', '-r', recipient, '-o', str(encrypted), str(plain))
            plain.unlink()
            await archive_file(store, encrypted, 'backups', tenant_id=PLATFORM_TENANT,
                               public=public, label='database.dump.age')
            source.request('PUT', '/collections/offline', json={'vectors': {'size': 2, 'distance': 'Cosine'}})
            source.request('PUT', '/collections/offline/points?wait=true',
                           json={'points': [{'id': 1, 'vector': [1., 0.]}, {'id': 2, 'vector': [0., 1.]}]})
            snapshot = source.request('POST', '/collections/offline/snapshots').json()['result']['name']
            plain = tmp_path / 'qdrant.snapshot'
            plain.write_bytes(source.request('GET', '/collections/offline/snapshots/' + snapshot).content)
            encrypted = tmp_path / 'qdrant.snapshot.age'
            command('age', '-r', recipient, '-o', str(encrypted), str(plain))
            plain.unlink()
            await archive_file(store, encrypted, 'backups', tenant_id=PLATFORM_TENANT,
                               public=public, label='qdrant/offline.snapshot.age')
        return await drill(region, identity, check_rls=True, store=store)

    result = asyncio.run(prepare())
    assert result['tenant_table_rows'] == {'"tank"."ledger"': 2, '"tank"."tasks"': 2, '"base"."records"': 2}
    assert result['collection_points'] == {'offline': 2}
    assert result['restore_seconds'] > 0
    assert result['rls_failures'] == [], result['rls_failures']
    # Altering ciphertext must be rejected by the real manifest verifier.
    key = next(k for k in store.data if k.endswith('part-000000'))
    store.data[key] = b'corrupt'
    with pytest.raises(Exception, match='integrity'):
        asyncio.run(drill(region, identity, store=store))
