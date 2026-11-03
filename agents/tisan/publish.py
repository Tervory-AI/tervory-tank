"""Publish stored builds through Tank, then deploy only registered staging apps."""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import os
import re
import tarfile
import uuid
from pathlib import Path, PurePosixPath

import httpx
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

MAX_BYTES = 24 * 1024 * 1024


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    slug: str = Field(pattern=r'^[a-z0-9-]{1,100}$')
    build: int = Field(gt=0, le=2147483647)
    operation_id: uuid.UUID


def stored_build(root: Path, tenant: str, slug: str, number: int) -> dict:
    """Read regular files without extracting any archive paths to disk."""
    folder = root / 'builds' / tenant / slug
    files = {}
    total = 0
    manifest_path, archive_path = folder / f'{number}.json', folder / f'{number}.tar.gz'
    for path in (manifest_path, archive_path):
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise ValueError('invalid stored build')
    if manifest_path.stat().st_size > 1024 * 1024 or archive_path.stat().st_size > MAX_BYTES:
        raise ValueError('stored build too large')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('ok') is not True or manifest.get('slug') != slug or manifest.get('build') != number
            or not manifest.get('checks') or any(c.get('ok') is not True for c in manifest['checks'])
            or manifest.get('detail')):
        raise ValueError('stored build did not pass')
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or '..' in path.parts or '.git' in path.parts
                    or str(path) != member.name or '\\' in member.name or member.name in files
                    or len(files) >= 5000 or member.size > MAX_BYTES):
                raise ValueError('invalid archive member')
            total += member.size
            if total > MAX_BYTES:
                raise ValueError('stored build too large')
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError('missing archive member')
            files[member.name] = {'content': base64.b64encode(stream.read()).decode('ascii'),
                                  'mode': '100755' if member.mode & 0o111 else '100644'}
    if not files or sorted(files) != sorted(manifest['files']):
        raise ValueError('manifest differs from archive')
    return {'manifest': manifest, 'files': files}


