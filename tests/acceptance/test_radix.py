"""One offline scenario per Radix founder row (R01–R58).

Exercise shipped handlers with their existing fake-service harnesses, not a
second implementation. Postgres/Redis are disposable loopback stores; HTTP
is ASGI/MockTransport and scanner output/pages are local fixtures.
"""
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import test_command_radix as command_passive
import test_command_radix_active as active_command
import test_command_radix_repo as repo
import test_radix_active_consent as consent
import test_radix_business as business
import test_radix_business_routes as business_routes
import test_radix_deploy_gate as deploy
import test_radix_gold as gold
import test_radix_iac as iac
import test_radix_infra as infra
import test_radix_passive as passive
import test_radix_report as reports
import test_radix_scheduler_budget as budget
import test_radix_weekly as weekly
import test_rx1_scans as source
import test_rx4_compliance as notices
from radix_i2 import test_active as active
from radix_i8 import test_events as laws
from radix_r6 import test_checks as r6
from tenant_bus import test_radix_events as bus_events
from tenant_bus.conftest import bus as bus

ROOT = Path(__file__).resolve().parents[2]
runtime = repo.runtime
command_pool = repo.command_pool
api = repo.api
repo_api = repo.repo_api
checkov_fixture = repo.fake_checkov

@pytest.fixture
def fake_checkov(checkov_fixture, monkeypatch):
    # Checkov's fixture enables every system tool. Keep this acceptance harness
    # on its real in-process static/secret engines and the one fake IaC CLI.
    monkeypatch.setenv('RADIX_USE_SYSTEM_TOOLS', '0')
    monkeypatch.setattr(iac.iac, 'checkov_bin', lambda: str(checkov_fixture))
    return checkov_fixture


@pytest_asyncio.fixture
async def database(command_pool):
    # The real Command harness gives every case its own disposable database.
    # Mount the room schema there so parallel acceptance cases never truncate
    # another worker's passive/watch/weekly queue.
    async with command_pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_radix')
        await conn.execute((ROOT / 'agents/radix/schema.sql').read_text())
        await conn.execute(passive.store.DDL)
    yield passive.store.Store(command_pool)


@pytest_asyncio.fixture
async def pool(database):
    # Use CI's existing Radix DB setting, not a second opt-in that CI lacks.
    async with database.pool.acquire() as conn:
        await conn.execute('TRUNCATE agent_radix.page_hashes')
    yield database.pool


@pytest.fixture(scope='session')
def redis_url():
    configured = os.environ.get('TENANT_BUS_REDIS_URL')
    if configured:
        from urllib.parse import urlsplit
        assert urlsplit(configured).hostname in {'localhost', '127.0.0.1', '::1'}
        yield configured
        return
    name = ROOT.name + '-redis-' + uuid4().hex
    docker = ['docker', '--host=unix:///var/run/docker.sock']
    env = {key: value for key, value in os.environ.items() if key not in {
        'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'}}
    subprocess.run([*docker, 'run', '-d', '--rm', '--label', 'tervory.test=1',
        '--name', name, '-p', '127.0.0.1::6379', 'redis:7.4.12'],
        check=True, capture_output=True, env=env)
    try:
        port = subprocess.check_output([*docker, 'port', name, '6379'], text=True, env=env).strip().rsplit(':', 1)[1]
        yield 'redis://127.0.0.1:' + port + '/0'
    finally:
        subprocess.run([*docker, 'rm', '-f', name], check=True, capture_output=True, env=env)



@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('RADIX_USE_SYSTEM_TOOLS', '0')
    monkeypatch.delenv('RADIX_EGRESS_REVOKED', raising=False)
    monkeypatch.setattr(passive.gateway, 'private_bind_address', lambda: '127.0.0.1')
    async def refuse(*args, **kwargs):
        raise AssertionError('placeholder acceptance attempted external HTTP/DNS')
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', refuse)
    monkeypatch.setattr(passive.gateway.dns.asyncresolver, 'resolve', refuse)


@pytest_asyncio.fixture
async def business_api(monkeypatch):
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    app = FastAPI()
    app.state.pool = business_routes.Store()
    async def run_skill(tenant, skill, body):
        return business.ENGINE.analyse(skill.removeprefix('radix.'), body, tenant)
    app.state.tank = SimpleNamespace(run_skill=AsyncMock(side_effect=run_skill))
    business_routes.ROUTES.attach(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://radix-room',
                               headers={'X-Tank-Key': 'placeholder-room-key'}) as client:
        yield client, app


