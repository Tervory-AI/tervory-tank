"""One offline shipped-path scenario per Tiger founder check (TG01–TG51).

ASGI rooms, saved HTML, disposable SQL and local SMTP replace external services.
The fixture harnesses are shared with Tiger's regression suites; no product
implementation or model/provider response is recreated here.
"""
import ast
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hmac
import os
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, HTTPException

import command
import test_access1 as sources
import test_access1_sources as archives
import test_ledger_sql_param as ledger
import test_rig_locate_checkout as locate
import test_tiger as core
import test_tiger_alert_email as mail
import test_tiger_alerts_read as alerts
import test_tiger_competitors as matches
import test_tiger_watch_commands as watches
import test_tiger_works as works
from rig_tiger_prices import test_cycle as cycle
from rig_tiger_prices import test_prices as prices
from tiger_brain import test_tg3 as brain
from tiger_g5 import test_alerts as g5
from tiger_g5 import test_integration as g5_jobs
from tiger_g5 import conftest as g5_fixtures
from tiger_playbooks import test_playbooks as playbooks
from tiger_works.fixture import PAGE as HTML_PAGE, URL as HTML_URL, extract, no_paid_call
from watch import DomainLimiter, MemoryStore, dispatch_tenant, run_check

ROOT = Path(__file__).resolve().parents[2]
postgres = matches.postgres
database = matches.database
offline_dns = matches.offline_dns
corridor = matches.corridor
watch_runtime = watches.runtime
catcher = mail.catcher
keys = sources.keys
access_app = sources.app
cycle_database = cycle.database
g5_database = g5_fixtures.database


@asynccontextmanager
async def reused(factory, *args):
    """Keep an existing async fixture's setup and teardown intact."""
    generator = factory.__wrapped__(*args)
    try:
        yield await anext(generator)
    finally:
        await generator.aclose()


@pytest_asyncio.fixture
async def alert_runtime(database, monkeypatch):
    # One sheet row collects once; the separate regression suite still proves
    # both storage backends. These cases use its real Postgres-backed fixture.
    async with reused(alerts.runtime, SimpleNamespace(param='postgres'), database, monkeypatch) as runtime:
        yield runtime


@pytest_asyncio.fixture
async def rig_system(cycle_database, monkeypatch):
    async with reused(prices.corridor, monkeypatch) as relay:
        yield await cycle.system.__wrapped__(cycle_database, relay, monkeypatch)


@pytest_asyncio.fixture
async def g5_system(g5_database, monkeypatch):
    async with reused(prices.corridor, monkeypatch) as relay:
        yield await g5_jobs.system.__wrapped__(g5_database, relay, monkeypatch)


