#!/usr/bin/env python3
"""Local synthetic Rig rooms only. No Coolify, stores, models or cloud k6."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from uuid import uuid4

K6_IMAGE = 'grafana/k6:0.54.0@sha256:32000aaa40b848add83425ed7cc77535c343ca473498b0bd29464d00fdca6c79'
POSTGRES_IMAGE = 'postgres:16.15'
ROOT = Path(__file__).resolve().parents[2]


def command(args, *, input=None, check=True):
    result = subprocess.run(args, input=input, text=True, capture_output=True, check=False, timeout=300)
    if check and result.returncode:
        raise RuntimeError('Test command failed: ' + args[0] + '\n' + result.stderr[-4000:])
    return result.stdout


def memory_bytes(value):
    match = re.fullmatch(r'\s*([\d.]+)\s*([KMGT]?i?B)\s*', value)
    if not match:
        raise ValueError('Unrecognized Docker memory unit')
    units = {'B': 1, 'kB': 1000, 'KB': 1000, 'MB': 1000**2, 'GB': 1000**3,
             'TB': 1000**4, 'KiB': 1024, 'MiB': 1024**2, 'GiB': 1024**3, 'TiB': 1024**4}
    return int(float(match[1]) * units[match[2]])


def summarize(raw, samples, rooms):
    """Use k6's measured percentiles. Never estimate a clients-per-box figure."""
    metrics = raw['metrics']
    result = {'rooms': rooms, 'capacity_claim': None,
              'search_p95_ms': metrics['rig_search_ms']['values']['p(95)'],
              'quote_p95_ms': metrics['rig_quote_ms']['values']['p(95)'],
              'failed_checks': metrics['checks']['values']['fails'],
              'http_failure_rate': metrics['http_req_failed']['values']['rate'],
              'memory_metric': 'Docker working set, sampled; bytes; app plus private database',
              'samples': samples, 'per_room': []}
    if not samples or any(len(sample['containers']) != rooms * 2 or
            len({row['name'] for row in sample['containers']}) != rooms * 2
            for sample in samples):
        raise ValueError('Memory samples must include every room application and database')
    result['max_total_room_memory_bytes'] = max(sum(row['bytes'] for row in sample['containers']) for sample in samples)
    for index in range(rooms):
        tag = str(index + 1)
        result['per_room'].append({'room': index + 1,
            'search_p95_ms': metrics[f'rig_search_ms{{room:{tag}}}']['values']['p(95)'],
            'quote_p95_ms': metrics[f'rig_quote_ms{{room:{tag}}}']['values']['p(95)']})
    timings = [result['search_p95_ms'], result['quote_p95_ms']] + [
        row[key] for row in result['per_room'] for key in ('search_p95_ms', 'quote_p95_ms')]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in timings):
        raise ValueError('Measured search/quote percentiles are missing or invalid')
    if result['failed_checks'] or result['http_failure_rate']:
        raise ValueError('k6 reported failed checks or HTTP requests; inspect raw-k6.json')
    return result


