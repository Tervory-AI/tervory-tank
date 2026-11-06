"""Replay every room handler in disposable Postgres; reject all TCP traffic."""
from contextlib import asynccontextmanager
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[3]


class Memory:
    """Private rehearsal memory; never calls Hermes or a model."""
    async def remember(self, *args, **kwargs):
        return {'id': kwargs.get('record_id', str(uuid4())), 'seen': 1}

    async def records(self, *args, **kwargs):
        return []

    async def forget(self, *args, **kwargs):
        return None


class Publisher:
    def __init__(self):
        self.data = json.loads((ROOT / 'tests/market_lab_ml3/sources.json').read_text())
        self.client = SimpleNamespace(max_bytes=None)
        self.downloads = []

    def get(self, url):
        from core import intel
        # Recorded dependency and publisher responses, never fetched here.
        self.downloads.append(url)
        if url == intel.REPO:
            data = {'sha': 'a' * 40, 'truncated': False, 'tree': [
                {'type': 'blob', 'path': 'workspace/package-lock.json'}]}
        elif url == intel.KEV:
            data = self.data['kev']
        elif url.endswith('/workspace/package-lock.json'):
            data = self.data['lock']
        elif url.endswith('/v1/vulns/' + self.data['osv_advisory']['id']):
            data = self.data['osv_advisory']
        else:
            raise RuntimeError('Unrecorded dry-run publisher request')
        return json.dumps(data).encode()

    def post_json(self, url, payload):
        from core import intel
        if url != intel.OSV:
            raise RuntimeError('Unrecorded dry-run publisher request')
        return json.dumps(self.data['osv_query']).encode()


async def run():
    # pgserver is a check-time dependency only; dry runs never select DATABASE_URL.
    import asyncpg
    import pgserver
    import app as room
    from chassis.db import ensure_schema
    from chassis import events
    from core import intel, feed_links, warning_bridge, ml3, briefs
    from core.ledger import PostgresLedger
    from core.evidence import overview
    from core.readiness import MAIL, REQUIRED
    from feeds.keys import KEY_NAMES

    def no_tcp(sock, address):
        if sock.family != socket.AF_UNIX:
            raise RuntimeError('Dry run refuses all TCP connections')
        return connect(sock, address)

    connect = socket.socket.connect
    with tempfile.TemporaryDirectory(prefix='market-lab-dry-run-') as directory:
        server = pgserver.get_server(Path(directory) / 'postgres')
        conn = None
        try:
            conn = await asyncpg.connect(server.get_uri())
            await ensure_schema(conn, 'market_lab')
            ledger = PostgresLedger(conn)
            ledger.memory = Memory()
            await ledger.apply_schema()
            owner = room.HEARTBEAT_TENANT
            ident = uuid4()
            await conn.execute('''INSERT INTO agent_market_lab.feed_links
                (tenant_id,id,url,label,cadence) VALUES ($1,$2,$3,$4,'daily')''',
                UUID(owner), ident, 'https://www.federalreserve.gov/feeds/press_all.xml', 'Recorded public RSS')
            fixture_dir = ROOT / 'tests/fixtures/feeds'
            # Subscriptions name feed.xml relative to the replay root.
            import shutil
            replay = Path(directory) / 'feeds'
            shutil.copytree(fixture_dir, replay)
            rss = ROOT / 'tests/market_lab_keyless_feeds/fixtures/feed.xml'
            (replay / 'rss').mkdir(exist_ok=True)
            shutil.copy2(rss, replay / 'feed.xml')
            publisher = Publisher()
            produce = intel.produce
            refresh_links = feed_links.refresh_links
            calls = []

            async def corridor(operation, payload):
                calls.append(operation)
                if operation == 'series':
                    return {'series': []}
                if operation == 'alerts/pending':
                    return {'pending': []}
                if operation == 'alerts/webhooks':
                    return {'sent': 0}
                if operation == 'alerts/settings':
                    return {'email': False, 'webhook': False}
                if operation == 'training':
                    return {'ok': True}
                raise RuntimeError('Unrecorded dry-run corridor request')

            async def subscriptions(*args, **kwargs):
                return await refresh_links(*args, **kwargs, fixtures=str(replay))

            @asynccontextmanager
            async def connection(**kwargs):
                yield ledger

            async def publish(*args, **kwargs):
                calls.append('events/publish')
                return True

            settings = {name: '' for name in (*MAIL, *KEY_NAMES, 'MARKET_LAB_SMTP_USER',
                        'MARKET_LAB_SMTP_PASSWORD', 'FEEDS_FIXTURES', *REQUIRED)}
            settings['DATABASE_URL'] = server.get_uri()
            results = {}
            with patch.dict('os.environ', settings), patch.object(socket.socket, 'connect', no_tcp), \
                    patch.object(room, '_ledger', connection), \
                    patch.object(intel, 'produce', lambda: produce(publisher)), \
                    patch.object(feed_links, 'refresh_links', subscriptions), \
                    patch.object(warning_bridge, 'call', corridor), patch.object(ml3, 'call', corridor), \
                    patch.object(briefs, 'call', corridor), patch.object(events, 'publish', publish):
                for kind, handler in room.app.state.handlers.items():
                    payload = {'engine': room.case_plan()['engine']}
                    if kind == 'ping':
                        payload['heartbeat'] = True
                    if kind == 'refresh':
                        payload['fixtures'] = str(replay)
                    if kind == 'research':
                        payload['question'] = 'Recent SEC filings from Ruger'
                    ctx = SimpleNamespace(agent='market_lab', tenant_id=owner,
                                          input=payload, memory=ledger.memory)
                    result = await handler(ctx)
                    if kind == 'feed_links':
                        assert result['feeds'] and result['feeds'][0]['rows'] > 0, 'RSS replay failed'
                    if kind == 'refresh':
                        assert not any(f['note'] == 'Off, source could not be read' for f in result['feeds']), 'Feed replay failed'
                    results[kind] = {'status': 'passed', 'result': result}
                live = await overview(ledger, owner, room.case_plan()['engine'])
                assert live['on_count'] == 0, 'Fixture observations leaked into live feeds'
                # A replay must not create a monthly brief with no cited claims.
                visible = await ledger.briefs_for(owner)
                assert await conn.fetchval('SELECT count(*) FROM agent_market_lab.reports') > 0
                assert visible == [], 'An unsourced rehearsal brief reached the live list'
            return {'dry_run': True, 'network': 'disabled', 'storage': 'disposable',
                    'jobs': results, 'publisher_downloads': len(publisher.downloads),
                    'corridor_calls': calls, 'training': 'not_applicable'}
        finally:
            if conn is not None:
                await conn.close()
            server.cleanup()
