"""Saved public shop pages; real check path; no external requests or models."""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

import asyncpg
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'agents/tiger'), str(ROOT / 'agents/_chassis'), str(ROOT / 'tests')]
from test_tiger import _load  # noqa: E402
import watch as watcher  # noqa: E402
from domain_playbooks import public_marker, public_page  # noqa: E402

READER = _load('playbook_test_reader', ROOT / 'tank/skills/tiger.price_extract/1.1.0/run.py')
HOST = 'books.toscrape.com'
RAW_MARKER = {'primary': 'dom', 'dom': 'scope:div.product_main|p.price_color'}
MARKER = public_marker(RAW_MARKER)
A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
SAVED = ROOT / 'tests/tiger_alert_page/fixtures/live'
PAGES = [
    ('a-light-in-the-attic_1000', SAVED / 'books-toscrape-com--a-light-in-the-attic.html'),
    ('tipping-the-velvet_999', SAVED / 'books-toscrape-com--tipping-the-velvet.html'),
    ('soumission_998', SAVED / 'books-toscrape-com--soumission.html'),
    ('offline-fourth', Path(__file__).parent / 'fixtures/fourth.html'),
]


@pytest_asyncio.fixture(params=['memory', 'postgres'])
async def store(request):
    if request.param == 'memory':
        yield watcher.MemoryStore()
        return
    dsn = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not dsn:
        pytest.skip('Disposable loopback Postgres required for persistence cases')
    assert urlsplit(dsn).hostname in {'localhost', '127.0.0.1', '::1'}
    schema = 'playbook_test_' + uuid4().hex
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        async with pool.acquire() as conn:
            await conn.execute(f'CREATE SCHEMA {schema}')
            await watcher.ensure_tables(conn, schema)
            await watcher.ensure_tables(conn, schema)
        yield watcher.PgStore(pool, schema)
    finally:
        async with pool.acquire() as conn:
            await conn.execute(f'DROP SCHEMA {schema} CASCADE')
        await pool.close()


async def forbidden(*args, **kwargs):
    raise AssertionError('No model, OCR, extra fetch or external request is permitted')


async def check(store, number, *, tenant=A, html=None, path=None, host=HOST, extra=None):
    saved_path, file = PAGES[number % 4]
    url = f'https://{host}/catalogue/{path or saved_path}/index.html'
    body = html if html is not None else file.read_text()
    async def render(*args):
        return {'ok': True, 'url': url, 'html': body, **(extra or {})}
    async def extract(html, address):
        return READER.extract(html, address)
    current = {'tenant_id': tenant, 'url': url, 'threshold': '0', 'alert_price': False, 'alert_stock': False}
    return await watcher.run_check(store, tenant, current, 'tiger', render, extract, forbidden,
                                   forbidden, watcher.DomainLimiter(0), now=lambda: datetime(2026, 10, 28, tzinfo=timezone.utc) + timedelta(seconds=number))


async def promote(store):
    for index in range(3):
        result = await check(store, index, tenant=A if index % 2 == 0 else B)
        assert result['status'] == 'observed' and not result['observation']['issue']
        snapshot = await store.get_playbook(HOST)
        assert snapshot['marker'] == (MARKER if index == 2 else None)
    return snapshot


async def shared_rows(store):
    if isinstance(store, watcher.MemoryStore):
        return store.playbooks
    async with store.pool.acquire() as conn:
        return [dict(row) for row in await conn.fetch(f'SELECT * FROM {store.schema}.domain_playbooks')]


@pytest.mark.asyncio
async def test_three_saved_pages_promote_fourth_uses_playbook_across_tenants(store, monkeypatch):
    await promote(store)
    def forbidden_learning(*args):
        raise AssertionError('The fourth page must use the playbook before learning')
    monkeypatch.setattr(watcher, 'learn_layout', forbidden_learning)
    result = await check(store, 3, tenant=B)
    assert result['price'] == '27.40' and result['observation']['issue'] is None
    assert (await store.get_playbook(HOST))['marker'] == MARKER
    # A second tenant does not inherit the first tenant's observation/history.
    first_url = f'https://{HOST}/catalogue/{PAGES[0][0]}/index.html'
    assert await store.latest_observation(B, first_url) is None


@pytest.mark.asyncio
async def test_repeats_tenants_queries_and_fragments_are_not_three_pages(store):
    for suffix in ('', '?client=private-one', '#private-two', '?client=private-three'):
        url = f'https://{HOST}/catalogue/one/index.html' + suffix
        page = public_page(url, {'ok': True, 'html': 'public'})
        snapshot = await store.get_playbook(HOST)
        await store.record_playbook(*page, snapshot['generation'], None, MARKER)
    assert (await store.get_playbook(HOST))['marker'] is None


@pytest.mark.asyncio
async def test_mismatch_falls_back_without_breaking_other_pages_and_success_resets(store):
    await promote(store)
    changed = PAGES[3][1].read_text().replace('price_color', 'sale-price')
    result = await check(store, 4, html=changed, path='changed-one')
    assert result['price'] == '27.40'
    assert result['observation']['evidence'] and (await store.get_playbook(HOST))['failures'] == 1
    assert (await check(store, 5, path='still-original'))['price'] == '53.74'
    assert (await store.get_playbook(HOST))['failures'] == 0


