"""Tenant-owned DNS challenges and completed passive assessments, never raw traffic."""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

DDL = """
CREATE TABLE IF NOT EXISTS agent_radix.passive_domains (
 tenant_id uuid NOT NULL, domain text NOT NULL, challenge text NOT NULL,
 expires_at timestamptz NOT NULL DEFAULT now() + interval '1 day',
 PRIMARY KEY (tenant_id, domain)
);
CREATE TABLE IF NOT EXISTS agent_radix.passive_scans (
 tenant_id uuid NOT NULL, id uuid NOT NULL, domain text NOT NULL,
 target text NOT NULL, artifact text NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','complete','error')),
 created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 high integer NOT NULL DEFAULT 0, critical integer NOT NULL DEFAULT 0,
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,domain) REFERENCES agent_radix.passive_domains(tenant_id,domain)
);
CREATE UNIQUE INDEX IF NOT EXISTS passive_one_running
 ON agent_radix.passive_scans ((true)) WHERE status='running';
"""


def domain_name(value: str) -> str:
    if not isinstance(value, str) or value != value.strip() or len(value) > 253:
        raise ValueError('invalid domain')
    value = value.lower().removesuffix('.')
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', value):
        raise ValueError('invalid domain')
    if value.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('invalid domain')
    return value


def target_url(value: str) -> tuple[str, str]:
    p = urlsplit(value)
    host = domain_name(p.hostname or '')
    # Deliberately one HTTPS origin root. No credentials, ports, query, path or fragments.
    if value != f'https://{host}/' or p.port is not None:
        raise ValueError('invalid target')
    return value, host


def artifact_id(value: str) -> str:
    if not re.fullmatch(r'(?:commit:[0-9a-f]{40}|sha256:[0-9a-f]{64})', value):
        raise ValueError('invalid artifact')
    return value


class Store:
    def __init__(self, pool):
        self.pool = pool

    async def issue(self, tenant: UUID, domain: str) -> dict:
        domain = domain_name(domain)
        # Public DNS proof, not an authentication key. No cross-tenant default.
        challenge = 'tervory-' + secrets.token_hex(32)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""INSERT INTO agent_radix.passive_domains(tenant_id,domain,challenge)
              VALUES($1,$2,$3) ON CONFLICT(tenant_id,domain) DO UPDATE
              SET challenge=$3, expires_at=now()+interval '1 day' RETURNING expires_at""", tenant, domain, challenge)
        return {'tenant_id': str(tenant), 'domain': domain, 'name': '_tervory-verify.' + domain,
                'value': challenge, 'expires_at': row['expires_at'].isoformat()}

    async def create(self, tenant: UUID, target: str, artifact: str) -> UUID:
        target, domain = target_url(target)
        artifact = artifact_id(artifact)
        ident = uuid4()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""INSERT INTO agent_radix.passive_scans(tenant_id,id,domain,target,artifact)
              SELECT tenant_id,$2,domain,$3,$4 FROM agent_radix.passive_domains
              WHERE tenant_id=$1 AND domain=$5 AND expires_at>now() RETURNING id""",
              tenant, ident, target, artifact, domain)
        if row is None:
            raise PermissionError('domain proof required')
        return ident

    async def pending(self, tenant: UUID, ident: UUID):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""SELECT s.domain,d.challenge FROM agent_radix.passive_scans s
              JOIN agent_radix.passive_domains d ON d.tenant_id=s.tenant_id AND d.domain=s.domain
              WHERE s.tenant_id=$1 AND s.id=$2 AND s.status='pending' AND d.expires_at>now()
              AND s.created_at>now()-interval '5 minutes'""", tenant, ident)

    async def running(self, tenant: UUID, ident: UUID) -> bool:
        async with self.pool.acquire() as conn:
            # Clear expired leases only; their findings never become a passing assessment.
            await conn.execute("""UPDATE agent_radix.passive_scans SET status='error'
              WHERE status='running' AND created_at<now()-interval '10 minutes'""")
            row = await conn.fetchrow("""UPDATE agent_radix.passive_scans SET status='running'
              WHERE tenant_id=$1 AND id=$2 AND status='pending' RETURNING id""", tenant, ident)
        return row is not None

    async def fail(self, tenant: UUID, ident: UUID) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("""UPDATE agent_radix.passive_scans SET status='error'
              WHERE tenant_id=$1 AND id=$2 AND status IN ('pending','running')""", tenant, ident)

    async def complete(self, tenant: UUID, ident: UUID, findings: list[dict]) -> None:
        from scanlib.store import ensure_findings, insert_findings
        high = sum(f['severity'] == 'high' for f in findings)
        critical = sum(f['severity'] == 'critical' for f in findings)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await ensure_findings(conn, 'agent_radix')
                await insert_findings(conn, 'agent_radix', str(tenant), str(ident), findings)
                row = await conn.fetchrow("""UPDATE agent_radix.passive_scans
                  SET status='complete',high=$3,critical=$4,completed_at=now()
                  WHERE tenant_id=$1 AND id=$2 AND status='running'
                  AND created_at>now()-interval '10 minutes' RETURNING id""", tenant, ident, high, critical)
                if row is None:
                    raise RuntimeError('scan lease expired')
        from chassis.events import publish
        for ordinal, finding in enumerate(findings):
            await publish(str(tenant), 'radix.finding', f'{ident}:{ordinal}',
                          {'scan_id': str(ident), 'ordinal': ordinal, 'severity': finding['severity']})

    async def gate(self, tenant: UUID, target: str, artifact: str) -> dict:
        target_url(target)
        artifact_id(artifact)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""SELECT id,status,high,critical,completed_at
              FROM agent_radix.passive_scans WHERE tenant_id=$1 AND target=$2 AND artifact=$3
              ORDER BY created_at DESC,id DESC LIMIT 1""", tenant, target, artifact)
        return gate_result(row, tenant, target, artifact)

    async def findings(self, tenant: UUID, ident: UUID) -> list:
        from scanlib.store import list_findings
        async with self.pool.acquire() as conn:
            return [dict(row) for row in await list_findings(conn, 'agent_radix', str(tenant), str(ident))]


def gate_result(row, tenant: UUID, target: str, artifact: str, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    complete = row and row['status'] == 'complete' and row['completed_at'] is not None
    fresh = complete and 0 <= (now - row['completed_at']).total_seconds() <= 3600
    return {'allowed': bool(fresh and row['high'] == 0 and row['critical'] == 0),
            'tenant_id': str(tenant), 'target': target, 'artifact': artifact,
            'scan_id': str(row['id']) if row else None, 'status': row['status'] if row else 'missing',
            'high': row['high'] if row else None, 'critical': row['critical'] if row else None,
            'completed_at': row['completed_at'].isoformat() if complete else None}
