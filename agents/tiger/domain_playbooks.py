"""Public layout facts only; client observations stay in the tenant store.

No HTML, prices, product names, tenant IDs, credentials or raw page URLs are
accepted by the shared store. Page fingerprints deduplicate public paths;
queries and fragments cannot manufacture additional confirming pages.
"""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit

from page_guard import STRUCTURED, _split_selector

# Only generic markup vocabulary may be shared. Site-specific/personalized
# classes remain in the existing tenant-scoped per-URL observation instead.
_TAGS = frozenset('article aside b body div em h1 h2 h3 h4 html li main p section small span strong ul'.split())
_WORDS = frozenset('product products main information details title price prices current regular sale special final '
                   'amount value money cost container wrapper wrap box block content info row col column '
                   'text color colour primary secondary large small normal now old new incl excl tax vat'.split())


def public_marker(layout: dict | None) -> dict | None:
    if not isinstance(layout, dict):
        return None
    primary = layout.get('primary')
    if primary in STRUCTURED:
        return {'primary': primary}
    selector = layout.get('dom')
    if primary != 'dom' or not isinstance(selector, str) or len(selector) > 200:
        return None
    if not re.fullmatch(r'(?:tag:[a-z][a-z0-9]*(?:\.[A-Za-z_-]+)?|scope:[a-z][a-z0-9]*(?:\.[A-Za-z_-]+)?\|[a-z][a-z0-9]*(?:\.[A-Za-z_-]+)?)', selector):
        return None
    scope, scope_class, tag, tag_class = _split_selector(selector)
    if tag not in _TAGS or scope and scope not in _TAGS:
        return None
    for value in (scope_class, tag_class):
        if value and not all(word.lower() in _WORDS for word in re.split('[-_]', value)):
            return None
    return {'primary': 'dom', 'dom': selector}


def public_page(url: str, page: dict) -> tuple[str, str] | None:
    """The browser only returns price-reader HTML for public, allowed pages."""
    if (not page.get('ok') or not page.get('html') or page.get('challenge')
            or page.get('blocked_by_check') or page.get('portal_item')
            or page.get('private') or page.get('login_status')
            or page.get('status') in {401, 403, 429}):
        return None
    try:
        parsed = urlsplit(page.get('url') or url)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
        if (parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password
                or parsed.port not in {None, 80, 443} or '.' not in host
                or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host)
                or host.endswith(('.local', '.localhost', '.internal'))):
            return None
        try:
            ipaddress.ip_address(host)
            return None  # A playbook describes a shop hostname, never an IP.
        except ValueError:
            pass
    except (ValueError, UnicodeError, TypeError):
        return None
    # Scheme/query/fragment differences are not independent pages. No raw path
    # survives this call, including any client parameter embedded in the URL.
    fingerprint = hashlib.sha256((host + (parsed.path or '/')).encode()).hexdigest()
    return host, fingerprint


def _empty() -> dict:
    return {'generation': 0, 'marker': None, 'failures': 0, 'confirmations': {}}


def _snapshot(state: dict) -> dict:
    return {key: copy.deepcopy(state[key]) for key in ('generation', 'marker', 'failures')}


def _advance(state: dict, page_hash: str, generation: int, attempted: bool | None, confirmed: dict | None) -> bool:
    if state['generation'] != generation or not re.fullmatch('[a-f0-9]{64}', page_hash):
        return False  # An in-flight result cannot revive a retired generation.
    if state['marker'] is not None:
        if attempted is not None:
            state['failures'] = 0 if attempted else state['failures'] + 1
            if state['failures'] == 3:
                state.update(marker=None, generation=generation + 1, confirmations={})
        return True
    marker = public_marker(confirmed)
    if marker is None:
        return state['confirmations'].pop(page_hash, None) is not None
    state['confirmations'][page_hash] = marker
    if sum(value == marker for value in state['confirmations'].values()) >= 3:
        state.update(marker=marker, failures=0, generation=generation + 1, confirmations={})
    return True


async def ensure_tables(conn, schema: str) -> None:
    await conn.execute(f'''CREATE TABLE IF NOT EXISTS {schema}.domain_playbooks (
        domain text PRIMARY KEY,
        generation bigint NOT NULL DEFAULT 0 CHECK(generation>=0),
        marker jsonb,
        failures smallint NOT NULL DEFAULT 0 CHECK(failures BETWEEN 0 AND 3),
        confirmations jsonb NOT NULL DEFAULT '{{}}'::jsonb)''')


class MemoryPlaybooks:
    async def get_playbook(self, domain: str) -> dict:
        if not hasattr(self, 'playbooks'):
            self.playbooks = {}
        return _snapshot(self.playbooks.setdefault(domain, _empty()))

    async def record_playbook(self, domain: str, page_hash: str, generation: int,
                              attempted: bool | None, confirmed: dict | None) -> None:
        _advance(self.playbooks[domain], page_hash, generation, attempted, confirmed)


class PgPlaybooks:
    async def get_playbook(self, domain: str) -> dict:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            await conn.execute(f'INSERT INTO {self.schema}.domain_playbooks(domain) VALUES($1) ON CONFLICT DO NOTHING', domain)
            row = await conn.fetchrow(f'SELECT generation,marker,failures FROM {self.schema}.domain_playbooks WHERE domain=$1', domain)
        result = dict(row)
        if isinstance(result['marker'], str):
            result['marker'] = json.loads(result['marker'])
        return result

    async def record_playbook(self, domain: str, page_hash: str, generation: int,
                              attempted: bool | None, confirmed: dict | None) -> None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(f'SELECT generation,marker,failures,confirmations FROM {self.schema}.domain_playbooks WHERE domain=$1 FOR UPDATE', domain)
                if row is None:
                    return
                state = dict(row)
                for key in ('marker', 'confirmations'):
                    if isinstance(state[key], str):
                        state[key] = json.loads(state[key])
                if not _advance(state, page_hash, generation, attempted, confirmed):
                    return
                await conn.execute(f'''UPDATE {self.schema}.domain_playbooks SET generation=$2,
                    marker=$3::jsonb,failures=$4,confirmations=$5::jsonb WHERE domain=$1''',
                    domain, state['generation'], json.dumps(state['marker']) if state['marker'] else None,
                    state['failures'], json.dumps(state['confirmations']))