class Publisher:
    def __init__(self, core, journal, coolify, http, root: Path, tank_url: str, key: str):
        self.core, self.journal, self.coolify, self.http = core, journal, coolify, http
        self.root, self.tank_url, self.key = root, tank_url.rstrip('/'), key

    async def run(self, body: PublishRequest, actor: str) -> dict:
        tenant, site, operation = str(body.tenant_id), body.slug, str(body.operation_id)
        expected = f'build:{body.build}'
        previous = self.journal.get(tenant, site, operation)
        if previous:
            if previous['action'] != 'publish' or previous['actor'] != actor or previous['details']['expected'] != expected:
                raise self.core.Refused('operation identity changed')
            return previous
        config = self.journal.site(tenant, site)
        self.journal.reserve(tenant, site, operation, 'publish', actor, expected)
        details = {'expected': expected}
        mutation = False
        try:
            build = stored_build(self.root, tenant, site, body.build)
            staging = await self.coolify.current(config['staging'])
            info = await self.coolify.call('GET', '/applications/' + config['staging'])
            branch = f'site/{tenant}/{site}'
            if (info.get('git_branch') != branch or info.get('base_directory') not in ('', '/')
                    or info.get('git_commit_sha') != staging['commit']
                    or info.get('settings', {}).get('is_auto_deploy_enabled') is not False
                    or config['url'] not in [self.core.origin(u.strip()) for u in (staging['fqdn'] or '').split(',') if u.strip()]):
                raise self.core.Refused('staging source or origin differs')
            # Reserve before Git writes too: an uncertain acknowledgement must not create a second commit.
            self.journal.update(tenant, site, operation, 'committing', details)
            mutation = True
            response = await self.http.post(self.tank_url + '/v1/tisan/publish/git',
                headers={'X-Tank-Key': self.key, 'X-Tervory-Admin': actor, 'X-Tervory-Tenant': tenant},
                json={**build, 'tenant_id': tenant, 'slug': site, 'repository': staging['repository']}, timeout=240)
            if response.status_code != 200:
                raise self.core.Refused('Git commit unavailable')
            sha = self.core.commit(response.json()['commit'])
            details.update(commit=sha, url=config['url'])
            # Recheck before mutating the pinned app. Never read or write production here.
            if await self.coolify.current(config['staging']) != staging:
                raise self.core.Refused('staging changed during commit')
            self.journal.update(tenant, site, operation, 'pinning', details)
            await self.coolify.call('PATCH', '/applications/' + config['staging'], json={'git_commit_sha': sha})
            pinned = await self.coolify.call('GET', '/applications/' + config['staging'])
            if pinned.get('git_commit_sha') != sha or pinned.get('git_branch') != branch:
                raise self.core.Refused('staging pin not confirmed')
            self.journal.update(tenant, site, operation, 'submitting', details)
            result = await self.coolify.call('POST', '/deploy', json={'uuid': config['staging']})
            rows = result.get('deployments', [])
            if len(rows) != 1 or rows[0].get('resource_uuid') != config['staging']:
                raise self.core.Refused('deployment acknowledgement mismatch')
            details['deployment'] = self.core.identifier(rows[0].get('deployment_uuid', ''))
            self.journal.update(tenant, site, operation, 'pending', details)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, tarfile.TarError, httpx.HTTPError):
            self.journal.update(tenant, site, operation, 'unknown' if mutation else 'refused', details, terminal=not mutation)
        return self.journal.get(tenant, site, operation)

    async def status(self, body: PublishRequest, actor: str) -> dict:
        tenant, site, operation = str(body.tenant_id), body.slug, str(body.operation_id)
        row = self.journal.get(tenant, site, operation)
        if (not row or row['action'] != 'publish' or row['actor'] != actor
                or row['details']['expected'] != f'build:{body.build}'):
            raise self.core.Refused('operation identity differs')
        if row['result'] != 'pending':
            return row
        details = row['details']
        config = self.journal.site(tenant, site)
        result = await self.coolify.call('GET', '/deployments/' + details['deployment'])
        state, terminal = 'pending', False
        if result.get('deployment_uuid') != details['deployment'] or result.get('pull_request_id') != 0:
            state = 'unknown'
        elif result.get('status') in ('failed', 'cancelled', 'cancelled-by-user'):
            state = 'failed'
        elif result.get('status') == 'finished':
            if result.get('commit') != details['commit']:
                state = 'unknown'
            else:
                current = await self.coolify.current(config['staging'])
                if current['deployment'] == details['deployment'] and current['commit'] == details['commit']:
                    state, terminal = 'succeeded', True
                else:
                    state = 'unknown'
        self.journal.update(tenant, site, operation, state, details, terminal=terminal)
        return self.journal.get(tenant, site, operation)


def mount(app, core):
    async def call(body, key, actor, action):
        expected = os.environ.get('TANK_KEY', '')
        founders = {p.strip() for p in os.environ.get('TERVORY_ADMIN_USER_IDS', '').split(',') if p.strip()}
        if not expected or not key or not hmac.compare_digest(key.encode(), expected.encode()) or actor not in founders:
            raise HTTPException(404, 'not found')
        try:
            root = Path(os.environ.get('DATA_DIR', '/data'))
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
                service = Publisher(core, core.Journal(root / 'promotion.sqlite3'), core.Coolify(http,
                    os.environ.get('TISAN_COOLIFY_URL', ''), os.environ.get('TISAN_COOLIFY_TOKEN', '')),
                    http, root, os.environ.get('TANK_URL', 'http://tank:8000'), key)
                if action == 'status':
                    return await service.status(body, actor)
                row = await service.run(body, actor)
                # Wait for this acknowledged deployment; a timeout stays pending and is polled, never resubmitted.
                deadline = asyncio.get_running_loop().time() + 480
                while row['result'] == 'pending' and asyncio.get_running_loop().time() < deadline:
                    row = await service.status(body, actor)
                    if row['result'] == 'pending':
                        await asyncio.sleep(2)
                return row
        except (ValueError, OSError, httpx.HTTPError):
            raise HTTPException(503, 'Publish could not be confirmed; inspect its operation status.') from None

    @app.post('/publish/build')
    async def publish(body: PublishRequest, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        return await call(body, x_tank_key, x_tervory_admin, 'build')

    @app.post('/publish/status')
    async def status(body: PublishRequest, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        return await call(body, x_tank_key, x_tervory_admin, 'status')
