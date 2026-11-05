"""One offline test per numbered Market Lab founder acceptance row.

Reuse the shipped path proofs rather than duplicate their fixtures or weaken
assertions. These run production parsers, handlers, SQL and local transports;
Node cases exercise the exact Workspace model, not a live browser deployment.
"""
from trigger_signin_fakes import set_founders
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tank'), str(ROOT / 'agents/market_lab')]
import test_market_lab as early
import test_market_lab_review as review
import test_vault_contract as vault_contract
import test_market_lab_evidence as evidence
import test_market_lab_source_pages as pages
import test_market_lab_documents as documents
import test_market_lab_gate2 as gate2
import test_market_lab_ml3 as ml3
import test_market_lab_ml5 as ml5
import test_market_lab_ml6 as ml6
import test_market_lab_wave4 as wave4
import test_market_quarantine_proxy as quarantine
from test_market_lab_ml3 import database as database
from test_market_lab_ml5 import room_app as room_app
from test_market_lab_ml6 import ledger as ledger, receiver as receiver
from test_tiger_alert_email import catcher as catcher


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    route = AsyncMock(side_effect=AssertionError('placeholder: acceptance must not call a model'))
    monkeypatch.setattr(ml5.TankClient, 'route', route)
    yield
    route.assert_not_called()


