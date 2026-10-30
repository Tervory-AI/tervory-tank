"""Automatic Rig catalogue watches and durable delivery of confirmed readings.

All product data is fetched per tenant through Tank. No page-reading or job
scheduling implementation lives here: ordinary Tiger watches do that work.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

import httpx

from watch import BadWatch, DuplicateWatch, PgStore, SQL_ENSURE_DISPATCH, _known_stock, ensure_tables

async def ensure_rig_tables(conn, schema: str) -> None:
    await conn.execute(f'ALTER TABLE {schema}.watchlist ADD COLUMN IF NOT EXISTS rig_managed boolean NOT NULL DEFAULT false')
    await conn.execute(f'''CREATE TABLE IF NOT EXISTS {schema}.rig_targets (
        tenant_id uuid NOT NULL, sku text NOT NULL, url text NOT NULL,
        watch_id uuid NOT NULL REFERENCES {schema}.watchlist(id) ON DELETE CASCADE,
        observed_at timestamptz, last_value jsonb, pending jsonb,
        attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, sku))''')
    await conn.execute(f'CREATE INDEX IF NOT EXISTS rig_targets_url ON {schema}.rig_targets(tenant_id,url)')


def confirmed_value(observation: dict) -> dict | None:
    if (observation.get('method') in {None, 'blocked', 'robots', 'error', 'none', 'unread'}
            or observation.get('issue') or not observation.get('product_name')):
        return None
    stock = _known_stock(observation.get('availability'))
    currency = str(observation.get('currency') or '').upper()
    try:
        price = Decimal(str(observation.get('price')))
        if not price.is_finite() or price < 0 or stock is None or not re.fullmatch('[A-Z]{3}', currency):
            return None
        return {'price': str(price.quantize(Decimal('.01'))), 'currency': currency,
                'active': stock in {'InStock', 'LimitedAvailability'}}
    except (InvalidOperation, ValueError):
        return None


async def publish_price_changed(store, tenant: str, watch: dict, previous: dict | None, current: dict) -> None:
    """One committed price fact per product (or ordinary watch), irrespective of mail preferences."""
    try:
        before = confirmed_value(previous) if previous else None
        after = confirmed_value(current)
        if not before or not after or before['currency'] != after['currency'] or before['price'] == after['price']:
            return
        from chassis.events import publish
        skus = await store.rig_skus(tenant, watch['id']) if hasattr(store, 'rig_skus') else []
        for sku in skus or [None]:
            await publish(tenant, 'tiger.price.changed', f"{watch['id']}:{current['id']}:{sku or ''}", {
                'watch_id': str(watch['id']), 'observation_id': str(current['id']), 'sku': sku,
                'page_id': hashlib.sha256(watch['url'].encode()).hexdigest(),
                'previous_price': before['price'], 'price': after['price'],
                'currency': after['currency'], 'observed_at': current['ts'],
            })
    except Exception:
        logging.getLogger(__name__).warning('Price event unavailable; the check remains saved')


async def record_observation(conn, schema: str, observation: dict) -> None:
    """Called in the observation INSERT transaction: a crash cannot lose a send."""
    value = confirmed_value(observation)
    if value is None:
        return
    stamp = datetime.fromisoformat(observation['ts'].replace('Z', '+00:00'))
    payload = {**value, 'url': observation['url'], 'observed_at': stamp.isoformat()}
    await conn.execute(f'''UPDATE {schema}.rig_targets SET
        pending=CASE WHEN last_value IS DISTINCT FROM $3::jsonb THEN $4::jsonb ELSE pending END,
        attempts=CASE WHEN last_value IS DISTINCT FROM $3::jsonb THEN 0 ELSE attempts END,
        next_attempt_at=CASE WHEN last_value IS DISTINCT FROM $3::jsonb THEN now() ELSE next_attempt_at END,
        last_value=$3::jsonb, observed_at=$5
        WHERE tenant_id=$1 AND url=$2 AND (observed_at IS NULL OR observed_at<$5)''',
        UUID(observation['tenant_id']), observation['url'], json.dumps(value), json.dumps(payload), stamp)


class TankRig:
    def __init__(self, http):
        self.http = http

    async def request(self, method: str, path: str = '', **kwargs):
        response = await self.http.request(method,
            os.environ.get('TANK_URL', 'http://tank:8000').rstrip('/') + '/v1/access/rig/tiger' + path,
            headers={'X-Tank-Key': os.environ.get('TANK_KEY', '')}, timeout=30, **kwargs)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('Invalid Rig response')
        return data

    async def tenants(self) -> list[str]:
        data = await self.request('GET', '/tenants')
        if not isinstance(data.get('tenants'), list):
            raise ValueError('Invalid Rig tenants')
        return sorted({str(UUID(tenant)) for tenant in data['tenants']})

    async def products(self, tenant: str) -> list[dict]:
        data = await self.request('GET', '/products', params={'tenant_id': tenant})
        if data.get('tenant_id') != tenant or not isinstance(data.get('products'), list):
            raise ValueError('Invalid Rig tenant snapshot')
        seen = set()
        for row in data['products']:
            if (not isinstance(row, dict) or not isinstance(row.get('sku'), str) or not 1 <= len(row['sku']) <= 120
                    or not isinstance(row.get('url'), str) or not row['url'] or row['sku'] in seen):
                raise ValueError('Invalid Rig product snapshot')
            seen.add(row['sku'])
        return data['products']

    async def send(self, tenant: str, sku: str, payload: dict) -> bool:
        data = await self.request('POST', json={**payload, 'tenant_id': tenant, 'sku': sku})
        if type(data.get('updated')) is not bool:
            raise ValueError('Invalid Rig delivery receipt')
        return data['updated']

    async def alert_context(self, tenant: str, url: str) -> dict:
        data = await self.request('GET', '/alert-context', params={'tenant_id': tenant, 'url': url})
        if data.get('tenant_id') != tenant or not isinstance(data.get('urls'), list):
            raise ValueError('Invalid Rig tenant snapshot')
        return data


class RigWatches:
    def __init__(self, watches: PgStore):
        self.watches = watches
        self.pool, self.schema = watches.pool, watches.schema

    async def discover(self, client: TankRig) -> int:
        tenants = await client.tenants()
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            await conn.executemany(SQL_ENSURE_DISPATCH.format(schema=self.schema), [(UUID(t),) for t in tenants])
        return len(tenants)

    async def managed(self, tenant: str, url: str) -> bool:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            return bool(await conn.fetchval(f'''SELECT rig_managed FROM {self.schema}.watchlist
                WHERE tenant_id=$1 AND url=$2''', UUID(tenant), url))

    async def sync(self, tenant: str, client: TankRig) -> None:
        from watch import check_url
        products = await client.products(tenant)  # An unavailable snapshot never means an empty catalogue.
        known = {w['url']: w for w in await self.watches.list_watches(tenant)}
        wanted = []
        for row in products:
            url = row['url']
            if url not in known:
                try:
                    url = await asyncio.to_thread(check_url, url)
                except BadWatch:
                    continue
                # A concurrent dispatcher must not read it before the Rig binding
                # and managed flag commit together below.
                fields = dict(tenant_id=tenant, url=url, label=str(row.get('name') or '')[:200],
                              engine='', every='6h', enabled=False, threshold=0,
                              alert_price=False, alert_stock=False, alert_new_product=False,
                              alert_below_cost=False, alert_market_gap=False)
                try:
                    known[url] = await self.watches.create_watch(fields)
                except DuplicateWatch:
                    known[url] = await self.watches.get_watch(tenant, url)
            wanted.append((row['sku'], url, UUID(known[url]['id'])))
        fresh = set()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', 'tiger-rig:' + tenant)
                await conn.execute(f'DELETE FROM {self.schema}.rig_targets WHERE tenant_id=$1 AND NOT(sku=ANY($2::text[]))',
                                   UUID(tenant), [r[0] for r in wanted])
                for sku, url, watch_id in wanted:
                    changed = await conn.fetchval(f'''INSERT INTO {self.schema}.rig_targets(tenant_id,sku,url,watch_id)
                        VALUES($1,$2,$3,$4) ON CONFLICT(tenant_id,sku) DO UPDATE SET
                        url=EXCLUDED.url,watch_id=EXCLUDED.watch_id,observed_at=NULL,last_value=NULL,pending=NULL,
                        attempts=0,next_attempt_at=now()
                        WHERE rig_targets.url<>EXCLUDED.url OR rig_targets.watch_id<>EXCLUDED.watch_id RETURNING sku''',
                        UUID(tenant), sku, url, watch_id)
                    if changed:
                        fresh.add(url)
                    await conn.execute(f'UPDATE {self.schema}.watchlist SET rig_managed=true,enabled=true WHERE tenant_id=$1 AND id=$2',
                                       UUID(tenant), watch_id)
                await conn.execute(f'''UPDATE {self.schema}.watchlist w SET enabled=false
                    WHERE tenant_id=$1 AND rig_managed AND NOT EXISTS
                    (SELECT 1 FROM {self.schema}.rig_targets t WHERE t.tenant_id=w.tenant_id AND t.watch_id=w.id AND t.url=w.url)''', UUID(tenant))
                await conn.execute(f'''UPDATE {self.schema}.jobs j SET status='cancelled'
                    WHERE tenant_id=$1 AND kind='check' AND status='queued' AND EXISTS
                    (SELECT 1 FROM {self.schema}.watchlist w WHERE w.tenant_id=j.tenant_id
                     AND w.url=j.input->>'url' AND w.rig_managed AND NOT w.enabled)''', UUID(tenant))
        for url in fresh:
            if not await self.watches.check_open(tenant, url):
                await self.watches.enqueue_check(tenant, url)

    async def deliver(self, tenant: str, client: TankRig) -> int:
        # Reconcile before every retry as well as before every read.
        await self.sync(tenant, client)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f'''SELECT sku,url,pending,attempts FROM {self.schema}.rig_targets
                WHERE tenant_id=$1 AND pending IS NOT NULL AND next_attempt_at<=now()
                ORDER BY next_attempt_at,sku LIMIT 20''', UUID(tenant))
        sent = 0
        for row in rows:
            payload = json.loads(row['pending']) if isinstance(row['pending'], str) else row['pending']
            try:
                accepted = await client.send(tenant, row['sku'], payload)
            except (httpx.HTTPError, ValueError):
                delay = min(3600, 60 * 2 ** min(row['attempts'], 6))
                async with self.pool.acquire() as conn:
                    await conn.execute(f'''UPDATE {self.schema}.rig_targets SET attempts=attempts+1,
                        next_attempt_at=now()+make_interval(secs=>$4)
                        WHERE tenant_id=$1 AND sku=$2 AND pending=$3::jsonb''',
                        UUID(tenant), row['sku'], json.dumps(payload), delay)
                continue
            async with self.pool.acquire() as conn:
                # Do not acknowledge a newer reading that arrived during this request.
                await conn.execute(f'''UPDATE {self.schema}.rig_targets SET pending=NULL,attempts=0,
                    last_value=CASE WHEN $4 THEN last_value ELSE NULL END
                    WHERE tenant_id=$1 AND sku=$2 AND pending=$3::jsonb''', UUID(tenant), row['sku'], json.dumps(payload), accepted)
            sent += int(accepted)
        return sent
