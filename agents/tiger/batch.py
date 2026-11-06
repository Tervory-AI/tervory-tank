"""Resumable product-page handoff. Industry-specific fields are supplied by Base."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import fcntl
import stat
from uuid import UUID, uuid5
from urllib.parse import urlsplit

import httpx


def plan(rows: list[dict], tenant: str) -> list[dict]:
    tenant = str(UUID(tenant))
    seen, result = set(), []
    for row in rows:
        if row.get('tenant_id', tenant) != tenant:
            raise ValueError('Source belongs to another tenant')
        ident, group = row.get('id') or row.get('record_id'), row.get('state', '')
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError('Source needs a unique record id')
        if not isinstance(group, str):
            raise ValueError('Source group must be text')
        seen.add(ident)
        urls = row.get('product_urls', [])
        if not isinstance(urls, list) or any(not isinstance(url, str) or not url for url in urls):
            raise ValueError('Product URLs must be a list of URLs')
        website = row.get('website') or ''
        if isinstance(website, dict):
            website = website.get('value') or ''
        if not isinstance(website, str):
            raise ValueError('Website must be a URL')
        for url in urls + ([website] if website else []):
            parsed = urlsplit(url)
            if url != url.strip() or parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Product source must be an HTTP URL without credentials')
        # A business homepage is not a product. Missing product evidence stays
        # explicit, rather than inventing a product price from a Base website.
        result.append({'id': ident, 'state': group, 'product_urls': sorted(set(urls)), 'website': website})
    counts = Counter(row['state'] for row in result)
    return sorted(result, key=lambda row: (counts[row['state']], row['state'], row['id']))


def job_id(tenant: str, batch: str, record: str, url: str) -> UUID:
    return uuid5(UUID(batch), json.dumps([str(UUID(tenant)), record, url], separators=(',', ':')))


def discovery_id(tenant: str, batch: str, record: str, url: str) -> UUID:
    return uuid5(job_id(tenant, batch, record, url), 'discovery')


# Three existing worker attempts of 120 seconds, plus its 30-second backoff.
JOB_WAIT_S = 3 * (120 + 30)


async def completed(client, tenant, job, expected, sleep, progress=None):
    async with asyncio.timeout(JOB_WAIT_S):
        return await _completed(client, tenant, job, expected, sleep, progress)


async def _completed(client, tenant, job, expected, sleep, progress):
    seen = set()
    while True:
        if job.get('tenant_id') != tenant or job.get('id') != expected:
            raise ValueError('Batch job receipt does not match the source')
        if progress:
            progress(expected)
        if job['status'] in {'queued', 'running'}:
            await sleep(2)
        elif job['status'] != 'done':
            raise RuntimeError('Batch job did not finish')
        else:
            continuation = (job.get('result') or {}).get('continuation_id')
            if not continuation:
                return job
            if continuation in seen or continuation == expected:
                raise ValueError('Invalid discovery continuation')
            seen.add(expected)
            expected = str(UUID(continuation))
        response = await client.get('/jobs/' + expected, params={'tenant_id': tenant}, timeout=60)
        response.raise_for_status()
        job = response.json()


class Checkpoint:
    def __init__(self, path: Path, tenant: str, batch: str, rows: list[dict]):
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Checkpoint must not use symbolic links')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(self.fd).st_mode):
                raise ValueError('Checkpoint must be a regular file')
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fchmod(self.fd, 0o600)
            self.db = sqlite3.connect(path)
        except BaseException:
            os.close(self.fd)
            raise
        try:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('CREATE TABLE IF NOT EXISTS source (id INTEGER PRIMARY KEY CHECK(id=1), binding TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS receipts (record TEXT PRIMARY KEY, receipt TEXT NOT NULL)')
            binding = json.dumps([str(UUID(tenant)), str(UUID(batch)), rows], sort_keys=True, separators=(',', ':'))
            digest = hashlib.sha256(binding.encode()).hexdigest()
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO source VALUES (1, ?)', (digest,))
            if self.db.execute('SELECT binding FROM source').fetchone()[0] != digest:
                raise ValueError('Checkpoint source, batch or tenant changed')
        except BaseException:
            self.close()
            raise

    def get(self, record: str):
        row = self.db.execute('SELECT receipt FROM receipts WHERE record=?', (record,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, record: str, receipt: dict):
        with self.db:
            self.db.execute('INSERT INTO receipts VALUES (?, ?) ON CONFLICT(record) DO UPDATE SET receipt=excluded.receipt',
                            (record, json.dumps(receipt, sort_keys=True)))

    def close(self):
        self.db.close()
        os.close(self.fd)


async def run(rows, tenant, batch, checkpoint, client, *, sleep=asyncio.sleep, retry_failed=False):
    ordered = plan(rows, tenant)
    state = Checkpoint(Path(checkpoint), tenant, batch, ordered)
    receipts = []
    try:
        for row in ordered:
            receipt = state.get(row['id'])
            if receipt and receipt['status'] == 'complete':
                receipts.append(receipt)
                continue
            receipt = receipt or {'record_id': row['id'], 'state': row['state'], 'tenant_id': tenant,
                                  'batch_id': batch, 'status': 'running', 'pages': []}
            urls = row['product_urls']
            if not urls and row['website']:
                if 'discovery' not in receipt:
                    ident = str(discovery_id(tenant, batch, row['id'], row['website']))
                    current = receipt.get('discovery_cursor', ident)
                    if current != ident and not retry_failed:
                        response = await client.get('/jobs/' + current, params={'tenant_id': tenant}, timeout=60)
                    else:
                        current = ident
                        response = await client.post('/batch/discover', json={'tenant_id': tenant, 'batch_id': batch,
                            'record_id': row['id'], 'url': row['website'], 'retry_failed': retry_failed}, timeout=60)
                    response.raise_for_status()
                    def progress(current):
                        receipt['discovery_cursor'] = current
                        state.save(row['id'], receipt)
                    discovered = await completed(client, tenant, response.json(), current, sleep, progress)
                    result = discovered.get('result') or {}
                    if result.get('status') != 'completed' or not isinstance(result.get('product_urls'), list):
                        raise ValueError('Discovery has no completed source receipt')
                    receipt['discovery'] = {'job_id': ident, 'final_job_id': discovered['id'],
                        'product_urls': result['product_urls'], 'sites': result.get('sites', []),
                        'skill_receipts': result.get('skill_receipts', [])}
                    state.save(row['id'], receipt)
                urls = receipt['discovery']['product_urls']
            done = {page['url'] for page in receipt['pages']}
            for url in urls:
                if url in done:
                    continue
                ident = str(job_id(tenant, batch, row['id'], url))
                response = await client.post('/batch/check', json={
                    'tenant_id': tenant, 'batch_id': batch, 'record_id': row['id'], 'url': url, 'retry_failed': retry_failed}, timeout=60)
                response.raise_for_status()
                job = await completed(client, tenant, response.json(), ident, sleep)
                result = job.get('result') or {}
                observation = result.get('observation') or {}
                if result.get('status') not in {'observed', "can't read", 'error', 'blocked', 'skipped'}:
                    raise ValueError('Batch job has no reading outcome')
                if result['status'] != 'skipped' and not (observation.get('id') and observation.get('ts')):
                    raise ValueError('Batch job has no saved attempt')
                if observation and (observation.get('tenant_id') != tenant or observation.get('url') != url):
                    raise ValueError('Observation belongs to another source')
                receipt['pages'].append({'url': url, 'job_id': ident, 'status': result.get('status'),
                    'observation_id': observation.get('id'), 'observed_at': observation.get('ts'),
                    'method': observation.get('method'), 'price': observation.get('price'),
                    'currency': observation.get('currency'), 'availability': observation.get('availability'),
                    'source_receipt': result.get('receipt'), 'skill_receipts': result.get('skill_receipts', []), 'model_calls': 0})
                state.save(row['id'], receipt)
            receipt['status'] = 'complete'
            receipt['source_status'] = ('checked' if receipt['pages'] and all(page['status'] == 'observed' for page in receipt['pages'])
                                        else 'attempted' if urls else 'no_product_urls')
            if not urls and any(site.get('status') != 'completed' or site.get('warnings')
                                for site in receipt.get('discovery', {}).get('sites', [])):
                receipt['source_status'] = 'source_unavailable'
            state.save(row['id'], receipt)
            receipts.append(receipt)
        return receipts
    finally:
        state.close()


async def main(args):
    rows = load_input(Path(args.input))
    tenant, batch = str(UUID(args.tenant)), str(UUID(args.batch))
    ordered = plan(rows, tenant)
    if getattr(args, 'smallest_state', False) and ordered:
        rows = [row for row in ordered if row['state'] == ordered[0]['state']]
        ordered = plan(rows, tenant)
    if getattr(args, 'dry_run', False):
        result = {'dry_run': True, 'records': len(ordered), 'states': dict(Counter(row['state'] for row in ordered)),
                  'product_pages': sum(len(row['product_urls']) for row in ordered),
                  'discovery_sites': sum(bool(row['website']) and not row['product_urls'] for row in ordered),
                  'missing_sources': sum(not row['website'] and not row['product_urls'] for row in ordered),
                  'settings': [] if os.environ.get('TIGER_BATCH_URL', '').strip() else ['TIGER_BATCH_URL']}
        if getattr(args, 'responses', None):
            recorded = json.loads(Path(args.responses).read_text())
            async def replay(request):
                if not recorded:
                    raise ValueError('No recorded response for this request')
                expected = recorded.pop(0)
                if request.method != expected['method'] or request.url.raw_path.decode() != expected['path']:
                    raise ValueError('Recorded request does not match')
                if request.method == 'POST' and json.loads(request.content) != expected['body']:
                    raise ValueError('Recorded request body does not match')
                return httpx.Response(expected['status'], json=expected['json'])
            async def no_wait(_):
                pass
            # Dry-run replay never opens the operator's real checkpoint or
            # writes observed prices into live receipts.
            with tempfile.TemporaryDirectory(prefix='tiger-dry-') as folder:
                async with httpx.AsyncClient(base_url='https://placeholder.invalid', transport=httpx.MockTransport(replay)) as client:
                    receipts = await run(rows, tenant, batch, Path(folder)/'checkpoint', client,
                                         sleep=no_wait, retry_failed=args.retry_failed)
                    resumed = await run(rows, tenant, batch, Path(folder)/'checkpoint', client, sleep=no_wait)
                    if resumed != receipts or recorded:
                        raise ValueError('Recorded replay or resume is incomplete')
            result.update(replayed=len(receipts), resume_verified=True)
        print(json.dumps(result, sort_keys=True))
        return result
    if not os.environ.get('TIGER_BATCH_URL', '').strip():
        result = {'status': 'not_configured', 'settings': ['TIGER_BATCH_URL']}
        print(json.dumps(result))
        return result
    if getattr(args, 'responses', None):
        raise ValueError('Recorded responses require dry-run')
    if not os.environ.get('TANK_KEY', '').strip():
        result = {'status': 'not_configured', 'settings': ['TANK_KEY']}
        print(json.dumps(result))
        return result
    async with httpx.AsyncClient(base_url=os.environ['TIGER_BATCH_URL'], follow_redirects=False, timeout=60,
                                 headers={'X-Tank-Key': os.environ['TANK_KEY'], 'X-Tenant-ID': tenant}) as client:
        receipts = await run(rows, str(UUID(args.tenant)), str(UUID(args.batch)), args.checkpoint, client,
                             retry_failed=args.retry_failed)
    output = Path(args.receipts)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=output.parent, prefix='.tiger-receipts-', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(''.join(json.dumps(row, sort_keys=True) + '\n' for row in receipts))
    temporary.replace(output)


def load_input(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        if path.suffix.lower() == '.csv':
            return list(csv.DictReader(stream))
        return [json.loads(line) for line in stream if line.strip()]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('input', 'tenant', 'batch', 'checkpoint', 'receipts'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--responses', help='Local recorded HTTP responses for offline dry-run replay')
    parser.add_argument('--smallest-state', action='store_true')
    try:
        asyncio.run(main(parser.parse_args()))
    except Exception:
        raise SystemExit('Batch incomplete; saved progress can be resumed. Source details are withheld.') from None