def node_case(name):
    result = subprocess.run(['node', '--experimental-strip-types', '--import',
        str(ROOT / 'tests/market_lab_register.mjs'), '--test',
        '--test-name-pattern=^' + name + '$',
        str(ROOT / 'workspace/app/market-lab/model.test.ts')],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '# pass 1' in result.stdout, result.stdout


async def alert(database, monkeypatch, mode):
    import market_lab_ml3
    monkeypatch.setattr(market_lab_ml3, 'room', AsyncMock(return_value={'status': 'queued'}))
    thread, card = await ml3.proposal(database, 'market_lab.alerts.' + mode)
    if mode == 'email':
        assert await database.pool.fetchval('SELECT count(*) FROM tank.market_lab_alerts') == 0
    response = await database.client.post('/v1/command/cards/' + card, json={'action': 'confirm'})
    assert response.status_code == 200
    assert response.json()['result']['status'] == mode
    assert response.json()['result']['cost_usd'] == 0
    saved = await database.pool.fetchrow('SELECT * FROM tank.market_lab_alerts WHERE tenant_id=$1', ml3.OWNER)
    assert saved['email_enabled'] is (mode == 'email')
    assert saved['webhook_url'] is None


def test_R01():
    node_case("no readings leave the on section empty, and a store error is its own state")


@pytest.mark.asyncio
async def test_R02():
    await evidence.test_every_public_feed_has_rows_but_fixtures_never_appear_in_the_client_path()


def test_R03(monkeypatch):
    evidence.test_missing_keys_never_start_a_fetch(monkeypatch)


@pytest.mark.asyncio
async def test_R04():
    await evidence.test_failed_last_run_turns_off_without_destroying_old_documents()


def test_R05():
    node_case("linked pages count checks without inventing a change")


@pytest.mark.asyncio
async def test_R06():
    await evidence.test_each_figure_links_to_an_exact_immutable_stored_row()


@pytest.mark.asyncio
async def test_R07():
    await pages.test_pages_are_newest_first_and_citations_keep_immutable_indexes()


@pytest.mark.asyncio
async def test_R08():
    await documents.test_pdf_answer_page_and_forget_isolated()


@pytest.mark.asyncio
async def test_R09():
    await documents.test_tables_go_through_guard_and_delete('csv')


@pytest.mark.asyncio
async def test_R10():
    await documents.test_tables_go_through_guard_and_delete('xlsx')


@pytest.mark.asyncio
async def test_R11():
    await documents.test_pdf_answer_page_and_forget_isolated()


@pytest.mark.asyncio
async def test_R12(database, monkeypatch):
    node_case("plugin state sent to the browser is a set of booleans and never a saved secret")
    headers = install_vault(database, monkeypatch)
    value = 'placeholder-secret-only-in-offline-fixture'
    response = await database.client.post('/v1/vaults/lab.vault/secrets', headers=headers,
        json={'tenant_id': str(ml3.OWNER), 'name': 'EIA_API_KEY', 'purpose': 'placeholder', 'value': value})
    assert response.status_code == 200 and response.json() == {'ok': True}
    listed = await database.client.get('/v1/vaults/lab.vault/plugins', headers=headers,
                                       params={'tenant_id': str(ml3.OWNER)})
    assert listed.status_code == 200 and value not in listed.text
    assert listed.json()['secrets'][0]['name'] == 'EIA_API_KEY'
    assert listed.json()['secrets'][0]['mask'] == '••••••••'
    removed = await database.client.delete('/v1/vaults/lab.vault/secrets', headers=headers,
        params={'tenant_id': str(ml3.OWNER), 'name': 'EIA_API_KEY'})
    assert removed.status_code == 200
    assert (await database.client.get('/v1/vaults/lab.vault/plugins', headers=headers,
        params={'tenant_id': str(ml3.OWNER)})).json()['secrets'] == []


def test_R13():
    node_case("an off vault shows the plain sentence and drops any secret that arrived with it")


@pytest.mark.asyncio
async def test_R14(monkeypatch):
    await gate2.test_tank_research_job_writes_only_claims_with_openable_sources(monkeypatch)


@pytest.mark.asyncio
async def test_R15(database, monkeypatch):
    await ml3.test_read_receipts_and_tenant_scope(database, monkeypatch)


@pytest.mark.asyncio
async def test_R16(database, monkeypatch):
    await wave4.test_warning_issues_and_returns_frozen_wilson_confidence(database, monkeypatch, 'available')


@pytest.mark.asyncio
async def test_R17(database, monkeypatch):
    await wave4.test_warning_issues_and_returns_frozen_wilson_confidence(database, monkeypatch, 'missing')


@pytest.mark.asyncio
async def test_R18(database, monkeypatch):
    gate2.test_calibration_excludes_legacy_unmeasurable_duplicates_and_other_tenants()
    await ml3.test_read_receipts_and_tenant_scope(database, monkeypatch)


@pytest.mark.asyncio
async def test_R19(database, room_app, monkeypatch):
    await ml5.test_confirmed_read_receipt_pagination_and_exact_command_without_planner(database, room_app, monkeypatch, 'patterns')


@pytest.mark.asyncio
async def test_R20(database, room_app, monkeypatch):
    await ml5.test_confirmed_read_receipt_pagination_and_exact_command_without_planner(database, room_app, monkeypatch, 'gate')
    ml5.test_gate_opening_date_matches_exact_ninety_day_boundary(timedelta(microseconds=-1), False)
    ml5.test_gate_opening_date_matches_exact_ninety_day_boundary(timedelta(), True)


@pytest.mark.asyncio
async def test_R21(database, monkeypatch):
    await wave4.test_curve_is_binned_tenant_scoped_zero_cost_and_never_uses_planner(database, monkeypatch)


@pytest.mark.asyncio
async def test_R22(monkeypatch):
    await ml3.test_room_feeds_returns_registered_key_names_without_values(monkeypatch)


@pytest.mark.asyncio
async def test_R23(database, monkeypatch):
    await alert(database, monkeypatch, 'email')


@pytest.mark.asyncio
async def test_R24(database, monkeypatch, caplog):
    await ml3.test_confirm_once_and_no_secret_in_history_or_logs(database, monkeypatch, caplog)
    # The independent delivery path is covered by row 26.


@pytest.mark.asyncio
async def test_R25(database, ledger, catcher, receiver, monkeypatch):
    await ml6.test_alerts_off_sends_nothing(database, ledger, catcher, receiver)
    await alert(database, monkeypatch, 'off')


@pytest.mark.asyncio
async def test_R26(database, ledger, catcher, receiver):
    await ml6.test_once_per_channel_saved_body_and_signature(database, ledger, catcher, receiver)


@pytest.mark.asyncio
async def test_R27(ledger):
    await ml6.test_closed_prediction_is_held_with_reason_and_open_is_queued(ledger, 89, 'held')


@pytest.mark.asyncio
async def test_R28(database, ledger, monkeypatch):
    await ml6.test_last_twelve_briefs_are_tenant_scoped_zero_cost_code_read(database, ledger, monkeypatch)


@pytest.mark.asyncio
async def test_R29():
    await wave4.test_every_fixture_brief_sentence_has_an_exact_source_row_and_url()


@pytest.mark.asyncio
async def test_R30(database, monkeypatch):
    await wave4.test_scored_events_require_keys_regions_exact_stage_and_owned_evidence(database, monkeypatch, ('LEGISCAN_API_KEY',))
    wave4.test_event_pairs_have_independent_measured_lag_histories()


@pytest.mark.asyncio
async def test_R31(database, monkeypatch):
    await wave4.test_scored_events_require_keys_regions_exact_stage_and_owned_evidence(database, monkeypatch, ('NOAA_TOKEN',))
    wave4.test_event_pairs_have_independent_measured_lag_histories()


@pytest.mark.asyncio
async def test_R32(database, monkeypatch):
    await wave4.test_scored_events_require_keys_regions_exact_stage_and_owned_evidence(database, monkeypatch, ())


@pytest.mark.asyncio
async def test_R33(monkeypatch):
    await quarantine.test_release_forwards_the_room_key_and_does_not_retire(monkeypatch)
    await quarantine.test_a_non_founder_is_not_found_and_the_room_is_not_called(monkeypatch)


@pytest.mark.asyncio
async def test_R34(monkeypatch):
    await quarantine.test_remove_marks_lineage_only_after_the_room_accepts(monkeypatch)
    await evidence.test_removed_observations_are_not_reused_in_answers()


@pytest.mark.asyncio
async def test_R35(monkeypatch, capsys):
    await early.test_fred_live_read_returns_source_numbers_and_stores_nothing(monkeypatch, capsys)


@pytest.mark.asyncio
async def test_R36(monkeypatch, capsys):
    await early.test_fred_stays_off_when_the_key_is_missing(monkeypatch, capsys)


def test_R37():
    node_case("search hits feeds and linked pages, and skips a question with no reading")


@pytest.mark.asyncio
async def test_R38(database, monkeypatch):
    import socket
    from contextlib import asynccontextmanager
    from uuid import uuid4
    import httpx
    from fastapi import FastAPI
    from chassis.db import ensure_schema
    from core.feed_links import build_router
    from core.ledger import PostgresLedger

    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_:
                        [(2, 1, 6, '', ('93.184.216.34', 443))])
    async with database.pool.acquire() as conn:
        await ensure_schema(conn, 'market_lab')
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        @asynccontextmanager
        async def context():
            yield ledger
        app = FastAPI()
        app.include_router(build_router(key_ok=lambda key: key == 'placeholder-room',
                                        ledger_context=context, engine='ffl'))
        owner, other, ident = ml3.OWNER, ml3.OTHER, uuid4()
        params = {'tenant_id': str(owner), 'region': 'us-east'}
        headers = {'x-tank-key': 'placeholder-room'}
        path = '/market/feeds/' + str(ident)
        payload = {'url': 'https://www.census.gov/data.html',
                   'label': 'placeholder source', 'frequency': 'weekly'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url='http://placeholder') as client:
            added = await client.put(path, params=params, headers=headers, json=payload)
            assert added.status_code == 200 and added.json() == {'ok': True}
            listed = (await client.get('/market/feeds', params=params, headers=headers)).json()['links']
            assert len(listed) == 1 and listed[0]['url'] == payload['url']
            assert listed[0]['frequency'] == 'weekly' and listed[0]['status'] == 'not_checked'
            foreign = {**params, 'tenant_id': str(other)}
            assert (await client.get('/market/feeds', params=foreign, headers=headers)).json()['links'] == []
            await client.delete(path, params=foreign, headers=headers)
            assert len((await client.get('/market/feeds', params=params, headers=headers)).json()['links']) == 1
            removed = await client.delete(path, params=params, headers=headers)
            assert removed.status_code == 200
            assert (await client.get('/market/feeds', params=params, headers=headers)).json()['links'] == []
            rejected = await client.put(path, params=params, headers=headers,
                                        json={**payload, 'url': 'http://localhost/private'})
            assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_R39(database, monkeypatch):
    headers = install_vault(database, monkeypatch)
    payload = {'tenant_id': str(ml3.OWNER), 'name': 'placeholder connection',
               'server_url': 'https://placeholder.example/mcp', 'auth_type': 'provider'}
    response = await database.client.post('/v1/vaults/lab.vault/connections', headers=headers, json=payload)
    assert response.status_code == 200
    listed = (await database.client.get('/v1/vaults/lab.vault/plugins', headers=headers,
                                       params={'tenant_id': str(ml3.OWNER)})).json()['connections']
    assert len(listed) == 1 and listed[0]['server_url'] == payload['server_url']
    assert listed[0]['name'] == 'placeholder connection' and listed[0]['has_token'] is False
    assert listed[0]['status'] == 'needs_auth'
    removed = await database.client.delete('/v1/vaults/lab.vault/connections/' + listed[0]['id'],
        headers=headers, params={'tenant_id': str(ml3.OWNER)})
    assert removed.status_code == 200
    rejected = await database.client.post('/v1/vaults/lab.vault/connections', headers=headers,
        json={**payload, 'server_url': 'http://localhost/private'})
    assert rejected.status_code == 422
    vault_contract.test_links_and_connections_require_public_https_without_credentials('http://localhost/private')


