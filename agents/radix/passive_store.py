"""Tenant-owned DNS challenges and completed passive assessments, never raw traffic."""
from __future__ import annotations

import json
import hashlib
import re
from html.parser import HTMLParser
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
 lease_until timestamptz,
 high integer NOT NULL DEFAULT 0, critical integer NOT NULL DEFAULT 0,
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,domain) REFERENCES agent_radix.passive_domains(tenant_id,domain)
);
ALTER TABLE agent_radix.passive_scans ADD COLUMN IF NOT EXISTS checks jsonb;
ALTER TABLE agent_radix.passive_scans ADD COLUMN IF NOT EXISTS watched boolean NOT NULL DEFAULT false;
ALTER TABLE agent_radix.passive_scans ADD COLUMN IF NOT EXISTS changes jsonb;
ALTER TABLE agent_radix.passive_scans ADD COLUMN IF NOT EXISTS previous_scan_id uuid;
CREATE TABLE IF NOT EXISTS agent_radix.passive_watches (
 tenant_id uuid NOT NULL, domain text NOT NULL, challenge text NOT NULL,
 interval text NOT NULL CHECK (interval IN ('daily','weekly')),
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','stopped')),
 stop_reason text CHECK (stop_reason IN ('txt_missing','txt_changed')),
 next_run timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,domain),
 FOREIGN KEY (tenant_id,domain) REFERENCES agent_radix.passive_domains(tenant_id,domain)
);
-- Follow personal_tokens: join an existing platform rollout, never start one.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='tank' AND c.relname='command_threads' AND c.relrowsecurity) THEN
  ALTER TABLE agent_radix.passive_watches ENABLE ROW LEVEL SECURITY;
  ALTER TABLE agent_radix.passive_watches FORCE ROW LEVEL SECURITY;
  IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='agent_radix.passive_watches'::regclass AND polname='tenant_access') THEN
   CREATE POLICY tenant_access ON agent_radix.passive_watches FOR ALL TO PUBLIC
    USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='agent_radix.passive_watches'::regclass AND polname='tenant_boundary') THEN
   CREATE POLICY tenant_boundary ON agent_radix.passive_watches AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
  END IF;
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS agent_radix.regulation_runs (
 tenant_id uuid NOT NULL, domain text NOT NULL, event_id uuid NOT NULL,
 scan_id uuid NOT NULL, facts jsonb NOT NULL,
 settled boolean NOT NULL DEFAULT false,
 next_attempt timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,domain,event_id),
 UNIQUE (tenant_id,scan_id)
);
CREATE TABLE IF NOT EXISTS agent_radix.page_hashes (
 tenant_id uuid NOT NULL, scan_id uuid NOT NULL, domain text NOT NULL,
 url text NOT NULL, sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
 PRIMARY KEY (tenant_id,scan_id,url)
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


def watch_artifact(domain: str) -> str:
    """Hash the canonical HTTPS scan target, not a nonexistent source commit.

    Identifies the assessed origin, not a content snapshot (the spider observes
    multiple responses). The run UUID and timestamps distinguish observations.
    """
    target = f'https://{domain_name(domain)}/'
    return 'sha256:' + hashlib.sha256(target.encode('ascii')).hexdigest()


def compare_findings(current: list[dict], previous: list[dict]) -> dict:
    # A check is namespaced by its scanner. An item is its URL/file and line.
    # A changed severity retires the old finding and introduces the new one.
    def identity(item):
        return (item.get('tool'), item.get('rule'), item.get('item') or item.get('file'),
                0 if item.get('item') else item.get('line') or 0, item.get('severity'))
    old = {identity(item): item for item in previous}
    new = {identity(item): item for item in current}
    return {'new': [item for key, item in new.items() if key not in old],
            'fixed': [item for key, item in old.items() if key not in new],
            'unchanged': [item for key, item in new.items() if key in old]}


class RuleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def report_finding(row) -> dict:
    item = dict(row)
    encoded = item.pop('fix', None)
    data = json.loads(encoded) if encoded else {}
    texts = data.get(item['rule'], {})
    if '_measured' in data:
        item.update(data['_measured'])
    for field in ('explanation', 'remediation'):
        text = texts.get(field)
        if text:
            parser = RuleText()
            parser.feed(text)
            item[field] = ' '.join(' '.join(parser.parts).split())
        elif '_measured' not in data:
            item[field] = f"No rule text for {item['rule']}."
    return item


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
              SET challenge=CASE WHEN EXISTS (SELECT 1 FROM agent_radix.passive_watches w
                WHERE w.tenant_id=$1 AND w.domain=$2 AND w.status='active')
                THEN passive_domains.challenge ELSE $3 END,
              expires_at=CASE WHEN EXISTS (SELECT 1 FROM agent_radix.passive_watches w
                WHERE w.tenant_id=$1 AND w.domain=$2 AND w.status='active')
                THEN passive_domains.expires_at ELSE now()+interval '1 day' END
              RETURNING expires_at,challenge""", tenant, domain, challenge)
        return {'tenant_id': str(tenant), 'domain': domain, 'name': '_tervory-verify.' + domain,
                'value': row['challenge'], 'expires_at': row['expires_at'].isoformat()}

    async def create(self, tenant: UUID, target: str, artifact: str, *, watched: bool = False) -> UUID:
        target, domain = target_url(target)
        artifact = artifact_id(artifact)
        ident = uuid4()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""INSERT INTO agent_radix.passive_scans(tenant_id,id,domain,target,artifact,watched)
              SELECT d.tenant_id,$2,d.domain,$3,$4,$6 FROM agent_radix.passive_domains d
              WHERE d.tenant_id=$1 AND d.domain=$5 AND
              (($6=false AND d.expires_at>now()) OR ($6=true AND EXISTS (
                SELECT 1 FROM agent_radix.passive_watches w WHERE w.tenant_id=d.tenant_id
                AND w.domain=d.domain AND w.status='active' AND w.challenge=d.challenge))) RETURNING id""",
              tenant, ident, target, artifact, domain, watched)
        if row is None:
            raise PermissionError('domain proof required')
        return ident

    async def pending(self, tenant: UUID, ident: UUID):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""SELECT s.domain,d.challenge FROM agent_radix.passive_scans s
              JOIN agent_radix.passive_domains d ON d.tenant_id=s.tenant_id AND d.domain=s.domain
              WHERE s.tenant_id=$1 AND s.id=$2 AND s.status='pending' AND
              ((s.watched=false AND d.expires_at>now()) OR (s.watched=true AND EXISTS (
                SELECT 1 FROM agent_radix.passive_watches w WHERE w.tenant_id=s.tenant_id
                AND w.domain=s.domain AND w.status='active' AND w.challenge=d.challenge)))
              AND (s.created_at>now()-interval '5 minutes' OR EXISTS (
                SELECT 1 FROM agent_radix.regulation_runs r WHERE r.tenant_id=s.tenant_id
                AND r.scan_id=s.id AND NOT r.settled))""", tenant, ident)

    async def running(self, tenant: UUID, ident: UUID) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""UPDATE agent_radix.passive_scans
              SET status='running',lease_until=now()+interval '420 seconds'
              WHERE tenant_id=$1 AND id=$2 AND status='pending' RETURNING id""", tenant, ident)
        return row is not None

    async def reap_expired(self) -> None:
        """Gateway maintenance only, never invoked from a tenant HTTP request.

        Discover expired lease owners, then update each row with its persisted
        tenant/id and recheck expiry. An active lease is never touched.
        """
        maintenance = getattr(self.pool, "admin_pool", None) or self.pool
        async with maintenance.acquire() as conn:
            owners = await conn.fetch("""SELECT tenant_id,id FROM agent_radix.passive_scans
              WHERE status='running' AND lease_until<now()""")
            for owner in owners:
                await conn.execute("""UPDATE agent_radix.passive_scans SET status='error'
                  WHERE tenant_id=$1 AND id=$2 AND status='running' AND lease_until<now()""",
                  owner['tenant_id'], owner['id'])

    async def fail(self, tenant: UUID, ident: UUID) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("""UPDATE agent_radix.passive_scans SET status='error'
              WHERE tenant_id=$1 AND id=$2 AND status IN ('pending','running')""", tenant, ident)

    async def complete(self, tenant: UUID, ident: UUID, findings: list[dict], *, measurements=None) -> None:
        from scanlib.store import ensure_findings, insert_findings
        high = sum(f['severity'] == 'high' for f in findings)
        critical = sum(f['severity'] == 'critical' for f in findings)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Serialize baselines for the same tenant/domain, including manual scans.
                domain = await conn.fetchval('SELECT domain FROM agent_radix.passive_scans WHERE tenant_id=$1 AND id=$2', tenant, ident)
                await conn.fetchrow('SELECT domain FROM agent_radix.passive_domains WHERE tenant_id=$1 AND domain=$2 FOR UPDATE', tenant, domain)
                await ensure_findings(conn, 'agent_radix')
                prior = await conn.fetchval('''SELECT id FROM agent_radix.passive_scans
                  WHERE tenant_id=$1 AND domain=$2 AND status='complete' AND id<>$3
                  AND EXISTS(SELECT 1 FROM agent_radix.regulation_runs r WHERE r.tenant_id=$1 AND r.scan_id=$3)
                    = EXISTS(SELECT 1 FROM agent_radix.regulation_runs r WHERE r.tenant_id=$1 AND r.scan_id=passive_scans.id)
                  ORDER BY completed_at DESC,id DESC LIMIT 1''', tenant, domain, ident)
                from scanlib.store import list_findings
                previous = [report_finding(r) for r in await list_findings(conn, 'agent_radix', str(tenant), str(prior))] if prior else []
                changes = compare_findings([report_finding(f) for f in findings], previous)
                await insert_findings(conn, 'agent_radix', str(tenant), str(ident), findings)
                row = await conn.fetchrow("""UPDATE agent_radix.passive_scans
                  SET status='complete',high=$3,critical=$4,completed_at=now(),changes=$5::jsonb,previous_scan_id=$6,checks=$7::jsonb
                  WHERE tenant_id=$1 AND id=$2 AND status='running'
                  AND lease_until>now() RETURNING id""", tenant, ident, high, critical, json.dumps(changes, default=str), prior, json.dumps((measurements or {}).get('checks', {})))
                if row is None:
                    raise RuntimeError('scan lease expired')
                for url, digest in ((measurements or {}).get('page_hashes') or {}).items():
                    await conn.execute('''INSERT INTO agent_radix.page_hashes(tenant_id,scan_id,domain,url,sha256)
                      VALUES($1,$2,$3,$4,$5)''', tenant, ident, domain, url, digest)
        from chassis.events import publish
        for ordinal, finding in enumerate(findings):
            await publish(str(tenant), 'radix.finding', f'{ident}:{ordinal}',
                          {'scan_id': str(ident), 'ordinal': ordinal, 'severity': finding['severity']})

    async def watch(self, tenant: UUID, domain: str, interval: str, *, run_now: bool = True) -> dict:
        domain = domain_name(domain)
        if interval not in {'daily', 'weekly'}:
            raise ValueError('invalid interval')
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""INSERT INTO agent_radix.passive_watches
              (tenant_id,domain,challenge,interval,next_run)
              SELECT d.tenant_id,d.domain,d.challenge,$3,
                now()+CASE WHEN $4 THEN interval '0 seconds' WHEN $3='daily' THEN interval '1 day' ELSE interval '7 days' END
              FROM agent_radix.passive_domains d WHERE d.tenant_id=$1 AND d.domain=$2
              AND (d.expires_at>now() OR EXISTS (SELECT 1 FROM agent_radix.passive_watches w
                WHERE w.tenant_id=d.tenant_id AND w.domain=d.domain AND w.status='active' AND w.challenge=d.challenge))
              ON CONFLICT (tenant_id,domain) DO UPDATE SET interval=EXCLUDED.interval,
                challenge=EXCLUDED.challenge,status='active',stop_reason=NULL,next_run=EXCLUDED.next_run
              RETURNING domain AS name,interval,status,stop_reason,next_run""", tenant, domain, interval, run_now)
        if row is None:
            raise PermissionError('domain proof required')
        return dict(row)

    async def unwatch(self, tenant: UUID, domain: str) -> dict:
        domain = domain_name(domain)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""UPDATE agent_radix.passive_watches SET status='stopped',stop_reason=NULL
              WHERE tenant_id=$1 AND domain=$2 RETURNING domain AS name,interval,status,stop_reason,next_run""", tenant, domain)
        return dict(row) if row else {'name': domain, 'status': 'stopped'}

    async def watches(self, tenant: UUID) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT domain AS name,interval,status,stop_reason,next_run
              FROM agent_radix.passive_watches WHERE tenant_id=$1 ORDER BY domain""", tenant)
        return [dict(row) for row in rows]

    async def stop_for_scan(self, tenant: UUID, ident: UUID, reason: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("""UPDATE agent_radix.passive_watches w SET status='stopped',stop_reason=$3
              FROM agent_radix.passive_scans s WHERE s.tenant_id=$1 AND s.id=$2 AND s.watched
              AND w.tenant_id=s.tenant_id AND w.domain=s.domain AND w.status='active'""", tenant, ident, reason)

    async def changes(self, tenant: UUID, domain: str) -> dict:
        domain = domain_name(domain)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""SELECT id,status,completed_at,changes,previous_scan_id,checks,
              (SELECT jsonb_build_object('event_id',r.event_id,'facts',r.facts,
                'checks',jsonb_build_array('comply.gdpr','cookie-missing-flags'),
                'browser_cookies_checked',coalesce(checks->'browser'->>'status'='complete',false))
               FROM agent_radix.regulation_runs r WHERE r.tenant_id=$1 AND r.scan_id=passive_scans.id) AS regulation_event
              FROM agent_radix.passive_scans WHERE tenant_id=$1 AND domain=$2
              ORDER BY created_at DESC,id DESC LIMIT 1""", tenant, domain)
        if not row:
            return {'status': 'pending'}
        result = {'scan_id': str(row['id']), 'status': 'failed' if row['status'] == 'error' else row['status'],
                  'completed_at': row['completed_at'], 'previous_scan_id': str(row['previous_scan_id']) if row['previous_scan_id'] else None}
        if row.get('checks') is not None:
            result['checks'] = json.loads(row['checks']) if isinstance(row['checks'], str) else row['checks']
        if row.get('regulation_event') is not None:
            event = row['regulation_event']
            result['regulation_event'] = json.loads(event) if isinstance(event, str) else event
        if row['status'] == 'complete':
            delta = json.loads(row['changes']) if isinstance(row['changes'], str) else row['changes']
            # Old complete manual scans predate comparison persistence.
            result.update(delta or {'new': [], 'fixed': [], 'unchanged': []})
            result['findings'] = await self.findings(tenant, row['id'])
        return result

    async def previous_hashes(self, tenant: UUID, domain: str) -> dict:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT url,sha256 FROM agent_radix.page_hashes
              WHERE tenant_id=$1 AND domain=$2 AND scan_id=(
                SELECT id FROM agent_radix.passive_scans WHERE tenant_id=$1 AND domain=$2
                AND status='complete' AND checks->'pages'->>'status'='complete'
                ORDER BY completed_at DESC,id DESC LIMIT 1)""", tenant, domain)
        return {r['url']:r['sha256'] for r in rows}

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
            return [report_finding(row) for row in await list_findings(conn, 'agent_radix', str(tenant), str(ident))]


def gate_result(row, tenant: UUID, target: str, artifact: str, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    complete = row and row['status'] == 'complete' and row['completed_at'] is not None
    fresh = complete and 0 <= (now - row['completed_at']).total_seconds() <= 3600
    return {'allowed': bool(fresh and row['high'] == 0 and row['critical'] == 0),
            'tenant_id': str(tenant), 'target': target, 'artifact': artifact,
            'scan_id': str(row['id']) if row else None, 'status': row['status'] if row else 'missing',
            'high': row['high'] if row else None, 'critical': row['critical'] if row else None,
            'completed_at': row['completed_at'].isoformat() if complete else None}