def run(root, count, duration, image, *, docker=command, ready=None, launch=None):
    """The injectable Docker/HTTP boundaries let CI replay a recorded fixture run."""
    root = Path(root).resolve()
    folder = root.name
    if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]*', folder) or count < 1:
        raise ValueError('Use a named checkout and at least one room')
    os.environ['TMPDIR'] = str(root / '.tmp')
    output = root / '.tmp' / ('rig-room-load-' + uuid4().hex[:10])
    output.mkdir(parents=True)
    os.chmod(output, 0o777)  # k6's unprivileged user writes only synthetic results here.
    suffix = uuid4().hex[:8]
    shared = f'{folder}-load-{suffix}'
    started, networks, samples = [], [], []
    stop = threading.Event()
    monitor = None
    process = None
    errors = []
    manifest = []
    k6_name = shared + '-k6'
    script = root / 'tests/load/rig_rooms.js'

    def sample():
        rows = docker(['docker', 'stats', '--no-stream', '--format', '{{json .}}', *started])
        values = [json.loads(line) for line in rows.splitlines() if line]
        samples.append({'elapsed_seconds': time.monotonic() - began,
            'containers': [{'name': row['Name'], 'bytes': memory_bytes(row['MemUsage'].split('/')[0])} for row in values]})

    def monitor_memory():
        while not stop.wait(2):
            try:
                sample()
            except Exception as exc:
                errors.append(type(exc).__name__)
                return

    def wait_ready(name):
        deadline = time.monotonic() + 180
        code = "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); print('ready')"
        while time.monotonic() < deadline:
            if 'ready' in docker(['docker', 'exec', name, 'python', '-c', code], check=False):
                return
            time.sleep(0.2)
        raise RuntimeError('Fixture room did not become ready')

    try:
        networks.append(shared)
        docker(['docker', 'network', 'create', '--internal', '--label', 'tervory.test=1', shared])
        for index in range(count):
            name = shared + '-room-' + str(index + 1)
            database = name + '-pg'
            private = name + '-private'
            tenant = str(uuid4())
            networks.append(private)
            docker(['docker', 'network', 'create', '--internal', '--label', 'tervory.test=1', private])
            started.append(database)
            docker(['docker', 'run', '--rm', '-d', '--label', 'tervory.test=1', '--name', database,
                '--network', private, '--network-alias', 'database', '--memory', '256m', '--cpus', '0.25',
                '--tmpfs', '/var/lib/postgresql/data:rw,size=256m',
                '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', POSTGRES_IMAGE])
            # Wait for private Postgres before the production lifespan starts.
            deadline = time.monotonic() + 120
            while 'accepting connections' not in docker(['docker', 'exec', database, 'pg_isready', '-U', 'postgres'], check=False):
                if time.monotonic() > deadline:
                    raise RuntimeError('Fixture Postgres did not become ready')
                time.sleep(0.2)
            started.append(name)
            docker(['docker', 'run', '--rm', '-d', '--label', 'tervory.test=1', '--name', name,
                '--network', private, '--memory', '384m', '--cpus', '0.5', '--pids-limit', '128',
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000',
                '--tmpfs', '/data:rw,nosuid,nodev,size=64m,uid=1000,gid=1000',
                '-v', str(root / 'tests') + ':/validation:ro',
                '-e', 'DATABASE_URL=postgresql://postgres@database:5432/postgres',
                '-e', 'RIG_ROOM_TENANT=' + tenant, '-e', 'DATA_DIR=/data',
                '-e', 'RIG_TRUSTED_PROXY_CIDRS=127.0.0.0/8', '-e', 'RIG_FORGE_TRELLIS_ENABLED=false',
                '-e', 'RIG_SAMPLE_ORIGIN=http://rig-load.fixture',
                '-e', 'TANK_URL=http://fixture-tank-unavailable:8000', image])
            docker(['docker', 'network', 'connect', shared, name])
            (ready or wait_ready)(name)
            seed = '''import asyncio, os, sys, asyncpg
sys.path.insert(0, '/validation')
from fixtures.rig_quote_sample import seed
from rigbox.store import PgStore
async def main():
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'])
    try:
        await seed(PgStore(pool), os.environ['RIG_ROOM_TENANT'], sample=False)
    finally:
        await pool.close()
asyncio.run(main())
'''
            docker(['docker', 'exec', '-i', name, 'python', '-'], input=seed)
            manifest.append({'room': index + 1, 'url': 'http://' + name + ':8000',
                             'tenant_id': tenant, 'key': 'rk_pub_neutral_sample'})
        (output / 'rooms.json').write_text(json.dumps(manifest))
        began = time.monotonic()
        sample()
        monitor = threading.Thread(target=monitor_memory, daemon=True)
        monitor.start()
        args = ['docker', 'run', '--rm', '--label', 'tervory.test=1', '--name', k6_name,
            '--platform', 'linux/amd64', '--network', shared, '--memory', '256m', '--cpus', '1',
            '-v', str(script) + ':/test.js:ro', '-v', str(output) + ':/results',
            '-e', 'K6_NO_USAGE_REPORT=true', '-e', 'DURATION=' + duration,
            K6_IMAGE, 'run', '/test.js']
        with (output / 'k6.log').open('w') as log:
            process = (launch or subprocess.Popen)(args, stdout=log, stderr=subprocess.STDOUT)
            seconds = int(duration[:-1]) * (60 if duration.endswith('m') else 1)
            code = process.wait(timeout=seconds + 180)
        stop.set()
        monitor.join(timeout=10)
        sample()
        if code or errors:
            raise RuntimeError('Load measurement failed; inspect ' + str(output))
        raw = json.loads((output / 'raw-k6.json').read_text())
        result = {**summarize(raw, samples, count), 'k6_image': K6_IMAGE, 'room_image': image,
                  'git_head': docker(['git', '-C', str(root), 'rev-parse', 'HEAD']).strip(),
                  'duration': duration, 'fixture': 'neutral Core catalogue, no models/email/stores',
                  'shared_workers_included': False}
        (output / 'measurement.json').write_text(json.dumps(result, indent=2))
        return output, result
    except Exception as exc:
        (output / 'failure.json').write_text(json.dumps({'error': type(exc).__name__, 'containers': started, 'networks': networks}))
        raise
    finally:
        stop.set()
        if monitor:
            monitor.join(timeout=10)
        cleanup_pending = []
        def cleanup(args):
            try:
                docker(args)
            except Exception as exc:
                if 'No such container' not in str(exc) and 'not found' not in str(exc):
                    cleanup_pending.append(args)
        if process and process.poll() is None:
            cleanup(['docker', 'stop', '-t', '2', k6_name])
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        for name in reversed(started):
            cleanup(['docker', 'stop', '-t', '3', name])
        for network in reversed(networks):
            cleanup(['docker', 'network', 'rm', network])
        if cleanup_pending:
            (output / 'cleanup-pending.json').write_text(json.dumps(cleanup_pending, indent=2))
            raise RuntimeError('Test cleanup is incomplete; retry only the commands in ' + str(output / 'cleanup-pending.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rooms', type=int, default=2)
    parser.add_argument('--duration', default='60s')
    parser.add_argument('--image', default=ROOT.name + ':load')
    args = parser.parse_args()
    if not re.fullmatch(r'[1-9][0-9]*(s|m)', args.duration):
        parser.error('Use a positive seconds/minutes duration')
    output, result = run(ROOT, args.rooms, args.duration, args.image)
    print(json.dumps({'output': str(output), **{key: value for key, value in result.items() if key != 'samples'}}, indent=2))


if __name__ == '__main__':
    main()
