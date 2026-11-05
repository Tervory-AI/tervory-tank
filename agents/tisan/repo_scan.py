"""R5 repo receipt for an immutable build archive, through Tank only."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

import httpx
try:
    from agents.tisan.storage import atomic_json
except ModuleNotFoundError:
    from storage import atomic_json


TOOLS = {'scan.secrets', 'scan.dependencies', 'scan.static', 'scan.iac'}


def headers(tenant):
    return {'X-Tank-Key': os.environ.get('TANK_KEY', ''), 'X-Tervory-Tenant': tenant,
            'X-Tervory-Region': os.environ.get('TANK_REGION', 'us-east')}


async def inspect(http, tenant, scan_id, digest):
    response = await http.get(os.environ.get('TANK_URL', 'http://tank:8000').rstrip('/') +
        '/v1/command/tisan/pipeline/repo-scan/' + str(UUID(scan_id)),
        params={'tenant_id': tenant}, headers=headers(tenant), timeout=30, follow_redirects=False)
    response.raise_for_status()
    row = response.json()
    if not isinstance(row, dict):
        raise ValueError('scan result unavailable')
    if row.get('scan_id') != scan_id:
        raise ValueError('scan identity changed')
    if row.get('status') in {'pending', 'running'}:
        return None
    critical = row.get('critical')
    if (row.get('status') != 'complete' or row.get('ref') != 'sha256:' + digest
            or type(critical) is not int or critical < 0 or row.get('scan_complete') is not True
            or row.get('leaked') is not False or not TOOLS.issubset(set(row.get('tools') or []))):
        raise ValueError('repo scan incomplete')
    return {'name': 'radix.repo', 'ok': critical == 0, 'tenant_id': tenant,
            'scan_id': scan_id, 'archive_sha256': digest, 'critical': critical,
            'scan_complete': True, 'summary': f'{scan_id}: {critical} critical findings'}


async def check(archive: Path, tenant: str, *, http=None):
    failed = {'name': 'radix.repo', 'ok': False, 'summary': 'repo scan unavailable'}
    try:
        tenant = str(UUID(tenant))
        if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 32 * 1024 * 1024:
            return failed
        raw = archive.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        failed['archive_sha256'] = digest
        async def run(client):
            response = await client.post(os.environ.get('TANK_URL', 'http://tank:8000').rstrip('/') +
                '/v1/command/tisan/pipeline/repo-scan', headers=headers(tenant),
                json={'tenant_id': tenant, 'source': base64.b64encode(raw).decode('ascii'), 'sha256': digest},
                timeout=60, follow_redirects=False)
            response.raise_for_status()
            scan_id = str(UUID(response.json()['scan_id']))
            failed['scan_id'] = scan_id
            deadline = asyncio.get_running_loop().time() + 390
            while asyncio.get_running_loop().time() < deadline:
                result = await inspect(client, tenant, scan_id, digest)
                if result is not None:
                    return result
                await asyncio.sleep(2)
            return failed
        if http is not None:
            return await run(http)
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
            return await run(client)
    except (OSError, ValueError, KeyError, TypeError, httpx.HTTPError):
        return failed


async def attach(result, tenant, *, http=None):
    """Only server-side handler results can add a measured repo receipt."""
    if result.get('ok') is not True or not result.get('archive'):
        return result
    archive = Path(result['archive'])
    check_result = await check(archive, tenant, http=http)
    result = {**result, 'checks': [*result.get('checks', []), check_result],
              'results': [*result.get('results', []), {k: check_result[k] for k in ('name', 'ok', 'summary')}]}

    result['summary'] = check_result['summary']
    if check_result['ok'] is not True:
        result.update(ok=False, detail='Failed checks: radix.repo')
    # Publish reads this same sidecar and independently verifies the archive hash.
    atomic_json(archive.with_suffix('').with_suffix('.json'), result)
    return result


def receipt(build, tenant, digest):
    rows = [c for c in build.get('checks', []) if c.get('name') == 'radix.repo']
    if (len(rows) != 1 or rows[0].get('ok') is not True or rows[0].get('tenant_id') != tenant
            or rows[0].get('archive_sha256') != digest or rows[0].get('scan_complete') is not True
            or type(rows[0].get('critical')) is not int or rows[0]['critical'] != 0):
        raise ValueError('repo scan required')
    UUID(rows[0]['scan_id'])
    return rows[0]


async def promotion_gate(journal, root: Path, http, tenant, site, expected):
    """Recheck R5 for the exact archive that produced the staged commit."""
    with journal.connect() as db:
        row = db.execute("SELECT details FROM operations WHERE tenant=? AND site=? "
            "AND action='publish' AND result='succeeded' AND json_extract(details,'$.commit')=? "
            "ORDER BY rowid DESC LIMIT 1", (tenant, site, expected)).fetchone()
    if row is None:
        raise ValueError('scanned staging build required')
    details = json.loads(row['details'])
    number = int(details['expected'].removeprefix('build:'))
    try:
        from agents.tisan import publish
    except ModuleNotFoundError:
        import publish
    build = publish.stored_build(root, tenant, site, number)['manifest']
    check_row = next(c for c in build['checks'] if c['name'] == 'radix.repo')
    verified = await inspect(http, tenant, check_row['scan_id'], check_row['archive_sha256'])
    if verified is None:
        raise ValueError('repo scan did not complete')
    return verified