@pytest.mark.asyncio
async def test_R40():
    await review.test_revisions_are_labelled_and_only_the_current_value_answers()


@pytest.mark.asyncio
async def test_R41():
    await pages.test_mixed_document_focuses_the_cited_kind_and_answer_marks_notices()


@pytest.mark.asyncio
async def test_R42():
    await wave4.test_unsourced_recommendations_are_omitted_and_empty_brief_is_held()


@pytest.mark.asyncio
async def test_R43():
    from core.evidence import overview, save_check
    from core.ledger import MemoryLedger
    from feeds.catalog import sources
    from feeds.collect import collect, EvidenceClient
    from datetime import UTC, datetime
    ledger = MemoryLedger()
    owner = str(ml3.OWNER)
    for source_id, expected in (('eia_diesel', '3.86'), ('census_population', '110')):
        spec = next(source for source in sources('ffl') if source.id == source_id)
        result = collect(spec, fixtures=str(ROOT / 'tests/fixtures/feeds'),
                         backfill=True, client=EvidenceClient())
        assert any(str(point['value']) == expected for point in result['points'])
        await save_check(ledger, owner, result, at=datetime(2026, 11, 3, tzinfo=UTC))
    shown = await overview(ledger, owner, 'ffl', fixtures=True)
    assert shown['on_count'] == 2
    for source_id in ('eia_diesel', 'census_population'):
        feed = next(feed for feed in shown['feeds'] if feed['id'] == source_id)
        assert feed['state'] == 'on' and feed['rows'] > 0 and feed['document_id']


def install_vault(database, monkeypatch):
    """Real vault routes/SQL; replace only room listing and external MCP discovery."""
    from types import SimpleNamespace
    import httpx
    import vault
    import vault_routes
    import mcp_connections
    set_founders(monkeypatch, 'placeholder-admin')
    monkeypatch.setattr(vault_routes, 'seal', vault.seal)
    monkeypatch.setattr(mcp_connections, 'discover', AsyncMock(return_value=[]))
    runtime = SimpleNamespace(pool=lambda: database.pool, box_region=lambda: 'us-east',
        TANK_API_KEY='placeholder-workspace-key', _http=SimpleNamespace(request=AsyncMock(
            return_value=httpx.Response(200, json={'links': []}))))
    database.app.include_router(vault_routes.build_router(runtime))
    return {'x-tank-key': runtime.TANK_API_KEY, 'x-tervory-user': 'placeholder-admin',
            'x-tervory-squad': 'market_lab', 'x-tervory-tenant': str(ml3.OWNER)}