async def business_roundtrip(business_api, skill, payload=None):
    client, app = business_api
    payload = payload or business.fixture()
    response = await client.post('/verify/' + skill, json=payload)
    assert response.status_code == 201, response.text
    result = response.json()
    read = await client.get('/verify/runs/' + result['id'], params={'tenant_id': payload['tenant_id']})
    assert read.status_code == 200 and read.json() == result
    foreign = await client.get('/verify/runs/' + result['id'], params={'tenant_id': business.OTHER})
    assert foreign.status_code == 404
    app.state.tank.run_skill.assert_awaited_with(payload['tenant_id'], 'radix.' + skill, payload)
    return result


@pytest.mark.asyncio
async def test_r01_business_verification(business_api):
    await business_roundtrip(business_api, 'verify_business')
    business.BusinessEvidenceTests().test_official_fixture_verifies_with_sources()


@pytest.mark.asyncio
async def test_r02_entity_links(business_api):
    await business_roundtrip(business_api, 'entity_links')
    business.BusinessEvidenceTests().test_company_address_and_agent_links_use_both_records()


@pytest.mark.asyncio
async def test_r03_account_links(business_api):
    await business_roundtrip(business_api, 'account_links')
    business.BusinessEvidenceTests().test_banned_seller_link_requires_client_business_evidence()


@pytest.mark.asyncio
async def test_r04_site_observations(business_api):
    payload = business.fixture()
    payload['lookup']['value'] = payload['businesses'][1]['id']
    await business_roundtrip(business_api, 'site_risk', payload)
    business.BusinessEvidenceTests().test_site_observations_and_lookalike_have_sources()


@pytest.mark.asyncio
async def test_r05_supported_risk_score(business_api):
    await business_roundtrip(business_api, 'business_risk')
    checks = business.BusinessEvidenceTests()
    checks.test_score_is_deterministic_bounded_and_all_factors_are_sourced()
    checks.test_missing_evidence_never_becomes_a_finding_or_a_safe_verdict()


@pytest.mark.asyncio
async def test_r06_business_scope_and_rejection(business_api):
    client, app = business_api
    for lookup in ({'kind': 'email', 'value': 'placeholder@example.test'},
                   {'kind': 'phone', 'value': '+12025550199'},
                   {'kind': 'name', 'value': 'Placeholder Person'}):
        payload = business.fixture()
        payload['lookup'] = lookup
        assert (await client.post('/verify/business_risk', json=payload)).status_code == 400
    payload = business.fixture()
    payload['region'] = 'za'
    assert (await client.post('/verify/business_risk', json=payload)).status_code == 400
    assert app.state.pool.calls == []
    app.state.tank.run_skill.assert_not_awaited()
    business.BusinessEvidenceTests().test_tenant_crossovers_reject_before_analysis()


def test_r07_handed_over_static_source(runtime):
    import test_command
    test_command.test_scan_adapter_preserves_packaged_skill_input(runtime)
    source.test_skill_engines_match_the_radix_scanners()
    source.test_javascript_concat_is_critical_and_a_placeholder_is_not()
    source.test_remote_source_is_refused()


@pytest.mark.asyncio
async def test_r08_tar_scan_confirm_receipts(repo_api, monkeypatch, fake_checkov):
    await repo.test_confirmed_archive_all_scanners_redacted_and_zero_receipts(repo_api, monkeypatch, fake_checkov, 'tar')


@pytest.mark.asyncio
async def test_r09_zip_confirm_replay(repo_api, monkeypatch, fake_checkov):
    await repo.test_confirmed_archive_all_scanners_redacted_and_zero_receipts(repo_api, monkeypatch, fake_checkov, 'zip')


@pytest.mark.asyncio
async def test_r10_foreign_upload_and_traversal(repo_api, monkeypatch):
    await repo.test_invalid_archive_and_foreign_upload_never_reach_room(repo_api, monkeypatch, 'other-tenant', 'tar')
    source.test_zip_slip_is_refused()


def test_r11_unavailable_iac_is_incomplete(monkeypatch, tmp_path):
    iac.test_missing_checkov_qualifies_summary_and_never_claims_complete(monkeypatch)
    iac.test_unavailable_or_failed_checkov_is_not_run(tmp_path, monkeypatch, 'bad-json')


@pytest.mark.asyncio
async def test_r12_txt_challenge_confirm(api, runtime, monkeypatch):
    await command_passive.test_confirm_dispatch_and_tenant_binding(api, runtime, monkeypatch, *command_passive.CASES[0])


