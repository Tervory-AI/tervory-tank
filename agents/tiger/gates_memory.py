"""Tiger personal kinds on shared Hermes user scoping, never product postfiltering.

Tenant-wide: heartbeat only. Personal: tracked products, observed prices, client
suppliers, margin rules, dismissed alerts, outcomes, corrections, memory settings.
Uses the shared signed-client/Hermes contract shipped in Tank #765.
"""
import hashlib
import json
import re
from uuid import UUID

KINDS = ('tiger.product', 'tiger.seen_price', 'tiger.supplier', 'tiger.margin_rule',
         'tiger.dismissed_alert', 'tiger.outcome', 'tiger.correction', 'tiger.setting')
REUSABLE_TASKS = frozenset({'tiger.supplier', 'tiger.margin'})


class ScopeError(ValueError):
    pass


class Unavailable(RuntimeError):
    pass


def key(task, payload):
    return hashlib.sha256(json.dumps([task, payload], sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def safe(value):
    if re.search(r'(?i)password|passwd|api[_-]?key|secret|bearer |-----BEGIN', json.dumps(value)):
        raise ValueError('Secrets cannot be remembered')


class Memory:
    def __init__(self, client, tenant, user):
        try:
            self.tenant = str(UUID(str(tenant)))
        except ValueError:
            raise ScopeError('Valid tenant required') from None
        if not isinstance(user, str) or not user.strip() or len(user) > 200:
            raise ScopeError('Verified user required')
        self.user, self.client = user, client

    async def call(self, method, *args, **kwargs):
        try:
            return await getattr(self.client, method)(*args, user_id=self.user, **kwargs)
        except TypeError:
            raise ScopeError('Shared signed memory client required') from None
        except RuntimeError as exc:
            text = str(exc)
            if any(str(code) in text for code in (400, 401, 403, 404, 409, 422)):
                raise ScopeError('Memory scope refused') from None
            if 'unreachable' in text or any(str(code) in text for code in (502, 503, 504)):
                raise Unavailable('memory unavailable') from None
            raise

    async def rows(self):
        return await self.call('records', self.tenant)

    async def enabled(self):
        settings = [r for r in await self.rows() if r['kind'] == 'tiger.setting']
        settings.sort(key=lambda r: r['meta']['revision'])
        return not settings or settings[-1]['meta']['enabled']

    async def write(self, kind, value, meta=None):
        if kind not in KINDS:
            raise ScopeError('Unknown kind')
        safe([value, meta])
        return await self.call('remember', self.tenant, json.dumps(value), kind, 'tiger', meta=meta or {}, index=False)

    async def setting(self, enabled):
        rows = await self.rows()
        revision = max((r['meta'].get('revision', 0) for r in rows), default=0) + 1
        return await self.write('tiger.setting', {'enabled': enabled}, {'enabled': enabled, 'revision': revision})

    async def forget(self, identity):
        identity = str(UUID(str(identity)))
        row = next((r for r in await self.rows() if r['id'] == identity), None)
        if row is None or row['meta'].get('user_id') != self.user:
            raise ScopeError('No owned record')
        if row['kind'] in KINDS[:5]:
            # A reusable answer can depend on any recalled personal fact. Clear
            # derived answers before removing their source; partial failures
            # cannot leave a stale answer eligible for the next request.
            for derived in await self.rows():
                if derived['kind'] in ('tiger.outcome', 'tiger.correction'):
                    await self.call('forget', derived['id'], self.tenant)
        await self.call('forget', identity, self.tenant)

    async def edit(self, identity, value):
        row = next((r for r in await self.rows() if r['id'] == str(identity)), None)
        if row is None or row['meta'].get('user_id') != self.user:
            raise ScopeError('No owned record')
        # Immutable Hermes ids: replace, then forget, never upsert changed claims.
        meta = {k: v for k, v in row['meta'].items() if k not in ('user_id', '_index_enabled')}
        if row['kind'] in ('tiger.outcome', 'tiger.correction'):
            meta['result'] = value
        saved = await self.write(row['kind'], value, meta)
        await self.forget(identity)
        return saved

    async def correct(self, task, payload, result):
        if not await self.enabled():
            return None
        digest = key(task, payload)
        rows = await self.rows()
        revision = max((r['meta'].get('revision', 0) for r in rows), default=0) + 1
        # Corrections outrank stale results even if deletion fails halfway.
        prior = [r for r in rows if r['kind'] in ('tiger.outcome', 'tiger.correction') and r['meta'].get('key') == digest]
        receipt = prior[-1]['meta'].get('receipt', {}) if prior else {}
        saved = await self.write('tiger.correction', result, {'key': digest, 'revision': revision, 'result': result, 'receipt': receipt})
        for row in rows:
            if row['kind'] in ('tiger.outcome', 'tiger.correction') and row['meta'].get('key') == digest:
                await self.forget(row['id'])
        return saved

    async def exact(self, task, payload):
        if task not in REUSABLE_TASKS or not await self.enabled():
            return None
        hits = [r for r in await self.rows() if r['kind'] in ('tiger.outcome', 'tiger.correction') and r['meta'].get('key') == key(task, payload)]
        hits.sort(key=lambda r: (r['kind'] == 'tiger.correction', r['meta'].get('revision', 0)))
        return hits[-1] if hits else None

    async def recall(self, task):
        if not await self.enabled():
            return []
        semantic = await self.call('recall', self.tenant, task)
        # SQL-only facts written without embeddings still inform the next task.
        # User isolation is entirely Hermes's SQL predicate, not this kind filter.
        facts = [r for r in await self.rows() if r['kind'] in KINDS[:5]]
        known = {r['id'] for r in semantic}
        return semantic + [r for r in facts if r['id'] not in known]

    async def remember(self, task, payload, result, receipt):
        if await self.enabled():
            # Save the paid answer first. If later fact writes fail, an exact
            # repeat still has its source receipt and never pays again.
            outcome = await self.write('tiger.outcome', result, {'key': key(task, payload), 'result': result, 'receipt': receipt})
            # Persist only supplied facts, not empty placeholders. These are
            # personal kinds; shared heartbeat is the only tenant-wide kind.
            for field, kind in (('products', 'tiger.product'), ('seen_prices', 'tiger.seen_price'),
                                ('suppliers', 'tiger.supplier'), ('margin_rules', 'tiger.margin_rule'),
                                ('dismissed_alerts', 'tiger.dismissed_alert')):
                if field in payload and payload[field] is not None:
                    await self.write(kind, payload[field])
            return outcome
