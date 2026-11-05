"""One offline scenario per Tisan founder acceptance row (T01–T56).

Reuse the shipped path and its existing fixture harness, not a parallel product
implementation. HTTP boundaries are ASGI/MockTransport; Postgres is disposable.
UI scenarios execute actual TSX in Chromium with only server boundaries stubbed.
"""
import os
import json
from datetime import datetime
from pathlib import Path
import subprocess

import pytest
import pytest_asyncio

import test_tisan_builder as builds
import test_tisan_figma_live as figma
import test_tisan_gold_sources as gold
import test_tisan_k6 as k6
import test_tisan_publish as publication
import test_tisan_quality as quality
import test_tisan_quotes_designed as quotes
import test_tisan_requests as requests
import test_tisan_wave4_pipeline as flows
import test_tisan_wave4_promotion as production
import test_tisan_wave4_repo as scans
from tisan_promotion import test_promotion as promotions

ROOT = Path(__file__).resolve().parents[2]
# Keep existing fixture dependencies and their real DB/HTTP behavior intact.
runtime = requests.runtime
command_pool = requests.command_pool
client = requests.client
builder = builds.builder
live = figma.live
gold_setup = gold.setup
servers = k6.servers
scaffold = quality.scaffold
corridor = scans.corridor
rig = promotions.rig
configured = publication.configured
api = quotes.api


@pytest_asyncio.fixture
async def database(command_pool):
    # Use CI's existing disposable DB, including its configured local password.
    # The imported API fixture still mounts the real room guard and tenant binder.
    from chassis.tenant_db import TenantPool
    async with command_pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_tisan')
        await conn.execute((ROOT / 'agents/tisan/schema.sql').read_text())
        yield quotes.q.Quotes(TenantPool(command_pool)), conn, command_pool