@pytest.mark.asyncio
async def test_r13_complete_passive_persistence(database, monkeypatch):
    await passive.test_complete_request_persists_clean_receipt_and_releases_lease(database, monkeypatch)


@pytest.mark.asyncio
async def test_r14_failed_passive_never_clean(database):
    await passive.test_execute_persists_error_not_clean_when_tool_fails(database)


@pytest.mark.asyncio
async def test_r15_txt_loss_stops_watch(pool, monkeypatch):
    for reason in ('txt_missing', 'txt_changed'):
        await laws.test_r4_missing_or_changed_txt_stops_without_scan(pool, monkeypatch, reason)


def test_r16_passive_proxy_scope_and_bounds(monkeypatch):
    with monkeypatch.context() as scope:
        passive.test_proxy_single_host_redirect_storage_and_dns_rebinding(scope)
    passive.test_loopback_proxy_rejects_outside_host_and_expired_lease()


@pytest.mark.asyncio
async def test_r17_promotion_gate_fresh_matching_receipt(database, monkeypatch):
    await passive.test_postgres_receipt_gate_bus_and_restart(database, monkeypatch)
    for status, age, high, critical, allowed in (
        ('complete', 0, 0, 0, True), ('complete', 3601, 0, 0, False),
        ('complete', 0, 1, 0, False), ('complete', 0, 0, 1, False), ('pending', 0, 0, 0, False)):
        passive.test_gate_fails_closed(status, age, high, critical, allowed)


@pytest.mark.asyncio
async def test_r18_watch_enable_list_and_shared_lease(pool):
    await laws.test_r4_due_watch_runs_one_and_compares_then_unwatches(pool)


@pytest.mark.asyncio
async def test_r19_changes_and_unwatch(pool):
    await laws.test_r4_due_watch_runs_one_and_compares_then_unwatches(pool)
    r6.test_changes_card_displays_states_items_and_fixed_findings_without_new_labels()


@pytest.mark.asyncio
async def test_r20_page_hash_baseline_and_gone(pool, tmp_path):
    r6.test_page_changes_and_unchanged_hash()
    await r6.test_snapshot_atomic_complete_and_tenant_scoped(pool, tmp_path)
    await r6.test_linked_page_404_is_gone_but_500_is_incomplete(tmp_path)


def test_r21_tls_and_certificate_measurements():
    r6.test_expiry_reuses_real_checker(10, 'tls-expiring')
    r6.test_partial_tls_json_retains_only_completed_objects()


@pytest.mark.asyncio
async def test_r22_clamav_baked_signature(tmp_path):
    await r6.test_tools_find_eicar_axe_cookies_and_preserve_only_measurements(tmp_path)


@pytest.mark.asyncio
async def test_r23_partial_checks_preserve_baseline(pool, tmp_path):
    await r6.test_memory_failure_skipped_other_checks_continue(tmp_path)
    await r6.test_skipped_check_cannot_fix_or_replace_complete_baseline(pool)


def test_r24_notice_checkers_use_their_own_text():
    for label in ('CCPA', 'CPRA'):
        r6.test_ccpa_notice_uses_existing_checker_without_new_wording(label)
    notices.test_missing_privacy_link_is_one_medium_finding()
    notices.test_saved_popia_notice_is_accepted_without_following_links('popia-link.html')


@pytest.mark.asyncio
async def test_r25_cookie_metadata_without_values(tmp_path):
    await r6.test_tools_find_eicar_axe_cookies_and_preserve_only_measurements(tmp_path)


@pytest.mark.asyncio
async def test_r26_axe_preserves_measured_rule_and_severity(tmp_path):
    await r6.test_tools_find_eicar_axe_cookies_and_preserve_only_measurements(tmp_path)


@pytest.mark.asyncio
async def test_r27_regulation_recheck_notice_cookie_only(pool):
    laws.test_both_bus_shapes(laws.FACTS)
    laws.test_both_bus_shapes({'document_id': 'a'*64, 'version_id': 'b'*64})
    await laws.test_worker_only_notice_cookie_and_shared_watch_lock(pool)


@pytest.mark.asyncio
async def test_r28_event_dedupe_tenant_queue_atomicity(pool, monkeypatch):
    await laws.test_queue_dedup_isolation_atomic_and_event_data(pool)
    await laws.test_consumer_ack_only_after_queue_and_fail_errors(monkeypatch)


