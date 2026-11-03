"""Regional restore proof in newly created containers only; never production SQL."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'jobs/train'))
from r2_archive import PLATFORM_TENANT, Storage, restore_archive  # noqa: E402

PG_IMAGE = 'postgres:16.15'
QDRANT_IMAGE = 'qdrant/qdrant:v1.20.0'
SAFE_ENV = {k: os.environ[k] for k in ('PATH', 'LANG', 'LC_ALL') if k in os.environ}


def command(*args: str, data: bytes | None = None) -> bytes:
    """Do not leak subprocess errors, dump rows or identity material."""
    if args[0] == 'docker':
        args = ('docker', '--host', 'unix:///var/run/docker.sock', *args[1:])
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=SAFE_ENV, timeout=3600)
    if result.returncode:
        raise RuntimeError(f'{Path(args[0]).name} failed (exit {result.returncode})')
    return result.stdout


class Sandbox:
    def __init__(self):
        self.name = 'restore-drill-' + uuid4().hex
        self.pg = self.name + '-pg'
        self.qd = self.name + '-qd'
        self.url = ''

    def sql(self, sql: str) -> str:
        return command('docker', 'exec', '-i', self.pg, 'psql', '-XAt',
                       '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres',
                       data=sql.encode()).decode().strip()

    def request(self, method, path, **kwargs):
        with httpx.Client(trust_env=False, timeout=3600, follow_redirects=False) as client:
            response = client.request(method, self.url + path, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f'Isolated Qdrant HTTP {response.status_code}')
        return response

    def wait(self):
        for _ in range(90):
            try:
                self.sql('SELECT 1')
                self.request('GET', '/readyz')
                return
            except (RuntimeError, httpx.HTTPError):
                time.sleep(1)
        raise RuntimeError('Isolated stores did not become ready')


@contextmanager
def sandbox():
    """Internal Docker network, random names, no host storage or production env."""
    box = Sandbox()
    command('docker', 'network', 'create', '--internal', box.name)
    try:
        command('docker', 'run', '-d', '--pull=never', '--name', box.pg,
                '--network', box.name, '--memory=1g', '--cpus=1',
                '--label', 'tervory.restore-drill=' + box.name,
                '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', PG_IMAGE)
        command('docker', 'run', '-d', '--pull=never', '--name', box.qd,
                '--network', box.name, '--memory=1g', '--cpus=1',
                '--label', 'tervory.restore-drill=' + box.name,
                QDRANT_IMAGE)
        address = command('docker', 'inspect', '--format',
                          '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                          box.qd).decode().strip()
        if not ipaddress.ip_address(address).is_private:
            raise RuntimeError('Disposable Qdrant must use its private bridge address')
        box.url = 'http://' + address + ':6333'
        box.wait()
        yield box
    finally:
        for name in (box.pg, box.qd):
            subprocess.run(['docker', '--host', 'unix:///var/run/docker.sock', 'rm', '-fv', name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, env=SAFE_ENV, timeout=60)
        command('docker', 'network', 'rm', box.name)


def newest(rows, prefix):
    """Completion manifests only; one newest SQL dump and one per collection."""
    selected = {}
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2}/\d{6}-[a-f0-9]{32}/(database\.dump\.age|qdrant/([A-Za-z0-9][A-Za-z0-9_.-]*)\.snapshot\.age)/manifest\.json$')
    for row in rows:
        key = row['key']
        if not key.startswith(prefix):
            raise RuntimeError('Archive listing crossed the regional prefix')
        name = key[len(prefix):]
        match = pattern.fullmatch(name)
        if match:
            label = match[1]
            selected[label] = max(selected.get(label, ''), name)
    if 'database.dump.age' not in selected:
        raise RuntimeError('No completed encrypted Postgres backup found')
    if len(selected) < 2:
        raise RuntimeError('No completed encrypted Qdrant backups found')
    return selected


def decrypt(source: Path, destination: Path, identity: Path):
    # age reads the file; Python never opens, copies or logs its contents.
    command('age', '--decrypt', '--identity', str(identity), '--output', str(destination), str(source))
    destination.chmod(0o600)


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def counts(box):
    tables = json.loads(box.sql("""SELECT coalesce(json_agg(x), '[]') FROM (
      SELECT DISTINCT n.nspname AS schema,c.relname AS name
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_attribute a ON a.attrelid=c.oid
      WHERE a.attname='tenant_id' AND NOT a.attisdropped AND c.relkind IN ('r','p')
      AND n.nspname NOT IN ('pg_catalog','information_schema')
      ORDER BY 1,2) x"""))
    result = {}
    for table in tables:
        relation = identifier(table['schema']) + '.' + identifier(table['name'])
        # Aggregate totals only: no tenant identifiers or customer rows emitted.
        result[relation] = int(box.sql(f'SELECT count(*) FROM {relation}'))
    return result


def rls(box, folder):
    failures = []
    for path in sorted((ROOT / 'db/migrations/tenant_rls').glob('*.sql')):
        try:
            box.sql(path.read_text())
        except RuntimeError:
            failures.append(str(path.relative_to(ROOT)))
    report = folder / 'rls.xml'
    env = {**SAFE_ENV, 'RESTORE_DRILL_PG': box.pg, 'PYTHONPATH': str(ROOT)}
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q',
                             'tests/tenant_rls',
                             '--tb=no', f'--junitxml={report}'], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)
    if report.exists():
        # pytest wrote this report locally. Read it as text, not with an XML parser
        # (Semgrep use-defused-xml): one <testcase ...> element per test.
        text = report.read_text(encoding='utf-8')
        cases = re.findall(r'<testcase\b([^>]*?)(?:/>|>(.*?)</testcase>)', text, re.S)
        if not cases:
            failures.append('tests/tenant_rls (no restored-copy tests executed)')
        for attrs, body in cases:
            if re.search(r'<(failure|error|skipped)\b', body or ''):
                classname = re.search(r'classname="([^"]*)"', attrs)
                name = re.search(r'\bname="([^"]*)"', attrs)
                failures.append((classname.group(1) if classname else '') + '::' + (name.group(1) if name else ''))
    else:
        failures.append('tests/tenant_rls (missing test report)')
    if result.returncode and not failures:
        failures.append('tests/tenant_rls/test_restored_copy.py (collection or runner failure)')
    return failures


async def drill(region, identity, *, check_rls=False, store=None):
    if os.environ.get('TANK_REGION') != region:
        raise RuntimeError('TANK_REGION must match --region on the owning regional box')
    owner = 'zenas' if region == 'za' else 'uploads'
    owned = store is None
    store = Storage(owner) if owned else store
    try:
        if store.region != region or store.owner != owner:
            raise RuntimeError('Storage owner/region mismatch')
        public = region == 'za'
        prefix = store._prefix(PLATFORM_TENANT, 'backups', public=public)
        selected = newest(await store.objects(PLATFORM_TENANT, 'backups', public=public), prefix)
        with tempfile.TemporaryDirectory(prefix='restore-drill-') as directory:
            folder = Path(directory)
            for index, name in enumerate(selected.values()):
                await restore_archive(store, name, folder / f'{index}.age', 'backups',
                                      tenant_id=PLATFORM_TENANT, public=public)
            started = time.monotonic()
            with sandbox() as box:
                for index, label in enumerate(selected):
                    plain = folder / f'{index}.plain'
                    decrypt(folder / f'{index}.age', plain, identity)
                    try:
                        if label == 'database.dump.age':
                            command('docker', 'cp', str(plain), box.pg + ':/tmp/restore.dump')
                            command('docker', 'exec', box.pg, 'pg_restore', '--exit-on-error',
                                    '--no-owner', '--no-privileges', '-U', 'postgres',
                                    '-d', 'postgres', '/tmp/restore.dump')
                        else:
                            collection = label.removeprefix('qdrant/').removesuffix('.snapshot.age')
                            with plain.open('rb') as snapshot:
                                box.request('POST', f'/collections/{collection}/snapshots/upload?priority=snapshot&wait=true',
                                            files={'snapshot': ('restore.snapshot', snapshot, 'application/octet-stream')})
                    finally:
                        plain.unlink(missing_ok=True)
                tables = counts(box)
                points = {}
                for label in selected:
                    if label.startswith('qdrant/'):
                        name = label.removeprefix('qdrant/').removesuffix('.snapshot.age')
                        points[name] = box.request('POST', f'/collections/{name}/points/count', json={'exact': True}).json()['result']['count']
                elapsed = round(time.monotonic() - started, 3)
                failures = rls(box, folder) if check_rls else []
                return {'region': region, 'archives': selected, 'restore_seconds': elapsed,
                        'tenant_table_rows': tables, 'collection_points': points,
                        'rls_requested': check_rls, 'rls_failures': failures}
    finally:
        if owned:
            await store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', required=True, choices=['us-east', 'za'])
    parser.add_argument('--identity-file', required=True, type=Path)
    parser.add_argument('--rls', action='store_true')
    args = parser.parse_args()
    try:
        result = asyncio.run(drill(args.region, args.identity_file, check_rls=args.rls))
        print(json.dumps(result, sort_keys=True))
        return int(bool(result['rls_failures']))
    except Exception as exc:
        # No raw exception, URL, SQL, subprocess stderr or identity ever logged.
        print(json.dumps({'error': 'Restore drill failed', 'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
