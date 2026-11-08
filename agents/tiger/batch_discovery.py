"""Use the existing public sitemap reader in durable, bounded job slices."""
import json
import httpx
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from uuid import UUID, uuid5

from rig_watch import CatalogueDiscovery, DiscoveryGate


def product_page(items):
    for item in items:
        if not isinstance(item, dict) or item.get('method') not in {'jsonld', 'microdata'}:
            continue
        try:
            price = Decimal(str(item.get('price')))
        except InvalidOperation:
            continue
        if price.is_finite() and price >= 0 and item.get('name') and item.get('currency'):
            return True
    return False


async def step(ctx, pool, fetch, render):
    tenant, current = UUID(str(ctx.tenant_id)), UUID(str(ctx.job_id))
    root = UUID(str(ctx.input.get('root_job_id') or current))
    async with pool.acquire() as conn:
        previous = await conn.fetchval('SELECT result FROM agent_tiger.jobs WHERE tenant_id=$1 AND id=$2', tenant, current)
        previous = json.loads(previous) if isinstance(previous, str) else previous
        if previous and previous.get('slice_saved'):
            return previous
        original = await conn.fetchval("""SELECT input FROM agent_tiger.jobs WHERE tenant_id=$1 AND id=$2
            AND kind='competitor_match' AND input->>'_batch_discovery'='true'""", tenant, root)
        original = json.loads(original) if isinstance(original, str) else original
        if original is None:
            raise ValueError('Missing discovery source')
        saved = {}
        if ctx.input.get('previous_job_id'):
            saved = await conn.fetchval("""SELECT result FROM agent_tiger.jobs WHERE tenant_id=$1 AND id=$2
                AND kind='competitor_match' AND input->>'_batch_discovery'='true'
                AND (id=$3 OR input->>'root_job_id'=$3::text)""",
                tenant, UUID(ctx.input['previous_job_id']), root)
            saved = json.loads(saved) if isinstance(saved, str) else saved
            if not saved or not saved.get('slice_saved'):
                raise ValueError('Missing discovery checkpoint')
    parsed = urlsplit(original['url'])
    site = f'{parsed.scheme}://{parsed.netloc}'
    urls = set(saved.get('product_urls', []))
    receipts = list(saved.get('skill_receipts', []))
    async def publish(site, url, html, human_check):
        if not human_check and html:
            result = await ctx.tank.run_skill(ctx.tenant_id, 'tiger.price_extract', {'html': html, 'url': url})
            if result.get('_ledger_id'):
                receipts.append({'url': url, 'skill': 'tiger.price_extract',
                                 'ledger_id': result['_ledger_id'], 'cost_usd': result.get('_cost_usd')})
            if product_page(result.get('items') or []):
                urls.add(url)
        return {'matches': []}
    async def read(url):
        response = await render(url)
        if not isinstance(response, dict) or (not response.get('ok') and not response.get('challenge')
                and response.get('status') not in {401, 403, 429, 301, 302, 303, 307, 308}
                and response.get('reason') != 'redirect'):
            raise httpx.HTTPError('Source unavailable')
        return response
    cursor, done = await CatalogueDiscovery(fetch, read, DiscoveryGate(pool), publish).step(
        [site], [], saved.get('cursor'))
    continuation = None if done else uuid5(current, 'continuation')
    result = {'slice_saved': True, 'status': 'completed' if done else 'running',
              'product_urls': sorted(urls), 'sites': cursor['sites'], 'cursor': None if done else cursor,
              'continuation_id': str(continuation) if continuation else None, 'model_calls': 0, 'skill_receipts': receipts}
    if getattr(ctx.tank, 'parts', []):
        result['_savings_parts'] = list(dict.fromkeys(ctx.tank.parts))
    async with pool.acquire() as conn:
        async with conn.transaction():
            if continuation:
                await conn.execute("""INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input,timeout_s,run_at)
                    VALUES($1,$2,'competitor_match',$3::jsonb,45,now()+interval '1 second') ON CONFLICT(id) DO NOTHING""",
                    continuation, tenant, json.dumps({'root_job_id': str(root), 'previous_job_id': str(current), '_batch_discovery': True}))
            await conn.execute('UPDATE agent_tiger.jobs SET result=$3::jsonb WHERE tenant_id=$1 AND id=$2',
                               tenant, current, json.dumps(result))
    return result