@pytest.mark.asyncio
async def test_r29_bus_retry_deadletter_and_pair_guard(bus, monkeypatch):
    await bus_events.test_malformed_regulation_delivery_retries_then_dead_letters(bus, monkeypatch)
    await laws.test_http_corridor_all_room_event_pairs(monkeypatch)


@pytest.mark.asyncio
async def test_r30_founder_active_same_lock_separate_bounds(pool, monkeypatch, tmp_path):
    active.test_allowlist_and_plan(tmp_path)
    await active.test_shared_running_lock_lease_and_active_results(pool, monkeypatch)


@pytest.mark.asyncio
async def test_r31_unlisted_unproved_refused_before_requests(pool):
    await active.test_unlisted_and_unproved_before_any_http(pool)


@pytest.mark.asyncio
async def test_r32_block_cap_timeout_never_clean(tmp_path):
    for mode in ('blocked', 'timeout', 'cap', 'lost-response', 'rule-timeout'):
        folder = tmp_path / mode
        folder.mkdir()
        await active.test_collect_never_calls_blocked_or_timeout_clean(folder, mode)


@pytest.mark.asyncio
async def test_r33_member_and_unconfirmed_active_refused(runtime, monkeypatch):
    active_command.test_admin_or_founder_single_url_and_existing_presentation(runtime)
    await active_command.test_direct_unconfirmed_corridor_and_wrong_user_refused(runtime, monkeypatch)


@pytest.mark.asyncio
async def test_r34_admin_written_consent_receipt(api, runtime, database, monkeypatch):
    client, pool = api
    runtime.app = FastAPI()
    runtime.pool = lambda: pool
    runtime.app.include_router(consent.radix_passive_routes.build_router(runtime))
    room = FastAPI()
    room.state.pool = database.pool
    passive.routes.attach(room)
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('TANK_KEY_RADIX', 'placeholder-room-key')
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix','placeholder-founder')", consent.TENANT)
    headers = {'x-tervory-user': 'placeholder-admin', 'x-tervory-role': 'org:admin'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room)) as http:
        runtime._http = http
        thread = (await client.post('/v1/command/threads', json={}, headers=headers)).json()['thread_id']
        args = {'domain': consent.DOMAIN, 'consent_text': 'placeholder founder-approved fixture consent'}
        response = await client.post(f'/v1/command/threads/{thread}/actions',
            json={'tool': 'radix.active.consent', 'arguments': args}, headers=headers)
        assert response.status_code == 200, response.text
        card = response.json()
        assert card['status'] == 'pending'
        assert await database.consent_id(consent.TENANT, consent.DOMAIN) is None
        path = '/v1/command/cards/' + card['card_id']
        result = (await client.post(path, json={'action': 'confirm'}, headers=headers)).json()
        assert result['status'] == 'confirmed', result
        ident = await database.consent_id(consent.TENANT, consent.DOMAIN)
        assert ident is not None
        assert (await client.post(path, json={'action': 'confirm'}, headers=headers)).json() == result
    async with database.pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM agent_radix.active_consents WHERE tenant_id=$1', consent.TENANT)
        assert len(rows) == 1
        assert rows[0]['domain'] == consent.DOMAIN and rows[0]['consent_text'] == args['consent_text']
        assert rows[0]['granted_by'] == 'placeholder-admin' and rows[0]['granted_at']
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT cost_usd,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2',
            consent.TENANT, UUID(result['result']['ledger_id']))
        assert row['cost_usd'] == 0 and row['model'] == 'code'


@pytest.mark.asyncio
async def test_r35_client_active_requires_fresh_proof(database, monkeypatch):
    for proven in (True, False):
        await consent.test_consented_scan_uses_fresh_proof_before_fake_scanner(database, monkeypatch, proven)


@pytest.mark.asyncio
async def test_r36_withdrawal_revokes_active_lease(database, monkeypatch):
    await consent.test_client_runtime_proof_same_lock_and_withdraw_revoke(database, monkeypatch)


@pytest.mark.asyncio
async def test_r37_top100_connect_and_scoped_dns(tmp_path):
    infra.test_proxy_scope_ports_public_address_dns_and_shared_bounds()
    await infra.test_collector_flags_proxy_coverage_and_keeps_tool_findings(tmp_path, True)


@pytest.mark.asyncio
async def test_r38_missing_infra_coverage_stays_incomplete(tmp_path):
    infra.test_proxy_scope_ports_public_address_dns_and_shared_bounds()
    await infra.test_collector_flags_proxy_coverage_and_keeps_tool_findings(tmp_path, False)