def ui(scenario):
    env = {**os.environ, 'TISAN_ACCEPTANCE_ROW': scenario}
    result = subprocess.run(['node', 'tests/acceptance/tisan_ui.cjs'], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'{scenario} passed' in result.stdout


def test_t01_shell_search_and_navigation():
    ui('T01')


def test_t02_plugins_off():
    ui('T02')


def test_t03_plugin_key_save_remove():
    ui('T03')


def test_t04_plugin_file_save_remove():
    ui('T04')


def test_t05_plugin_link_save_remove():
    ui('T05')


def test_t06_plugin_connection_save_remove():
    ui('T06')


def test_t07_gold_approval(gold_setup):
    gold.test_approval_creates_both_candidates_and_preserves_truth(gold_setup)
    from test_tisan_gold_actions import test_founder_server_actions
    test_founder_server_actions()


def test_t08_stale_gold_is_refused(gold_setup):
    gold.test_changed_frame_or_page_drops_out_and_stale_review_cannot_approve(gold_setup, 'readings')


def test_t09_nonfounder_cannot_approve(gold_setup):
    gold.test_non_founder_and_wrong_key_cannot_approve(gold_setup)


@pytest.mark.asyncio
async def test_t10_recorded_figma_eval(tmp_path, monkeypatch):
    await figma.test_real_skala_eval_calls_room_endpoint_with_platform_tenant(tmp_path, monkeypatch, '1.0.1', 6)


@pytest.mark.asyncio
async def test_t11_paired_live_figma(live, caplog):
    await figma.test_paired_live_page_uses_two_proxy_requests_and_recorded_tokens(live, caplog)


@pytest.mark.asyncio
async def test_t12_unpaired_live_figma(live, monkeypatch):
    await figma.test_unpaired_file_refused_before_client_or_request(live, figma.TENANT, 'placeholderUnpairedFile01', monkeypatch)


@pytest.mark.asyncio
async def test_t13_variables_denied_stays_unknown(live):
    await figma.test_variables_403_preserves_unknown_collections_and_no_values(live)


@pytest.mark.asyncio
async def test_t14_scaffold_brand_and_private_archive(tmp_path):
    from test_tisan_scaffold import test_two_brands_write_different_tokens_for_their_own_tenants
    await test_two_brands_write_different_tokens_for_their_own_tenants(tmp_path)


@pytest.mark.asyncio
async def test_t15_missing_accepted_copy(builder, tmp_path):
    await builds.test_copy_needed_has_purpose_and_no_work(builder, tmp_path)


@pytest.mark.asyncio
async def test_t16_missing_media(builder, tmp_path):
    await builds.test_media_needed_is_not_invented(builder, tmp_path)


@pytest.mark.asyncio
async def test_t17_confirm_queues_once_and_updates_original_card(client, runtime, monkeypatch, tmp_path):
    await flows.test_actual_confirm_request_queues_one_durable_room_job_and_refreshes_card(client, runtime, monkeypatch, tmp_path)


async def saved_request(client):
    http, _, journal, _ = client
    response = await requests.confirmed(http, 'tisan.request', requests.brief())
    assert response.status_code == 200 and response.json()['status'] == 'requested'
    requests.journal_row(journal, 1)
    return http, journal


@pytest.mark.asyncio
async def test_t18_preview(client):
    http, _ = await saved_request(client)
    response = await http.get('/v1/command/tisan/preview', params={'slug': 'placeholder-site'})
    assert response.status_code == 200
    assert {k: response.json()[k] for k in ('status', 'build_id', 'commit', 'url')} == {
        'status': 'requested', 'build_id': 1, 'commit': requests.SHA, 'url': 'https://placeholder-stage.test/'}


@pytest.mark.asyncio
async def test_t19_feedback_requires_new_build(client):
    http, _ = await saved_request(client)
    response = await requests.confirmed(http, 'tisan.feedback', {'slug': 'placeholder-site', 'text': 'placeholder change request'})
    assert response.status_code == 200 and response.json()['status'] == 'changes_requested'
    refused = await requests.confirmed(http, 'tisan.handover', {'slug': 'placeholder-site'})
    assert refused.status_code == 409 and refused.json()['detail']['status'] == 'new_build_required'


@pytest.mark.asyncio
async def test_t20_handover(client):
    http, journal = await saved_request(client)
    await requests.confirmed(http, 'tisan.feedback', {'slug': 'placeholder-site', 'text': 'placeholder change request'})
    requests.journal_row(journal, 2, sha='b' * 40)
    response = await requests.confirmed(http, 'tisan.handover', {'slug': 'placeholder-site'})
    assert response.status_code == 200
    assert response.json()['status'] == 'accepted' and response.json()['build_id'] == 2
    assert response.json()['commit'] == 'b' * 40


@pytest.mark.asyncio
async def test_t21_pipeline_reaches_staging(tmp_path):
    await flows.test_one_request_runs_to_staging_records_steps_and_never_promotes(tmp_path)


@pytest.mark.asyncio
async def test_t22_unapproved_page_blocks_build(tmp_path):
    await flows.test_unapproved_live_changed_or_revoked_page_never_starts_build(tmp_path, 'missing')


@pytest.mark.asyncio
async def test_t23_critical_repo_blocks_and_is_recorded(tmp_path, corridor):
    await scans.test_build_records_real_r5_corridor_receipt_and_critical_blocks(tmp_path, corridor, 1)


@pytest.mark.asyncio
async def test_t24_quality_secret_check_blocks(scaffold, tmp_path):
    await quality.test_real_secret_scanner_via_approved_tank_contract(scaffold, tmp_path, True)
    from test_tisan_quality_card import test_existing_build_card_shows_quality_results
    test_existing_build_card_shows_quality_results()


def test_t25_real_k6_all_pages(tmp_path, servers):
    assert __import__('shutil').which('k6'), 'Install the pinned room k6 on PATH; acceptance must not skip it'
    k6.test_real_k6_every_page_200_and_p95_with_no_redirects(tmp_path, servers, '/placeholder-clean', True)


@pytest.mark.asyncio
async def test_t26_real_k6_500_fails_build(tmp_path, servers, monkeypatch):
    assert __import__('shutil').which('k6'), 'Install the pinned room k6 on PATH; acceptance must not skip it'
    await k6.test_500_smoke_fails_build_and_saved_manifest(tmp_path, servers, monkeypatch)


@pytest.mark.asyncio
async def test_t27_build_memory(tmp_path, corridor, monkeypatch):
    await scans.test_repo_receipt_is_recorded_in_existing_build_memory(tmp_path, corridor, monkeypatch)


@pytest.mark.asyncio
async def test_t28_publish_only_staging(tmp_path, monkeypatch, configured, caplog):
    await publication.test_publish_commits_every_file_and_workflow_unchanged_then_only_staging(tmp_path, monkeypatch, configured, caplog, False)


@pytest.mark.asyncio
async def test_t29_promote(rig, corridor, tmp_path):
    await production.test_exact_scanned_site_promotes_and_rolls_back_without_docker(rig, corridor, tmp_path)


@pytest.mark.asyncio
async def test_t30_rollback_and_original_card(rig, corridor, tmp_path, monkeypatch):
    await production.test_original_pipeline_tracks_founder_promote_and_rollback_without_dispatching(rig, tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_t31_unknown_deploy_does_not_retry(rig):
    await promotions.test_pending_and_lost_ack_never_repeat_deploy(rig)


@pytest.mark.asyncio
async def test_t32_quote_designed_request(api):
    response = await quotes.create(api)
    assert response.status_code == 201
    row = response.json()
    assert row['state'] == 'submitted' and json.loads(row['contact']) == quotes.designed()['contact']
    assert json.loads(row['items']) == quotes.designed()['items']
    http, _, _, _ = api
    response = await http.get(f"/quotes/{row['id']}?tenant_id={quotes.A}", headers=quotes.HEADERS)
    assert response.status_code == 200 and response.json()['events'][0]['to_state'] == 'draft'


@pytest.mark.asyncio
async def test_t33_quote_validation(api):
    for change in ('phone', 'description', 'control'):
        data = quotes.designed()
        if change == 'phone':
            data['contact'].pop('phone')
        elif change == 'description':
            data['items'][0]['description'] = 'placeholder' * 23
        else:
            data['contact']['name'] = 'placeholder\x00'
        assert (await quotes.create(api, data)).status_code == 422


async def priced_quote(api):
    ref = await quotes.acknowledged(api)
    http, _, _, _ = api
    response = await http.post(f'/quotes/{ref}/state', headers=quotes.HEADERS,
        json={'tenant_id': str(quotes.A), 'state': 'quoted', **quotes.quote_fields()})
    assert response.status_code == 200 and response.json()['state'] == 'quoted'
    return ref


@pytest.mark.asyncio
async def test_t34_quote_snapshot_is_immutable(api):
    ref = await priced_quote(api)
    http, _, _, _ = api
    response = await http.post(f'/quotes/{ref}/state', headers=quotes.HEADERS,
        json={'tenant_id': str(quotes.A), 'state': 'quoted', **quotes.quote_fields(), 'quote_amount': '99.99'})
    assert response.status_code == 409
    row = (await http.get(f'/quotes/{ref}?tenant_id={quotes.A}', headers=quotes.HEADERS)).json()
    assert row['quote_amount'] == '12.34' and row['quote_currency'] == 'USD'


@pytest.mark.asyncio
async def test_t35_customer_accepted_is_final(api):
    ref = await priced_quote(api)
    http, _, _, _ = api
    for target, expected in [('accepted', 200), ('declined', 409)]:
        response = await http.post(f'/quotes/{ref}/state', headers=quotes.HEADERS,
            json={'tenant_id': str(quotes.A), 'state': target})
        assert response.status_code == expected
    row = (await http.get(f'/quotes/{ref}?tenant_id={quotes.A}', headers=quotes.HEADERS)).json()
    assert row['state'] == 'accepted'
    assert [e['to_state'] for e in row['events']] == ['draft', 'submitted', 'acknowledged', 'quoted', 'accepted']
    assert all(datetime.fromisoformat(e['happened_at']).utcoffset() is not None for e in row['events'])


@pytest.mark.asyncio
async def test_t36_customer_declined_is_final(api):
    ref = await priced_quote(api)
    http, _, _, _ = api
    for target, expected in [('declined', 200), ('accepted', 409)]:
        response = await http.post(f'/quotes/{ref}/state', headers=quotes.HEADERS,
            json={'tenant_id': str(quotes.A), 'state': target})
        assert response.status_code == expected
    row = (await http.get(f'/quotes/{ref}?tenant_id={quotes.A}', headers=quotes.HEADERS)).json()
    assert row['state'] == 'declined'


@pytest.mark.asyncio
async def test_t37_no_quote_email(api, tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    assert quotes.q.approved_letter() is None
    response = await quotes.create(api)
    http, _, _, _ = api
    response = await http.post(f"/quotes/{response.json()['id']}/email?tenant_id={quotes.A}", headers=quotes.HEADERS)
    assert response.status_code == 200 and response.json()['mail'] == 'wording_missing'


@pytest.mark.asyncio
async def test_t38_quotes_tenant_and_founder_guards(api):
    response = await quotes.create(api)
    http, _, _, _ = api
    ref = response.json()['id']
    assert (await http.get(f'/quotes/{ref}?tenant_id={quotes.B}', headers=quotes.HEADERS)).status_code == 404
    assert (await http.get(f'/quotes?tenant_id={quotes.B}', headers=quotes.HEADERS)).json() == []
    assert (await http.get(f'/quotes/{ref}?tenant_id={quotes.A}', headers={**quotes.HEADERS, 'X-Tervory-Admin': 'placeholder-member'})).status_code == 404


@pytest.mark.asyncio
async def test_t39_legacy_quotes_remain_unfilled(api):
    await quotes.test_legacy_request_reads_without_fabricating_missing_fields(api, 'submitted')


def test_t40_privacy_cookie_and_visual_gate():
    template = ROOT / 'agents/tisan/templates/next-site'
    result = subprocess.run(['node', 'node_modules/vitest/vitest.mjs', 'run', 'tests/deploy-gate.test.ts', 'tests/visual.test.ts'], cwd=template,
                            capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope='module')
def quality_proof():
    # Actual Chromium, axe, link proxy and Lighthouse; fixed local HTML only.
    template = ROOT / 'agents/tisan/templates/next-site'
    result = subprocess.run(['node', 'tests/quality-browser.cjs', '--lighthouse'], cwd=template,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_t41_accessibility(quality_proof):
    assert quality_proof['clean'] is True
    assert any(row['rule'] == 'image-alt' and row['page'] == '/missing-alt' for row in quality_proof['missingAlt'])


def test_t42_links_never_fetch_external(quality_proof):
    assert quality_proof['externalNeverFetched'] is True
    assert any(row['url'] == '/missing-test-link' and row['status'] == 404 for row in quality_proof['brokenLink'])


def test_t43_lighthouse_budget(quality_proof):
    assert quality_proof['lighthouse']['ok'] is False
    assert any(row['category'] == 'performance' and row['score'] < 0.9 for row in quality_proof['lighthouse']['failures'])


def generated(scenario):
    result = subprocess.run(['node', 'tests/acceptance/tisan_generated.cjs', scenario], cwd=ROOT,
                            capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'{scenario} passed' in result.stdout


def test_t44_contact_is_accept_only():
    generated('T44')


def test_t45_sections_wait_for_approved_frames():
    template = ROOT / 'agents/tisan/templates/next-site'
    result = subprocess.run(['node', 'node_modules/vitest/vitest.mjs', 'run', 'tests/content-route.test.ts'],
                            cwd=template, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr


def test_t46_build_authority_and_body_scope(runtime):
    requests.test_admin_catalogue_and_build_validation(runtime)


def test_t47_invalid_plan_and_media(builder):
    builds.test_refuse_invalid_plan(builder, lambda plan: plan['pages'][0]['sections'][0].update(type='placeholder-invented'))
    for url in ('http://placeholder.invalid/x', 'https://placeholder:placeholder@placeholder.invalid/x',
                '/media/../placeholder-private', 'data:image/png;base64,placeholder', '//placeholder.invalid/x'):
        builds.test_unsafe_media_refused(builder, url)


def test_t48_visual_measurements_match_real_render():
    generated('T48')


# Finish gates reuse the same offline proofs as the product regression suite.
def test_t49_concurrent_build_numbers_preserve_failed_receipts(tmp_path):
    from test_tisan_finish_builds import test_concurrent_builds_reserve_distinct_numbers_and_keep_failed_receipts
    test_concurrent_builds_reserve_distinct_numbers_and_keep_failed_receipts(tmp_path)


@pytest.mark.asyncio
async def test_t50_approved_frame_is_bound_to_pipeline_and_direct_jobs(tmp_path, monkeypatch):
    from test_tisan_finish_builds import test_pipeline_binds_approved_frame_even_when_caller_omits_it, test_direct_room_builds_inherit_the_same_approved_source
    await test_pipeline_binds_approved_frame_even_when_caller_omits_it(tmp_path)
    await test_direct_room_builds_inherit_the_same_approved_source(monkeypatch)


def test_t51_local_quality_gate_detects_recorded_visual_regressions():
    from test_tisan_finish_builds import test_actual_visual_gate_detects_text_and_geometry_regressions
    test_actual_visual_gate_detects_text_and_geometry_regressions()


def test_t52_durable_receipts_survive_failed_and_concurrent_writes(tmp_path, monkeypatch):
    from test_tisan_finish_storage import test_failed_serialization_preserves_existing_receipt_and_cleans_partial, test_readers_never_observe_truncated_receipts_while_updates_commit, test_unwritable_room_volume_never_falls_back_to_temporary_storage
    from agents.tisan import scaffold, figma
    for name, proof in [('atomic',test_failed_serialization_preserves_existing_receipt_and_cleans_partial),
                        ('concurrent',test_readers_never_observe_truncated_receipts_while_updates_commit)]:
        folder = tmp_path/name
        folder.mkdir()
        proof(folder)
    for module in (scaffold,figma):
        with monkeypatch.context() as isolated:
            test_unwritable_room_volume_never_falls_back_to_temporary_storage(module,tmp_path/module.__name__,isolated)


def test_t53_existing_tenant_aliases_cannot_read_or_overwrite_foreign_artifacts(tmp_path):
    from test_tisan_finish_storage import test_existing_review_artifact_aliases_are_rejected_on_read, test_publish_cannot_read_a_different_tenants_build_directory
    for category in ('builds','readings','reviews'):
        test_existing_review_artifact_aliases_are_rejected_on_read(category,tmp_path)
    test_publish_cannot_read_a_different_tenants_build_directory(tmp_path)


@pytest.mark.asyncio
async def test_t54_archive_is_private_verified_and_idempotent(tmp_path, monkeypatch):
    from test_tisan_finish_sources import test_private_archive_roundtrip_and_retry_use_signed_immutable_keys
    await test_private_archive_roundtrip_and_retry_use_signed_immutable_keys(tmp_path,monkeypatch)


@pytest.mark.asyncio
async def test_t55_saturday_heartbeat_queue_and_private_receipt(command_pool):
    from test_tisan_finish_sources import test_saturday_heartbeat_enqueues_once_per_slot_and_writes_private_receipt
    await test_saturday_heartbeat_enqueues_once_per_slot_and_writes_private_receipt(command_pool)


def test_t56_production_mode_build_tools_are_installed_offline(tmp_path, monkeypatch):
    from test_tisan_finish_sources import test_production_environment_installs_the_locked_dev_toolchain_offline
    test_production_environment_installs_the_locked_dev_toolchain_offline(tmp_path,monkeypatch)
