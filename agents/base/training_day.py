"""Cloud-local, restartable official-list execution using Base's existing worker."""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import date
import gzip
import hashlib
import ipaddress
import json
import os
import re
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
import uuid

import asyncpg
import httpx

if __package__:
    from .engines.ffl.reference import MAX_BYTES, official_url, parse_file, refresh
    from .engines.ffl import reference_source
else:
    from engines.ffl.reference import MAX_BYTES, official_url, parse_file, refresh
    from engines.ffl import reference_source
from pipeline import order_states
from room import SkillClient, _run_batch, ensure_tables, insert_batch
from sources.vendor_ledger import PLATFORM_TENANT, decoded
from configuration import missing_settings, not_configured


def local_service(url):
    host = urlsplit(url).hostname
    try:
        local = ipaddress.ip_address(host or '').is_loopback
    except ValueError:
        local = host == 'localhost'
    if not local:
        raise ValueError('Training services must run on cloud loopback')
    return url


def write_receipt(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            name = Path(stream.name)
            json.dump(value, stream, sort_keys=True, indent=2, default=str)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def retain_source(directory, snapshot):
    directory = Path(directory)
    name = snapshot['sha256'] + '.json'
    if not re.fullmatch(r'[a-f0-9]{64}\.json', name):
        raise ValueError('Invalid source cache identity')
    path = directory / 'sources' / name
    write_receipt(path, snapshot)
    write_receipt(directory / 'active-source.json', {
        'snapshot': name, 'cache_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})


def retained_source(directory):
    directory = Path(directory)
    pointer = directory / 'active-source.json'
    if not pointer.exists():
        return None
    if pointer.is_symlink():
        raise ValueError('Invalid source cache pointer')
    active = json.loads(pointer.read_text())
    if not re.fullmatch(r'[a-f0-9]{64}\.json', active['snapshot']):
        raise ValueError('Invalid source cache identity')
    path = directory / 'sources' / active['snapshot']
    if path.is_symlink():
        raise ValueError('Invalid source cache file')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != active['cache_sha256']:
        raise ValueError('The retained official source changed')
    snapshot = json.loads(data)
    if snapshot['sha256'] + '.json' != active['snapshot']:
        raise ValueError('Source cache does not match the official source identity')
    return snapshot


def plan(snapshot, *, states=None, today=None):
    today = today or date.today()
    published = date.fromisoformat(str(snapshot['published_on']))
    configured = os.environ.get('BASE_REFERENCE_FILE_URL', '').strip()
    trusted = official_url(snapshot['source_url'])
    if configured and snapshot['source_url'] == configured:
        reference_source.validate(configured)
        trusted = True
    if not trusted or not 0 <= (today - published).days <= 90:
        raise ValueError('A current dated official ATF source is required')
    stamp = re.search(r'(?<!\d)(\d{2})(\d{2})-ffl-list', snapshot['source_url'])
    if stamp is None or date(2000 + int(stamp[2]), int(stamp[1]), 1) != published:
        raise ValueError('Publication date must match the dated official file')
    if not re.fullmatch('[a-f0-9]{64}', snapshot['sha256']):
        raise ValueError('An exact source SHA256 is required')
    groups = defaultdict(list)
    seen = set()
    for row in snapshot['rows']:
        if row['licence_key'] in seen:
            raise ValueError('Duplicate official licence identity')
        seen.add(row['licence_key'])
        if states is None or row['state'] in states:
            meta = {key: row[key] for key in ('licence_key', 'licence_number', 'state', 'licence_type', 'name')}
            meta.update(source_url=snapshot['source_url'], published_on=str(published),
                        checked_at=snapshot.get('checked_at') or str(today))
            groups[row['state']].append({**row['raw'], '_base_reference': meta})
    if states and set(states) != set(groups):
        raise ValueError('A selected state has no official records')
    if not groups:
        raise ValueError('No official records')
    identity = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(
        [PLATFORM_TENANT, snapshot['source_url'], snapshot['sha256'], str(published)], separators=(',', ':')))
    return {'id': str(identity), 'source_url': snapshot['source_url'], 'sha256': snapshot['sha256'],
            'published_on': str(published), 'source_records': len(snapshot['rows']),
            'records': sum(map(len, groups.values())),
            'states': [{'state': state, 'count': len(rows), 'task_id': str(uuid.uuid5(identity, state)), 'rows': rows}
                       for state, rows in order_states(groups)]}


async def state_task(pool, run, state, refs, versions):
    tenant = uuid.UUID(PLATFORM_TENANT)
    identity = uuid.UUID(state['task_id'])
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', 'base-training-state:' + str(identity))
        row = await conn.fetchrow('SELECT input,status FROM agent_base.tasks WHERE id=$1 AND tenant_id=$2', identity, tenant)
        if row is None:
            await insert_batch(conn, tenant, 'base-training', 'ATF ' + run['id'] + ' ' + state['state'],
                               state['rows'], '', False, 'ffl', 8, None, task_id=identity)
            row = await conn.fetchrow('SELECT input,status FROM agent_base.tasks WHERE id=$1 AND tenant_id=$2', identity, tenant)
            cfg = decoded(row['input'])
            cfg.update(training_run=run['id'], source_sha256=run['sha256'], refs=refs,
                       versions=versions, engine_data_version=versions['ffl.profile'])
            # The driver owns these tasks. The ordinary queued-job worker must
            # not race a second pipeline against the same licence records.
            await conn.execute("UPDATE agent_base.tasks SET task_type='base.training',input=$3::jsonb WHERE id=$1 AND tenant_id=$2",
                               identity, tenant, json.dumps(cfg))
        else:
            cfg = decoded(row['input'])
            if cfg.get('training_run') != run['id'] or cfg.get('source_sha256') != run['sha256']:
                raise ValueError('Existing state task belongs to another source')
        return identity, cfg, row['status']


async def execute(pool, skills, snapshot, directory, *, states=None, today=None):
    run = plan(snapshot, today=today)
    if states is not None and (not states or not states <= {state['state'] for state in run['states']}):
        raise ValueError('A selected state has no official records')
    directory = Path(directory) / run['id']
    async with pool.acquire() as owner:
        locked = await owner.fetchval('SELECT pg_try_advisory_lock(hashtextextended($1,0))', 'base-training:' + run['id'])
        if not locked:
            raise RuntimeError('This source run already has a cloud worker')
        try:
            async with pool.acquire() as conn:
                await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_base')
                await ensure_tables(conn, recover=False)
            versions, refs = await skills.pin(False, 'ffl')
            if any(int(versions[skill].split('.')[0]) < 2 for skill in ('base.extract', 'base.business_data')):
                raise ValueError('Approve the existing code-only extract and business-data skills before training')
            manifest = {**run, 'states': [{key: value for key, value in state.items() if key != 'rows'} for state in run['states']],
                        'refs': refs, 'versions': versions}
            existing = directory / 'source.json'
            if existing.exists():
                saved = json.loads(existing.read_text())
                if saved != manifest:
                    raise ValueError('The source or approved skill versions changed; resume requires the pinned run')
            write_receipt(existing, manifest)
            receipts = []
            for state in run['states']:
                if states is not None and state['state'] not in states:
                    continue
                identity, cfg, status = await state_task(pool, run, state, refs, versions)
                if cfg['versions'] != versions:
                    raise ValueError('State skills differ from the pinned run')
                if status != 'done':
                    direct = skills.bind(versions, False, PLATFORM_TENANT)

                    async def code_only(skill, payload):
                        return await direct(skill, {**payload, '_base_brain_free': True})

                    await _run_batch(pool, identity, cfg, code_only)
                async with pool.acquire() as conn:
                    task = await conn.fetchrow('SELECT status,input FROM agent_base.tasks WHERE id=$1 AND tenant_id=$2',
                                               identity, uuid.UUID(PLATFORM_TENANT))
                    counts = await conn.fetchrow(
                        "SELECT count(*) AS total,count(*) FILTER (WHERE status='done') AS done,"
                        "count(*) FILTER (WHERE status='failed') AS failed FROM agent_base.records WHERE task_id=$1 AND tenant_id=$2",
                        identity, uuid.UUID(PLATFORM_TENANT))
                final = decoded(task['input'])
                receipt = {'state': state['state'], 'task_id': str(identity), 'source_sha256': run['sha256'],
                           'status': task['status'], **dict(counts), 'model_spend': final.get('model_spend'), 'refs': refs}
                write_receipt(directory / (state['state'] + '.json'), receipt)
                if counts['total'] != state['count'] or counts['done'] + counts['failed'] != counts['total'] or task['status'] != 'done':
                    raise RuntimeError('State is not complete; restart this command to resume its queued records')
                if final.get('model_spend') != 0:
                    raise RuntimeError('Code-only run returned a nonzero model receipt')
                receipts.append(receipt)
            from base_gold.build import join_list, publish
            from base_gold.gold_sources import candidates
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT raw,passes->'2b'->'gold_observation' AS observation FROM agent_base.records "
                    "WHERE tenant_id=$1 AND status='done' AND passes->'2b' ? 'gold_observation' "
                    "AND task_id IN (SELECT id FROM agent_base.tasks WHERE tenant_id=$1 AND input->>'training_run'=$2)",
                    uuid.UUID(PLATFORM_TENANT), run['id'])
            observed = [{'raw': decoded(row['raw']), 'observation': decoded(row['observation'])} for row in rows]
            matches = await join_list([row['raw'] for row in snapshot['rows']], observed,
                skills.bind(versions, False, PLATFORM_TENANT), source_url=run['source_url'],
                snapshot=date.fromisoformat(run['published_on']), today=today or date.today())
            publish(matches, region='us-east', data_dir=directory)
            gold = candidates(matches, region='us-east', today=today or date.today())
            write_receipt(directory / 'gold-candidates.json', gold)
            result = {'run_id': run['id'], 'source_sha256': run['sha256'], 'states': len(receipts),
                      'records': sum(item['total'] for item in receipts),
                      'done': sum(item['done'] for item in receipts), 'failed': sum(item['failed'] for item in receipts),
                      'model_spend': 0, 'receipts': [item['state'] + '.json' for item in receipts],
                      'complete': len(receipts) == len(run['states']),
                      'gold_candidates': len(gold), 'gold_file': 'gold-candidates.json'}
            write_receipt(directory / 'result.json', result)
            return result
        finally:
            await owner.execute('SELECT pg_advisory_unlock(hashtextextended($1,0))', 'base-training:' + run['id'])


async def main(args):
    if getattr(args, 'dry_run', False):
        from base_gate4_dry_run import run
        result = await run(Path(args.work_dir))
        print(json.dumps(result, sort_keys=True))
        return result
    missing = missing_settings(('DATABASE_URL', 'TANK_KEY'))
    if missing:
        result = not_configured(missing)
        print(json.dumps(result, sort_keys=True))
        return result
    database = local_service(os.environ['DATABASE_URL'])
    tank = local_service(os.environ.get('TANK_URL', 'http://127.0.0.1:8000'))
    if os.environ.get('TANK_REGION', 'us-east') != 'us-east':
        raise ValueError('The ATF run belongs to the US region')
    async with httpx.AsyncClient(follow_redirects=False) as http:
        if args.reference:
            path = Path(args.reference)
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rb') as stream:
                data = stream.read(MAX_BYTES + 1)
            snapshot = {'rows': parse_file(data), 'source_url': args.source_url,
                        'published_on': args.published_on, 'sha256': hashlib.sha256(data).hexdigest()}
        else:
            snapshot = retained_source(args.work_dir)
            if snapshot is None:
                snapshot = await refresh(http, None, date.today())
        plan(snapshot)
        retain_source(args.work_dir, snapshot)
        pool = await asyncpg.create_pool(database, min_size=1, max_size=4)
        try:
            # Public downloads retain the managed proxy. Loopback Tank traffic
            # stays on this cloud machine and carries the room key only here.
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as local:
                skills = SkillClient(local, tank, os.environ.get('TANK_KEY', ''))
                result = await execute(pool, skills, snapshot, args.work_dir, states=set(args.state) if args.state else None)
            print(json.dumps(result, sort_keys=True))
        finally:
            await pool.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', help='Optional current saved official TXT/CSV, optionally gzip compressed')
    parser.add_argument('--source-url', default='')
    parser.add_argument('--published-on', default='')
    parser.add_argument('--state', action='append', help='Explicit jurisdiction selection; default is the complete file')
    parser.add_argument('--work-dir', required=True)
    parser.add_argument('--dry-run', action='store_true', help='Replay the recorded smallest state and every scheduled job offline')
    options = parser.parse_args()
    if options.reference and (not options.source_url or not options.published_on):
        parser.error('--reference requires --source-url and --published-on')
    asyncio.run(main(options))