def node(script, *args, row=None, timeout=240):
    env = dict(os.environ)
    if row:
        env['TIGER_ACCEPTANCE_ROW'] = row
    # CI installs these pinned test-only tools; a builder may supply its own
    # already-installed prefix. Neither path installs during an offline test.
    env.setdefault('TIGER_TEST_TOOLS', str(ROOT / 'tests/acceptance/tiger-browser/node_modules'))
    result = subprocess.run(['node', script, *args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.asyncio
async def test_tg01_watch_reads_actual_page_html(watch_runtime):
    action = command.validate_action(command.PlannedAction(tool='tiger.watch', arguments={'url': HTML_URL}), watch_runtime.actor)
    status, created = await command.dispatch_action(action, watch_runtime.actor)
    assert status == 201 and created['every'] == '1d'
    watch = await watch_runtime.store.get_watch(str(watches.TENANT), HTML_URL)
    seen = []
    async def render(url, session, room, tenant):
        seen.append((url, tenant))
        return {'ok': True, 'html': HTML_PAGE.read_text()}
    result = await run_check(watch_runtime.store, str(watches.TENANT), watch, 'tiger', render,
                             extract, no_paid_call, no_paid_call, DomainLimiter(0))
    assert result['status'] == 'observed' and result['price'] == '120.00'
    assert seen == [(HTML_URL, str(watches.TENANT))]
    watch_runtime.main.app.add_api_route('/v1/tiger/observations', watch_runtime.main.tiger_observations,
        methods=['GET'], dependencies=[Depends(watch_runtime.main.require_key)])
    action = command.validate_action(command.PlannedAction(tool='tiger.read', arguments={'url': HTML_URL}), watch_runtime.actor)
    status, result = await command.dispatch_action(action, watch_runtime.actor)
    assert status == 200
    readings = result['observations']
    assert readings[0]['price'] == '120.00'
    assert readings[0]['currency'] == 'USD' and readings[0]['product_name']
    assert readings[0]['availability'] == 'InStock'
    assert await watch_runtime.store.list_observations(str(watches.OTHER), HTML_URL) == []


@pytest.mark.asyncio
async def test_tg02_only_page_intervals_and_daily_default(watch_runtime):
    watches.test_interval_choices_match_existing_tiger_page_and_paid_kind_matches_single()
    for tool in ('tiger.watch', 'tiger.watch.bulk'):
        await watches.test_invalid_interval_is_refused_before_room_call(watch_runtime, tool)
        for every in ('15m', '1h', '6h', '12h', '1d'):
            args = {'url': watches.URL} if tool == 'tiger.watch' else {'pages': [watches.URL]}
            action = command.validate_action(command.PlannedAction(tool=tool, arguments={**args, 'every': every}), watch_runtime.actor)
            assert action.arguments['every'] == every
    await watches.test_single_watch_default_reaches_actual_room(watch_runtime)


@pytest.mark.asyncio
async def test_tg03_watch_list_is_scoped_and_free(watch_runtime):
    await watches.test_list_scopes_leaky_room_and_records_tiger_code_receipt(watch_runtime)


@pytest.mark.asyncio
async def test_tg04_pause_only_exact_owned_watch(watch_runtime):
    await watches.test_changes_target_only_exact_owned_url(watch_runtime, 'pause')
    due = await dispatch_tenant(watch_runtime.store, str(watches.TENANT), datetime.now(timezone.utc))
    assert watches.URL not in due['queued']


@pytest.mark.asyncio
async def test_tg05_resume_restores_due_dispatch(watch_runtime):
    await watches.test_changes_target_only_exact_owned_url(watch_runtime, 'resume')
    await watches.test_pause_excludes_dispatch_and_resume_restores_it(watch_runtime)


@pytest.mark.asyncio
async def test_tg06_remove_only_exact_owned_watch(watch_runtime):
    await watches.test_changes_target_only_exact_owned_url(watch_runtime, 'remove')


@pytest.mark.asyncio
async def test_tg07_paid_bulk_card_creates_only_new_daily_urls(watch_runtime, database, monkeypatch):
    await watches.test_real_cards_confirm_paid_bulk_and_code_changes_once(watch_runtime, database, monkeypatch)
    # The durable-card exercise removes its initial watch. A fresh fixture scope
    # preserves the independent five-page/default/duplicate regression inputs.
    with monkeypatch.context() as scoped:
        async with reused(watches.runtime, scoped) as fresh:
            await watches.test_bulk_creates_five_daily_watches_counts_duplicates_and_foreign_url(fresh)


@pytest.mark.asyncio
async def test_tg08_bulk_limits_and_private_destinations(watch_runtime):
    for pages in ([], [watches.URL] * 51, ['file:///tmp/page']):
        await watches.test_bulk_argument_refusals_do_not_call_room(watch_runtime, pages)
    for url in ('http://127.0.0.1/page', 'http://10.0.0.1/page', 'https://private.placeholder.example/page'):
        await watches.test_bulk_private_addresses_are_refused_by_room_checker(watch_runtime, url)


@pytest.mark.asyncio
async def test_tg09_each_change_requires_own_confirmation(watch_runtime):
    for operation in watches.CHANGES:
        await watches.test_every_change_requires_confirmation_before_room_call(watch_runtime, operation)
        await watches.test_foreign_confirmation_is_not_authority(watch_runtime, operation)


@pytest.mark.asyncio
async def test_tg10_watch_read_and_history_tenant_boundary(monkeypatch):
    await works.test_two_tenants_cannot_read_or_remove_each_others_saved_page_job(monkeypatch)


@pytest.mark.asyncio
async def test_tg11_price_change_email_once(catcher):
    core.test_price_move_uses_a_strict_threshold()
    await mail.test_five_saved_pages_send_only_changed_page_once(catcher)


@pytest.mark.asyncio
async def test_tg12_stock_change_email_once(catcher):
    store = MemoryStore()
    watch = await store.create_watch({**core._watch(), 'url': mail.URL, 'alert_price': False})
    await mail.checked(store, watch)
    changed = await mail.checked(store, watch, stock='OutOfStock', at=core.NOW + timedelta(minutes=1))
    assert [row['kind'] for row in changed['alerts']] == ['stock']
    assert (await mail.checked(store, watch, stock='OutOfStock', at=core.NOW + timedelta(minutes=2)))['alerts'] == []
    assert (await mail.deliver_pending(store, core.TENANT_A, transport=catcher.transport,
                                     recipient='placeholder@example.invalid'))['sent'] == 1
    assert (await mail.deliver_pending(store, core.TENANT_A, transport=catcher.transport,
                                     recipient='placeholder@example.invalid'))['sent'] == 0
    assert len(catcher.messages) == 1 and mail.URL in catcher.messages[0].get_content()


@pytest.mark.asyncio
async def test_tg13_new_product_agent_to_email(g5_system, catcher, monkeypatch):
    await g5_jobs.test_agent_job_to_existing_email_path(g5_system, catcher, monkeypatch, 'new_product')
    await g5.test_listing_empty_baseline_reorder_failed_check_and_recovery(MemoryStore())


@pytest.mark.asyncio
async def test_tg14_below_own_cost_agent_to_email(g5_system, catcher, monkeypatch):
    await g5_jobs.test_agent_job_to_existing_email_path(g5_system, catcher, monkeypatch, 'below_cost')
    await g5.test_cost_requires_own_matching_row_currency_and_transition(MemoryStore())


@pytest.mark.asyncio
async def test_tg15_market_gap_agent_to_email(g5_system, catcher, monkeypatch):
    await g5_jobs.test_agent_job_to_existing_email_path(g5_system, catcher, monkeypatch, 'market_gap')
    await g5.test_market_gap_counts_muted_competitor_unknowns_own_stock_and_staleness(MemoryStore())


@pytest.mark.asyncio
async def test_tg16_all_five_chat_alerts_are_free(alert_runtime):
    await alerts.test_all_five_saved_kinds_and_data_only_counts(alert_runtime)


@pytest.mark.asyncio
async def test_tg17_chat_alert_filters_and_receipts(alert_runtime):
    for kind in alerts.KINDS:
        await alerts.test_kind_filter_and_one_tiger_zero_receipt(alert_runtime, kind)
    alert_runtime.inject_foreign = True
    data = await alerts.read(alert_runtime, url=alerts.URL)
    assert {row['url'] for row in data['alerts']} == {alerts.URL}
    assert all(str(alerts.OTHER) not in row['after'] for row in data['alerts'])
    assert (await alert_runtime.client.get('/v1/command/tiger/alerts', params={'kind': 'placeholder-unknown'})).status_code == 422


@pytest.mark.asyncio
async def test_tg18_preferences_apply_to_reads_and_queued_mail(catcher, monkeypatch):
    await works.test_alert_preferences_reach_tank_and_tiger_routes(monkeypatch)
    for source in ('page', 'feed', 'portal'):
        await works.test_preferences_apply_to_saved_readings_and_changes(False, False, source)
    for kind in g5.KINDS:
        await g5.test_switch_off_prevents_email_and_preserves_other_tenant(MemoryStore(), catcher, kind, True)
        catcher.messages.clear()


@pytest.mark.asyncio
async def test_tg19_email_retry_and_uncertain_acceptance(catcher, monkeypatch):
    await mail.test_rejected_send_retries_after_backoff_without_duplicate(catcher)
    catcher.messages.clear()
    await mail.test_failed_receipt_after_acceptance_cannot_resend(catcher, monkeypatch)
    mail.test_tenant_address_is_explicit_and_tiger_settings_are_separate(monkeypatch)


def test_tg20_blocked_or_unreadable_never_invents_prices():
    core.test_blocked_pages_do_not_invent_a_price_or_fetch_robots()
    node('--test', '--test-name-pattern=failed checks|missing or invalid|nameless', 'tests/tiger_works/workspace.test.cjs')


@pytest.mark.asyncio
async def test_tg21_rig_product_watch_updates_only_own_sku(rig_system):
    await cycle.test_one_cycle_price_stock_and_tenant_isolation(rig_system)


@pytest.mark.asyncio
async def test_tg22_rig_ineligible_watch_is_cancelled(rig_system):
    await cycle.test_product_becoming_ineligible_stops_before_next_read(rig_system, 'deleted')


@pytest.mark.asyncio
async def test_tg23_read_only_check_now_uses_explicit_stock():
    await locate.test_tiger_check_now_reads_only_explicit_stock_on_watched_pages()


@pytest.mark.asyncio
async def test_tg24_gtin_auto_match_uses_evidence(corridor):
    await matches.test_exact_gtin_links_with_evidence_and_all_handmade_watch_defaults(corridor)


@pytest.mark.asyncio
async def test_tg25_brand_mpn_requires_confirmation(corridor):
    await matches.test_brand_mpn_requires_a_bound_confirm_card_and_is_tenant_scoped(corridor)


@pytest.mark.asyncio
async def test_tg26_review_is_bounded_scoped_and_free(corridor, monkeypatch):
    await matches.test_review_read_is_tenant_scoped_newest_first_bounded_and_receipted(corridor)
    monkeypatch.setattr(matches.access, 'tiger_catalogue', AsyncMock(side_effect=HTTPException(503)))
    response = await corridor.client.get('/v1/access/tiger/matches')
    assert response.status_code == 200
    rows = response.json()['matches']
    assert len(rows) == 100 and all(row['identifiers']['seen']['mpn'] == 'ABC-1' for row in rows)
    assert all(row['product']['name'] is None for row in rows)


@pytest.mark.asyncio
async def test_tg27_reject_undo_confirm_are_durable(corridor, monkeypatch):
    await matches.test_review_buttons_use_real_durable_cards_and_decision_routes(corridor, monkeypatch)
    match_id = str(await corridor.pool.fetchval("SELECT id FROM agent_tiger.matches WHERE tenant_id=$1 AND state='confirmed'", matches.TENANT))
    assert UUID(match_id)
    assert (await matches.decision(corridor, match_id, 'undo', matches.OTHER)).status_code == 404
    assert (await matches.decision(corridor, match_id, 'undo')).status_code == 409


@pytest.mark.asyncio
async def test_tg28_position_uses_real_latest_prices(corridor):
    await matches.test_position_figures_use_latest_tenant_reading_and_zero_receipt(corridor)


def test_tg29_unknown_prices_never_claim_rank():
    matches.test_position_ties_missing_and_cross_currency_are_not_guessed()
    node('--test', '--test-name-pattern=position excludes|ties, currency|unsafe links', 'tests/tiger_position/workspace.test.cjs')


@pytest.mark.asyncio
async def test_tg30_saved_site_checks_use_immutable_own_run(corridor):
    await matches.test_saved_site_checks_use_only_own_latest_run_and_immutable_sightings(corridor)


def test_tg31_approved_populated_frames_and_buttons():
    output = node('tests/tiger_position/browser.cjs', row='TG31')
    assert len(re.findall(r'^256-\d+ changed pixels', output, re.M)) == 6


def test_tg32_approved_empty_frames_and_no_false_empty():
    output = node('tests/tiger_position/browser.cjs', row='TG32')
    assert len(re.findall(r'^267-\d+ changed pixels', output, re.M)) == 4


def test_tg33_plugins_off():
    assert 'TG33 passed' in node('tests/acceptance/tiger_ui.cjs', row='TG33')


def test_tg34_plugins_write_only_key():
    assert 'TG34 passed' in node('tests/acceptance/tiger_ui.cjs', row='TG34')


def test_tg35_plugins_files():
    assert 'TG35 passed' in node('tests/acceptance/tiger_ui.cjs', row='TG35')


def test_tg36_plugins_saved_links():
    assert 'TG36 passed' in node('tests/acceptance/tiger_ui.cjs', row='TG36')


def test_tg37_plugins_hidden_mcp_token():
    assert 'TG37 passed' in node('tests/acceptance/tiger_ui.cjs', row='TG37')


@pytest.mark.asyncio
async def test_tg38_private_sources_and_public_fallback(access_app, monkeypatch):
    await sources.test_portal_prices_never_cross_tenants(access_app)
    for failure in ('miss', 'http', 'timeout', 'json', 'shape'):
        await works.test_failed_or_missing_feed_reads_public_page_without_robots_gate(monkeypatch, failure)


@pytest.mark.asyncio
async def test_tg39_only_owning_tiger_browser_releases_credentials(access_app):
    server, db, actor = access_app
    row, values = sources.make_connection(actor.tenant_id, room='tiger')
    db.rows[(actor.tenant_id, 'tiger', row['site'])] = row
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url='http://placeholder.invalid') as client:
        for tenant, site, allowed in ((actor.tenant_id, row['site'], True), (uuid4(), row['site'], False),
                                     (actor.tenant_id, 'https://other.example', False)):
            envelope = sources.vault.envelope('tiger', 'request', {'tenant_id': str(tenant), 'site': site, 'action': 'release'})
            response = await client.post('/v1/access/browser/tiger', json=envelope)
            assert response.status_code == 200
            data = sources.vault.open_envelope('tiger', 'response', response.json())
            assert ('credential' in data) is allowed
            if allowed:
                assert hmac.compare_digest(data['credential']['password'], values['password'])
            assert all(value not in response.text for value in values.values() if value)
        row['revoked'] = True
        envelope = sources.vault.envelope('tiger', 'request', {'tenant_id': str(actor.tenant_id), 'site': row['site'], 'action': 'release'})
        response = await client.post('/v1/access/browser/tiger', json=envelope)
        assert 'credential' not in sources.vault.open_envelope('tiger', 'response', response.json())
    await sources.test_vault_scope_and_browser_keys_cannot_be_substituted(None)


@pytest.mark.asyncio
async def test_tg40_human_handback_preserves_same_live_page(keys, monkeypatch, tmp_path):
    await sources.test_hand_back_preserves_same_live_page(keys, monkeypatch, tmp_path, 'tiger')
    await sources.test_live_control_refuses_ordinary_room_key_and_replay(keys)


@pytest.mark.asyncio
async def test_tg41_archives_are_dated_public_only(monkeypatch, access_app):
    await archives.test_retry_backoff_then_dated_archive(monkeypatch)
    await archives.test_captcha_never_uses_archive_as_bypass()
    await sources.test_private_site_never_sent_to_archives(access_app, monkeypatch)


@pytest.mark.asyncio
async def test_tg42_code_playbook_promotion_and_retirement(monkeypatch):
    with monkeypatch.context() as scoped:
        await playbooks.test_three_saved_pages_promote_fourth_uses_playbook_across_tenants(MemoryStore(), scoped)
    await playbooks.test_repeats_tenants_queries_and_fragments_are_not_three_pages(MemoryStore())
    await playbooks.test_three_consecutive_changes_retire_then_require_three_fresh_confirmations(MemoryStore())
    await playbooks.test_shared_records_contain_only_public_structure_and_opaque_page_fingerprints(MemoryStore())


def test_tg43_correction_stays_unverified(tmp_path):
    feedback = core._load('placeholder_acceptance_correction', ROOT / 'agents/tiger/gold_feedback.py')
    row = feedback.record_correction(page_id='placeholder-product', layout='placeholder-layout',
        expected_price='$12.00', html='<h1>Fixture product</h1><span class="product-price">$12.00</span>',
        url='https://placeholder.invalid/product', currency='usd', inbox=tmp_path / 'corrections.jsonl')
    assert row['verified'] is False and row['split'] == 'inbox'
    assert row['expected_price'] == '12.00' and row['source'] == 'client_correction'
    assert (tmp_path / 'placeholder-product.html').exists()


def test_tg44_brain_off_and_optional_topology_sealed(monkeypatch, capsys, tmp_path):
    brain.test_optional_services_reuse_pinned_runtime_and_sandbox_without_caller()
    for profile in (False, True):
        brain.test_actual_compose_profile_model_excludes_optional_services_by_default(profile)
    brain.test_isolation_checker_passes_own_topology_and_uses_supplied_sandbox(monkeypatch, capsys, 'tiger')
    brain.test_seal_accepts_optional_pair(tmp_path)
    brain.test_extra_networks_cannot_weaken_tiger_brain_seal(tmp_path, 'tiger-sandbox', True)


@pytest.mark.asyncio
async def test_tg45_brain_owning_key_guards_and_ledger(monkeypatch):
    with monkeypatch.context() as scoped:
        runtime = brain.corridor.__wrapped__(scoped)
        await brain.test_foreign_and_workspace_keys_cannot_use_tiger_brain_route(runtime, 'placeholder-base-key')
        await brain.test_tiger_owning_key_keeps_policy_guard_and_durable_ledger(runtime)
    with monkeypatch.context() as scoped:
        fresh = brain.corridor.__wrapped__(scoped)
        await brain.test_pause_and_model_refusal_prevent_any_gateway_send(fresh)
    with monkeypatch.context() as scoped:
        setup = ledger.setup.__wrapped__(scoped)
        await ledger.test_hostile_room_never_reaches_sql(setup, "tiger'); DELETE FROM tank.ledger; --")


@pytest.mark.asyncio
async def test_tg46_missing_tiger_squad_refuses_work(watch_runtime):
    for tool in ('tiger.watches', *('tiger.watch.' + op for op in watches.CHANGES)):
        await watches.test_no_squad_cannot_access_watch_commands(watch_runtime, tool)
    for tool in ('tiger.alerts', 'tiger.matches', 'tiger.position'):
        with pytest.raises(HTTPException) as refused:
            command.validate_action(command.PlannedAction(tool=tool, arguments={}), watch_runtime.actor)
        assert refused.value.status_code == 403


def test_tg47_shipped_price_and_ocr_skill_cases():
    core.test_saved_skill_cases_pass_offline()
    core.test_ocr_confidence_is_lower_than_html_and_uses_the_tiger_box()
    packages = core.skala.load_packages(ROOT / 'tank/skills')
    for skill, version in (('tiger.price_extract', '1.1.0'), ('tiger.price_structured', '1.0.0')):
        package = packages[(skill, version)]
        module = core._load('placeholder_acceptance_' + skill.replace('.', '_'), package.path / 'run.py')
        async def cases(package=package, module=module):
            for case in package.cases:
                result = await module.run(case['input'], None)
                ok, why = core.skala.score_case(case['expected'], result, case['tolerance'])
                assert ok, f'{package.ref}: {why}'
        asyncio.run(cases())


def test_tg48_existing_history_and_search_are_real_data():
    node('--test', 'tests/tiger_works/workspace.test.cjs')


@pytest.mark.asyncio
async def test_tg49_shared_rig_url_reads_once(rig_system):
    await cycle.test_shared_url_updates_each_sku_once_with_one_read(rig_system)


@pytest.mark.asyncio
async def test_tg50_rig_delivery_retry_without_reread(rig_system, monkeypatch):
    await cycle.test_failed_send_is_durable_retries_without_rereading_and_keeps_tenant(rig_system, monkeypatch)


@pytest.mark.asyncio
async def test_tg51_rig_changed_url_rebinds(rig_system):
    await cycle.test_url_change_cancels_old_read_and_rebinds_to_new_page(rig_system)


def test_sheet_has_exactly_one_fixture_case_per_row(request):
    sheet = (ROOT / 'docs/acceptance/tiger.md').read_text()
    rows = re.findall(r'^\| (TG\d\d) `test_(tg\d\d)_\*`', sheet, re.M)
    expected = [f'TG{i:02}' for i in range(1, 52)]
    assert [row[0] for row in rows] == expected
    assert all(identity.lower() == function for identity, function in rows)
    tree = ast.parse(Path(__file__).read_text())
    cases = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and re.match(r'test_tg\d\d_', node.name)]
    assert [re.match(r'test_(tg\d\d)_', case.name)[1].upper() for case in cases] == expected
    collected = [item for item in request.session.items if Path(str(item.path)) == Path(__file__)
                 and re.match(r'test_tg\d\d_', item.name)]
    # A full run must collect each row once, not once per fixture backend.
    if len(collected) >= 51:
        assert len(collected) == 51 and all('[' not in item.name for item in collected)


def test_sheet_settings_are_in_founder_settings_and_env_example():
    sheet = (ROOT / 'docs/acceptance/tiger.md').read_text()
    settings = (ROOT / 'docs/ops/FOUNDER-SETTINGS.md').read_text()
    example = (ROOT / '.env.example').read_text()
    names = set(re.findall(r'\b(?:TIGER_SMTP_[A-Z_]+|TIGER_BRAIN_ENABLED|SANDBOX_KEY_TIGER|RIG_TIGER_CHECK_KEY|TANK_VAULT_KEY|ACCESS_BROWSER_KEY_TIGER)\b', sheet))
    assert names and all(name in settings and name + '=' in example for name in names)