@pytest.mark.asyncio
async def test_r39_infra_consent_and_single_running_lock(database, monkeypatch):
    await infra.test_infra_admission_refuses_no_consent_or_txt_and_uses_one_lock(database, monkeypatch)


@pytest.mark.asyncio
async def test_r40_weekly_durable_pair_restart_dedupe(database, monkeypatch):
    await weekly.test_durable_pair_once_per_week_expired_challenge_and_scheduler_lock(database, monkeypatch)


@pytest.mark.asyncio
async def test_r41_withdrawal_cancels_weekly_pair(database):
    await weekly.test_withdrawal_cancels_queued_week_and_no_consent_never_enrolls(database)


@pytest.mark.asyncio
async def test_r42_worker_allows_bounded_weekly_infra(monkeypatch):
    await budget.test_weekly_infra_reaches_its_scan_budget_through_the_real_worker(monkeypatch)


@pytest.mark.asyncio
async def test_r43_verified_own_main_bundle_gate_provenance(repo_api, tmp_path, monkeypatch):
    await deploy.test_verified_founder_bundle_flows_from_confirmed_repo_scan_to_app_gate(repo_api, tmp_path, monkeypatch)


def test_r44_critical_holds_only_affected_app(monkeypatch, tmp_path):
    deploy.test_deploy_blocks_only_one_app_and_continues_other_apps(monkeypatch, tmp_path)


@pytest.mark.asyncio
async def test_r45_confirmed_override_and_receipt(api, runtime, monkeypatch):
    await deploy.test_scan_materialization_is_tenant_app_and_commit_scoped_then_confirm_override(api, runtime, monkeypatch)


def test_r46_unreachable_gate_fails_open(monkeypatch, capsys):
    deploy.test_unreachable_tank_fails_open_without_disclosing_key(monkeypatch, capsys)


@pytest.mark.asyncio
async def test_r47_only_complete_descendant_clears_hold(api, runtime, monkeypatch):
    await deploy.test_complete_descendant_scan_resolves_older_partial_scan_cannot_clear(api, runtime, monkeypatch)


def test_r48_every_finding_escaped_with_evidence(monkeypatch):
    reports.test_every_finding_escaped_counts_and_private_evidence_links(monkeypatch)


@pytest.mark.asyncio
async def test_r49_repository_report_download_and_zero_receipt(api, runtime, monkeypatch):
    await reports.test_real_scan_kinds_download_tenant_scoped_with_zero_receipt(api, runtime, monkeypatch, 'repo')


@pytest.mark.asyncio
async def test_r50_real_private_room_report_corridor(api, runtime, database, monkeypatch):
    from passive_store import watch_artifact
    client, _ = api
    room = FastAPI()
    room.state.pool = database.pool
    passive.routes.attach(room)
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('TANK_KEY_RADIX', 'placeholder-room-key')
    await database.issue(reports.TENANT, consent.DOMAIN)
    await database.watch(reports.TENANT, consent.DOMAIN, 'daily')
    granted = await database.consent(reports.TENANT, consent.DOMAIN, 'placeholder-admin', 'placeholder consent')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room)) as http:
        runtime._http = http
        for mode in ('passive', 'watch', 'active'):
            options = {'watched': True} if mode == 'watch' else (
                {'active': True, 'consent_id': UUID(granted['id'])} if mode == 'active' else {})
            ident = await database.create(reports.TENANT, consent.URL, watch_artifact(consent.DOMAIN), **options)
            assert await database.running(reports.TENANT, ident)
            await database.complete(reports.TENANT, ident, [{'tool': 'zap', 'rule': 'placeholder-' + mode,
                'severity': 'low', 'file': consent.URL, 'line': 0}])
            path = f'/v1/command/radix/reports/{ident}'
            download = await client.get(path + '/html')
            assert download.status_code == 200, download.text
            assert 'placeholder-' + mode in download.text and download.text.count('<article>') == 1
            evidence = await client.get(path + '/evidence/0')
            assert evidence.status_code == 200 and evidence.json()['rule'] == 'placeholder-' + mode
            foreign = await client.get(path + '/html', headers={'x-tervory-tenant': str(reports.OTHER)})
            assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_r51_partial_and_pending_reports(runtime, monkeypatch):
    await reports.test_clients_need_radix_and_cannot_select_tenant_or_pdf_imports(runtime, monkeypatch)
    await reports.test_real_scan_required_pending_and_unknown_are_not_reports(runtime, monkeypatch)


