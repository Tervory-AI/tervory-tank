"""API-only site promotion. The durable journal never retries an ambiguous deploy."""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from collections.abc import Awaitable, Callable, Iterator
from typing import Any
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class Refused(ValueError):
    pass


def identifier(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise Refused('invalid identifier')
    return value


def commit(value: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{40}', value):
        raise Refused('full commit required')
    return value


def origin(value: str) -> str:
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443) or p.path not in ('', '/') or p.query or p.fragment:
        raise Refused('HTTPS site origin required')
    return f'https://{p.hostname}/'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    """SQLite on the existing Tisan data volume; short atomic transactions only."""
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sites (
                    tenant TEXT NOT NULL, site TEXT NOT NULL, config TEXT NOT NULL,
                    active TEXT, PRIMARY KEY(tenant,site));
                CREATE TABLE IF NOT EXISTS operations (
                    tenant TEXT NOT NULL, site TEXT NOT NULL, id TEXT NOT NULL,
                    action TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, result TEXT NOT NULL, details TEXT NOT NULL,
                    PRIMARY KEY(tenant,site,id));
            ''')

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=1)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def site(self, tenant: str, site: str) -> dict:
        with self.connect() as db:
            row = db.execute('SELECT config FROM sites WHERE tenant=? AND site=?', (tenant, site)).fetchone()
        if not row:
            raise Refused('site not registered')
        return json.loads(row['config'])

    def register(self, tenant: str, site: str, config: dict) -> None:
        if config['staging'] == config['production']:
            raise Refused('separate applications required')
        config = {**config, 'url': origin(config['url'])}
        identifier(config['staging'])
        identifier(config['production'])
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # A Coolify application may belong to only one registered tenant/site.
            for row in db.execute('SELECT tenant,site,config,active FROM sites'):
                old = json.loads(row['config'])
                if (row['tenant'], row['site']) == (tenant, site):
                    if row['active'] or old != config:
                        raise Refused('registered site configuration is immutable')
                elif {old['staging'], old['production']} & {config['staging'], config['production']}:
                    raise Refused('application already registered')
            db.execute('INSERT OR IGNORE INTO sites(tenant,site,config) VALUES(?,?,?)', (tenant, site, json.dumps(config)))

    def get(self, tenant: str, site: str, operation: str) -> dict | None:
        with self.connect() as db:
            row = db.execute('SELECT * FROM operations WHERE tenant=? AND site=? AND id=?', (tenant, site, operation)).fetchone()
        if row:
            return {**dict(row), 'details': json.loads(row['details'])}
        return None

    def reserve(self, tenant: str, site: str, operation: str, action: str, actor: str, expected: str) -> None:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT active FROM sites WHERE tenant=? AND site=?', (tenant, site)).fetchone()
            if not row:
                raise Refused('site not registered')
            if row['active']:
                active = db.execute('SELECT result FROM operations WHERE tenant=? AND site=? AND id=?',
                                    (tenant, site, row['active'])).fetchone()
                if action != 'rollback' or not active or active['result'] != 'failed':
                    raise Refused('site has an unresolved operation')
            stamp = now()
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)',
                       (tenant, site, operation, action, actor, stamp, stamp, 'checking', json.dumps({'expected': expected})))
            db.execute('UPDATE sites SET active=? WHERE tenant=? AND site=?', (operation, tenant, site))

    def update(self, tenant: str, site: str, operation: str, result: str, details: dict, *, terminal: bool = False) -> None:
        with self.connect() as db:
            db.execute('UPDATE operations SET result=?,details=?,updated_at=? WHERE tenant=? AND site=? AND id=?',
                       (result, json.dumps(details), now(), tenant, site, operation))
            if terminal:
                db.execute('UPDATE sites SET active=NULL WHERE tenant=? AND site=? AND active=?', (tenant, site, operation))

    def latest_recorded(self, tenant: str, site: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT id FROM operations WHERE tenant=? AND site=? AND result IN ('succeeded','failed') ORDER BY rowid DESC LIMIT 1", (tenant, site)).fetchone()
        return self.get(tenant, site, row['id']) if row else None

    def history(self, tenant: str, site: str) -> list[dict]:
        with self.connect() as db:
            ids = db.execute('SELECT id FROM operations WHERE tenant=? AND site=? ORDER BY rowid DESC LIMIT 100', (tenant, site)).fetchall()
        return [self.get(tenant, site, row['id']) for row in ids]


class Coolify:
    def __init__(self, http: httpx.AsyncClient, base: str, token: str) -> None:
        p = urlsplit(base)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/', '/api/v1', '/api/v1/'):
            raise Refused('TISAN_COOLIFY_URL must be an HTTPS API origin')
        if not token:
            raise Refused('TISAN_COOLIFY_TOKEN is not set')
        self.http, self.base, self._token = http, base.rstrip('/').removesuffix('/api/v1'), token

    async def call(self, method: str, path: str, **kwargs: Any) -> dict:
        try:
            r = await self.http.request(method, self.base + '/api/v1' + path,
                headers={'Authorization': 'Bearer ' + self._token}, follow_redirects=False, timeout=30, **kwargs)
            if r.status_code >= 300:
                raise Refused('Coolify request failed')
            data = r.json()
            if not isinstance(data, dict):
                raise Refused('Coolify response shape unavailable')
            return data
        except (httpx.HTTPError, ValueError):
            raise Refused('Coolify response unavailable') from None

    async def current(self, app: str, *, allow_failed: bool = False) -> dict:
        info = await self.call('GET', '/applications/' + identifier(app))
        settings = info.get('settings') or {}
        if info.get('uuid') != app or (not allow_failed and info.get('status') != 'running:healthy') or settings.get('is_auto_deploy_enabled') is not False:
            raise Refused('application must be healthy with automatic deployment disabled')
        history = await self.call('GET', '/deployments/applications/' + app, params={'take': 1, 'skip': 0})
        rows = history.get('deployments', [])
        if len(rows) != 1 or rows[0].get('status') not in (('failed', 'cancelled-by-user', 'cancelled') if allow_failed else ('finished',)) or rows[0].get('pull_request_id') != 0:
            raise Refused('latest application deployment must be finished')
        row = rows[0]
        # A build can fail before Coolify resolves HEAD; recovery is bound to
        # the acknowledged failed UUID and its still-pinned intended SHA.
        sha = commit(info.get('git_commit_sha', '') if allow_failed else row.get('commit', ''))
        # Pinning staging prevents a moving branch from being tested/promoted.
        if info.get('git_commit_sha') != sha:
            raise Refused('application must be pinned to its deployed full commit')
        return {'commit': sha, 'deployment': identifier(row['deployment_uuid']),
                'repository': info.get('git_repository'), 'base_directory': info.get('base_directory'),
                'build_pack': info.get('build_pack'), 'fqdn': info.get('fqdn')}


class Promotion:
    def __init__(self, journal: Journal, coolify: Coolify, live_check: Callable[[str], Awaitable[dict]],
                 radix_gate: Callable[[str, str, str], Awaitable[dict]]) -> None:
        self.journal, self.coolify, self.live_check, self.radix_gate = journal, coolify, live_check, radix_gate

    async def run(self, tenant: str, site: str, operation: str, action: str, actor: str, expected: str) -> dict:
        tenant, operation = str(uuid.UUID(tenant)), str(uuid.UUID(operation))
        identifier(site)
        if action not in ('promote', 'rollback'):
            raise Refused('invalid action')
        commit(expected)
        previous = self.journal.get(tenant, site, operation)
        if previous:
            if previous['action'] != action or previous['actor'] != actor or previous['details']['expected'] != expected:
                raise Refused('operation identity changed')
            return previous  # replay never repeats PATCH/POST or gates
        config = self.journal.site(tenant, site)
        self.journal.reserve(tenant, site, operation, action, actor, expected)
        details = {'expected': expected}
        mutation = False
        try:
            prior = self.journal.latest_recorded(tenant, site)
            recovery = action == 'rollback' and prior is not None and prior['result'] == 'failed'
            production = await self.coolify.current(config['production'], allow_failed=recovery)
            details['previous'] = production['commit']
            if action == 'promote':
                if production['commit'] == expected:
                    raise Refused('production is already at the requested commit')
                staging = await self.coolify.current(config['staging'])
                if staging['commit'] != expected:
                    raise Refused('staging commit changed')
                if staging['repository'] != production['repository'] or not staging['repository'] or any(
                    staging[k] != production[k] for k in ('base_directory', 'build_pack')):
                    raise Refused('staging and production sources differ')
                if config['url'] not in [origin(u.strip()) for u in (staging['fqdn'] or '').split(',') if u.strip()]:
                    raise Refused('staging origin differs from registered application')
                details['staging_deployment'] = staging['deployment']
                details['live_check'] = await self.live_check(config['url'])
                if not isinstance(details['live_check'], dict) or details['live_check'].get('passed') is not True:
                    raise Refused('staging live check failed')
                gate = await self.radix_gate(tenant, config['url'], 'commit:' + expected)
                if not isinstance(gate, dict):
                    raise Refused('Radix gate response unavailable')
                if not isinstance(gate.get('completed_at'), str):
                    raise Refused('Radix completion time unavailable')
                stamp = datetime.fromisoformat(gate['completed_at'].replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - stamp).total_seconds()
                if (gate.get('allowed') is not True or gate.get('status') != 'complete'
                    or gate.get('tenant_id') != tenant or gate.get('target') != config['url']
                    or gate.get('artifact') != 'commit:' + expected or not gate.get('scan_id')
                    or type(gate.get('high')) is not int or gate['high'] != 0
                    or type(gate.get('critical')) is not int or gate['critical'] != 0 or not 0 <= age <= 3600):
                    raise Refused('Radix gate did not pass for this staging commit')
                details['scan_id'] = str(gate['scan_id'])
                if await self.coolify.current(config['staging']) != staging:
                    raise Refused('staging changed during checks')
            else:
                if not prior or prior['details']['commit'] != production['commit']:
                    raise Refused('production differs from last recorded operation')
                if recovery and prior['details'].get('deployment') != production['deployment']:
                    raise Refused('failed production deployment changed')
                if expected != prior['details']['previous']:
                    raise Refused('rollback must restore previous production commit')
                if recovery:
                    details['recovery_of'] = prior['id']
                    details['previous'] = prior['details']['previous']
            if await self.coolify.current(config['production'], allow_failed=recovery) != production:
                raise Refused('production changed during checks')
            details['commit'] = expected
            self.journal.update(tenant, site, operation, 'pinning', details)
            mutation = True
            await self.coolify.call('PATCH', '/applications/' + config['production'], json={'git_commit_sha': expected})
            info = await self.coolify.call('GET', '/applications/' + config['production'])
            if info.get('git_commit_sha') != expected:
                raise Refused('production pin was not confirmed')
            self.journal.update(tenant, site, operation, 'submitting', details)
            deploy = {'uuid': config['production']}
            if action == 'rollback':
                deploy['force'] = True  # A failed build may have left this same commit running.
            result = await self.coolify.call('POST', '/deploy', json=deploy)
            rows = result.get('deployments', [])
            if len(rows) != 1 or rows[0].get('resource_uuid') != config['production']:
                raise Refused('deployment acknowledgement mismatch')
            details['deployment'] = identifier(rows[0].get('deployment_uuid', ''))
            self.journal.update(tenant, site, operation, 'pending', details)
        except (Refused, ValueError, TypeError, KeyError, AttributeError, OSError, TimeoutError, httpx.HTTPError):
            self.journal.update(tenant, site, operation, 'unknown' if mutation else 'refused', details, terminal=not mutation)
        return self.journal.get(tenant, site, operation)

    async def status(self, tenant: str, site: str, operation: str) -> dict:
        row = self.journal.get(tenant, site, operation)
        if not row:
            raise Refused('operation not found')
        details = row['details']
        if row['result'] != 'pending' or not details.get('deployment'):
            return row
        config = self.journal.site(tenant, site)
        result = await self.coolify.call('GET', '/deployments/' + details['deployment'])
        if result.get('deployment_uuid') != details['deployment'] or result.get('pull_request_id') != 0:
            self.journal.update(tenant, site, operation, 'unknown', details)
        elif result.get('status') == 'finished' and result.get('commit') != details['commit']:
            self.journal.update(tenant, site, operation, 'unknown', details)
        elif result.get('status') == 'finished':
            current = await self.coolify.current(config['production'])
            if current['deployment'] != details['deployment'] or current['commit'] != details['commit']:
                self.journal.update(tenant, site, operation, 'unknown', details)
            else:
                self.journal.update(tenant, site, operation, 'succeeded', details, terminal=True)
        elif result.get('status') in ('failed', 'cancelled-by-user', 'cancelled'):
            # Configuration may be pinned but the running version is uncertain.
            self.journal.update(tenant, site, operation, 'failed', details)
        return self.journal.get(tenant, site, operation)