@pytest.mark.asyncio
async def test_three_consecutive_changes_retire_then_require_three_fresh_confirmations(store):
    active = await promote(store)
    changed = PAGES[3][1].read_text().replace('price_color', 'sale-price')
    for index in range(3):
        result = await check(store, index + 4, html=changed, path=f'changed-{index}')
        assert result['price'] == '27.40'
        state = await store.get_playbook(HOST)
        assert state['failures'] == index + 1
        assert state['marker'] == (MARKER if index < 2 else None)
    assert state['generation'] > active['generation']
    # A late success from before retirement cannot revive the old playbook.
    page = public_page(f'https://{HOST}/old', {'ok': True, 'html': 'public'})
    await store.record_playbook(*page, active['generation'], True, MARKER)
    assert (await store.get_playbook(HOST))['marker'] is None
    for index in range(3):
        await check(store, index + 7, html=changed, path=f'fresh-{index}')
        marker = (await store.get_playbook(HOST))['marker']
        assert marker == (public_marker({'primary': 'dom', 'dom': 'scope:div.product_main|p.sale-price'}) if index == 2 else None)


@pytest.mark.asyncio
async def test_known_url_guard_stays_in_control_and_failures_retire_shared_marker(store):
    await promote(store)
    for index in range(3):
        changed = PAGES[index][1].read_text().replace('price_color', 'sale-price')
        result = await check(store, index + 4, tenant=A if index % 2 == 0 else B,
                             html=changed, path=PAGES[index][0])
        assert result['status'] == "can't read" and result['price'] is None
    assert (await store.get_playbook(HOST))['marker'] is None


@pytest.mark.asyncio
async def test_domain_and_public_private_boundaries(store):
    await promote(store)
    assert (await store.get_playbook('other.' + HOST))['marker'] is None
    for flag in ({'login_status': 'logged in'}, {'private': True}, {'challenge': True},
                 {'portal_item': {'name': 'Private customer item', 'price': '9', 'currency': 'GBP', 'quantity': 3}}):
        await check(store, 3, host='private.example', extra=flag)
    assert 'private.example' not in json.dumps(await shared_rows(store))


@pytest.mark.asyncio
async def test_shared_records_contain_only_public_structure_and_opaque_page_fingerprints(store):
    secret_layout = {**RAW_MARKER, 'tenant_id': A, 'name': 'CLIENT-NAME-SENTINEL', 'html': 'CLIENT-HTML-SENTINEL', 'price': 'PRIVATE-PRICE'}
    for index in range(3):
        page = public_page(f'https://{HOST}/product-{index}?email=CLIENT-EMAIL-SENTINEL', {'ok': True, 'html': 'public'})
        snapshot = await store.get_playbook(HOST)
        await store.record_playbook(*page, snapshot['generation'], None, secret_layout)
        dumped = json.dumps(await shared_rows(store))
        for value in (A, B, 'tenant_id', 'CLIENT-', 'PRIVATE-', 'https://', '/product-'):
            assert value not in dumped
    assert (await store.get_playbook(HOST))['marker'] == MARKER
    personalized = public_marker({'primary': 'dom', 'dom': 'scope:div.CLIENT-NAME-SENTINEL|p.price'})
    assert personalized and 'CLIENT-' not in json.dumps(personalized)


@pytest.mark.asyncio
async def test_custom_class_names_work_without_entering_shared_state(store, monkeypatch):
    for index in range(3):
        html = PAGES[index][1].read_text().replace('price_color', 'shop-price')
        assert (await check(store, index, html=html))['status'] == 'observed'
    assert (await store.get_playbook(HOST))['marker']
    assert 'shop-price' not in json.dumps(await shared_rows(store))
    def no_learning(*args):
        raise AssertionError('Custom classes must use the shared fingerprint')
    monkeypatch.setattr(watcher, 'learn_layout', no_learning)
    html = PAGES[3][1].read_text().replace('price_color', 'shop-price')
    assert (await check(store, 3, html=html))['price'] == '27.40'
    # The fingerprint also survives the existing per-URL evidence format.
    assert (await check(store, 7, html=html))['price'] == '27.40'


@pytest.mark.asyncio
async def test_failed_candidate_page_cannot_leave_a_stale_confirmation(store):
    await check(store, 0)
    await check(store, 1)
    changed = PAGES[0][1].read_text().replace('price_color', 'sale-price')
    await check(store, 4, html=changed, path=PAGES[0][0])
    await check(store, 2)
    assert (await store.get_playbook(HOST))['marker'] is None
    await check(store, 3)
    assert (await store.get_playbook(HOST))['marker'] == MARKER


@pytest.mark.parametrize('url', ['https://user:password@shop.example/item', 'http://127.0.0.1/item',
                               'http://store.local/item', 'https://shop.example:8443/item', 'file:///item'])
def test_nonpublic_identity_never_enters_shared_store(url):
    assert public_page(url, {'ok': True, 'html': 'public'}) is None


@pytest.mark.asyncio
async def test_persistence_and_concurrent_confirmation_use_distinct_pages(store):
    snapshot = await store.get_playbook(HOST)
    async def confirm(index):
        page = public_page(f'https://{HOST}/page-{index}', {'ok': True, 'html': 'public'})
        await store.record_playbook(*page, snapshot['generation'], None, MARKER)
    await asyncio.gather(*(confirm(index) for index in (0, 0, 1)))
    assert (await store.get_playbook(HOST))['marker'] is None
    await confirm(2)
    if isinstance(store, watcher.PgStore):
        restarted = watcher.PgStore(store.pool, store.schema)
        assert (await restarted.get_playbook(HOST))['marker'] == MARKER
    assert (await store.get_playbook(HOST))['marker'] == MARKER