@pytest.mark.asyncio
async def test_r52_optional_existing_pdf_without_external_assets(api, runtime, monkeypatch):
    client, pool = api
    runtime.pool = lambda: pool
    runtime.app = FastAPI()
    runtime.app.include_router(reports.command.router)
    async def load(actor, scan_id):
        assert scan_id == reports.JOB and actor.tenant_id == reports.TENANT
        return reports.fixture()
    monkeypatch.setattr(reports.report, 'load', load)
    detect_pdf = reports.report.pdf_available
    monkeypatch.setattr(reports.report, 'pdf_available', lambda: False)
    path = f'/v1/command/radix/reports/{reports.JOB}'
    assert (await client.get(path + '/html')).status_code == 200
    # Optional format availability is capability detection, not a missing route.
    assert (await client.get(path + '/pdf')).status_code == 404
    seen = []
    class HTML:
        def __init__(self, *, string, url_fetcher):
            assert string.count('<article>') == 12
            with pytest.raises(ValueError, match='external resource refused'):
                url_fetcher('https://placeholder.example/asset')
            seen.append(string)
        def write_pdf(self):
            return b'%PDF-placeholder-offline-renderer'
    monkeypatch.setitem(sys.modules, 'weasyprint', SimpleNamespace(HTML=HTML))
    # Exercise the real capability detector with a fake already-installed module.
    monkeypatch.setattr(reports.report, 'pdf_available', detect_pdf)
    file = await client.get(path + '/pdf')
    assert file.status_code == 200 and file.content.startswith(b'%PDF-')
    assert file.headers['content-type'] == 'application/pdf' and len(seen) == 1
    assert file.headers['cache-control'] == 'private, no-store'


def test_r53_existing_result_workspace_auth_corridor():
    reports.test_actual_workspace_download_corridor_and_existing_result_label()


@pytest.mark.asyncio
async def test_r54_exact_iac_candidate_eval(monkeypatch):
    await iac.test_room_eval_auth_and_exact_skill_version(monkeypatch)


@pytest.mark.asyncio
async def test_r55_private_frozen_gold_sources(monkeypatch):
    await gold.test_room_key_only_limits_and_no_services(monkeypatch)
    monkeypatch.setenv('TANK_REGION', 'us-east')
    gold.test_frozen_answers_match_skills_and_independent_business_truth()


@pytest.mark.asyncio
async def test_r56_tenant_catalogue_and_job_isolation(repo_api, runtime, monkeypatch):
    repo.test_client_catalogue_and_no_injected_authority(runtime)
    await repo.test_findings_refuse_foreign_or_mismatched_job(repo_api, monkeypatch, 'result')


def test_r57_clean_source_observations():
    source.test_clean_tree_has_zero_criticals()


def test_r58_legacy_fixed_host_header_check(monkeypatch):
    import importlib.util
    path = ROOT / 'agents/radix/tests/test_live_scan.py'
    spec = importlib.util.spec_from_file_location('placeholder_radix_legacy', path)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    monkeypatch.delenv('RADIX_ALLOWED_HOSTS', raising=False)
    legacy.test_only_the_approved_home_page_is_accepted()
    legacy.test_missing_headers_are_findings_and_cookie_values_are_dropped()
    legacy.test_off_host_redirect_is_not_followed()
    legacy.test_one_same_host_redirect_is_followed()
    legacy.test_csp_nonce_is_not_stored()
    legacy.test_wider_allowlist_is_refused_before_transport(monkeypatch)


def test_sheet_has_exactly_one_fixture_case_per_row():
    sheet = (ROOT / 'docs/acceptance/radix.md').read_text()
    rows = re.findall(r'^\| (R\d\d)\b', sheet, flags=re.M)
    cases = [match[1].upper() for name, value in globals().items()
             if callable(value) and (match := re.fullmatch(r'test_(r\d\d)_\w+', name))]
    names = re.findall(r'^\| R\d\d `([a-z0-9_]+)`', sheet, flags=re.M)
    assert names == [name for name in globals() if re.fullmatch(r'test_r\d\d_\w+', name)]
    assert len(rows) == len(set(rows)) == 58
    assert rows == cases == [f'R{number:02}' for number in range(1, 59)]
    settings = (ROOT / 'docs/ops/FOUNDER-SETTINGS.md').read_text()
    for row in sheet.splitlines():
        if re.match(r'^\| R\d\d\b', row):
            for setting in re.findall(r'\b[A-Z][A-Z0-9]+_[A-Z0-9_]+\b', row.split('|')[-2]):
                assert setting in settings, setting
