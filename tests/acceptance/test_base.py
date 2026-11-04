"""One offline fixture case per shipped Base acceptance row.

Matches Tisan's reuse of existing real-path fixture harnesses. External services
are ASGI/MockTransport/recorded pages; durable fixtures require loopback Postgres.
"""
import os
import asyncio
import json
from pathlib import Path
import re
import signal
import subprocess

import pytest
import test_base_workflow as workflow
import test_base_product as product
import test_base_products as products
import test_base_database as db
import test_base_atf_download as atf
import test_base_reference_file as files
import test_base_lists as lists
import test_base_list_products as lp
import test_base_list_costs as costs
import test_base_contact_quality as contact
import test_base_wave4 as wave
import test_base_readiness as readiness
import test_base_site_signals as signals
import test_base_audit as audit
import test_base_audit_commands as audit_commands
import test_base_source_reliability as reliability
import test_base_context_dev as context
import test_base_trial_launch as trial
import test_base_gold_sources as gold
import test_base_gold_nightly as nightly
import test_base_public_http as public
import test_base_product_origin as origin
import test_base_proxy_boundary as proxy
import test_base_scrape_limits as limits
import test_case_study_reports as reports
import test_case_study_apollo_scoreboard as scoreboard

ROOT = Path(__file__).resolve().parents[2]
database = db.database
audit_db = audit.audit_db
corridor = audit_commands.corridor
local_file = files.local_file
report_api = reports.api


def ui(ident):
    env = {**os.environ, 'BASE_ACCEPTANCE_ROW': ident}
    with subprocess.Popen(['node', 'tests/acceptance/base_ui.cjs'], cwd=ROOT,
            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True) as run:
        try:
            stdout, stderr = run.communicate(timeout=240)
        except subprocess.TimeoutExpired:
            # Playwright handles SIGTERM by closing its browser. SIGKILL from
            # subprocess.run's timeout cannot run that cleanup.
            run.terminate()
            try:
                run.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(run.pid, signal.SIGKILL)
                run.communicate()
            raise
    assert run.returncode == 0, stdout + stderr
    assert ident + ' passed' in stdout


def test_b01_upload_status_and_batch_download():
    workflow.test_base_upload_status_download_and_two_tenants()


@pytest.mark.asyncio
async def test_b02_search_cards(monkeypatch):
    await products.test_search_card_reuses_summary_for_products_and_preserves_older_records(monkeypatch)

def test_b03_official_reference_changes():
    product.test_atf_fixture_refresh_keeps_collectors_and_tracks_identity_across_move()


@pytest.mark.asyncio
async def test_b04_reference_adoption(database):
    await db.test_existing_platform_adoption_refresh_batch_pairs_and_isolation(database)


@pytest.mark.asyncio
async def test_b05_blocked_official_source(database, monkeypatch):
    await atf.test_atf_block_is_visible_and_durable_without_further_reads(database, monkeypatch, 'listing', 403, b'')


@pytest.mark.asyncio
async def test_b06_configured_official_file(database, monkeypatch, local_file):
    await files.test_new_file_source_installs_after_legacy_atf_block_and_retains_stop(database, monkeypatch, local_file)


@pytest.mark.asyncio
async def test_b07_verified_find_filters(monkeypatch):
    for args in ({'state':'dc'}, {'city':'washington'}, {'licence_type':'01'}, {'engine_category':'dealer'}, {'has_website':True}, {'has_phone':True}, {'has_email':True}, {'email_syntax_ok':True}, {'email_disposable':False}, {'phone_valid':True}, {'technologies_contain':'shopify'}, {'sells_online':True}, {'site_newest_year_at_least':2026}, {'confidence_tier':'ready'}):
        lists.test_every_filter_accepts_verified_values(args)
    for args in ({'state':'CA'}, {'has_website':False}, {'has_phone':False}, {'has_email':False}, {'technologies_contain':'other'}):
        lists.test_every_filter_rejects_nonmatching_values(args)
    await lists.test_find_get_returns_count_first_twenty_and_free_receipt(monkeypatch)

def test_b08_original_evidence_dates():
    lists.test_date_uses_original_checks_not_new_record_timestamp()
    lists.test_unverified_or_missing_date_cannot_satisfy_filter('website', {'has_website':True})


@pytest.mark.asyncio
async def test_b09_save_fixed_list():
    await lists.test_saved_list_is_fixed_tenant_snapshot_and_csv_identical()


@pytest.mark.asyncio
async def test_b10_list_catalogue_and_show(monkeypatch, database):
    import sys
    from types import SimpleNamespace
    from uuid import UUID
    import command
    import httpx
    from fastapi import FastAPI
    conn, runtime = database
    async def scan(self, conn, tenant, filters, ids=None):
        assert tenant == lists.TENANT
        yield lists.record()
    monkeypatch.setattr(lists.lists.Store, 'scan', scan)
    pool = runtime.pool()
    pool.fetchval = conn.fetchval
    saved = await lists.lists.Store(pool).save(lists.TENANT, 'Founder acceptance', lists.lists.FindArgs(state='DC'))
    monkeypatch.setattr(command, 'db', lambda: pool)
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    app = FastAPI()
    app.include_router(lists.lists.build_router())
    actor = command.Actor(lists.TENANT, 'placeholder-founder', False, frozenset({'base'}))
    app.dependency_overrides[command.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        catalogue = await client.get('/v1/command/base/lists')
        assert catalogue.status_code == 200
        assert catalogue.json()['items'][0]['name'] == 'Founder acceptance'
        assert catalogue.json()['items'][0]['list_id'] == str(saved['list_id'])
        result = await client.get('/v1/command/base/lists/show', params={'list_id':str(saved['list_id'])})
        assert result.status_code == 200 and result.json()['total'] == 1
        assert result.json()['records'][0]['record_id'] == str(lists.RECORD)
        for response in (catalogue, result):
            cost = await conn.fetchval('SELECT cost_usd FROM tank.ledger WHERE tenant_id=$1 AND id=$2',
                lists.TENANT, UUID(response.json()['ledger_id']))
            assert cost == 0
        actor = command.Actor(lists.OTHER, 'placeholder-founder', False, frozenset({'base'}))
        other = await client.get('/v1/command/base/lists')
        assert other.json()['items'] == []
        assert (await client.get('/v1/command/base/lists/show', params={'list_id':str(saved['list_id'])})).status_code == 404
    assert (await lists.lists.Store(pool).show(lists.TENANT, saved['list_id']))['filters']['state'] == 'DC'


def test_b11_list_csv_and_existing_cards():
    lists.test_workspace_download_preserves_bytes_and_existing_batch_behavior()


@pytest.mark.asyncio
async def test_b12_products_from_existing_pages():
    await products.test_preserved_cases_fixtures_and_candidate_evals()
    await products.test_microdata_offer_and_each_pages_own_provenance()

def test_b13_product_list_filter_and_compact_previews():
    lp.test_projection_retains_individual_sources_and_drops_unsourced_products()
    for present in (True, False):
        lp.test_has_products_filters_missing_and_verified_products(present)
    lp.test_preview_omits_products_without_changing_the_saved_snapshot()
    lp.test_product_cutoff_uses_oldest_observation_in_either_order(False)
    lp.test_products_alone_cannot_create_a_confidence_tier()


@pytest.mark.asyncio
async def test_b14_products_download(monkeypatch):
    await lp.test_product_download_tenant_scope_columns_and_real_zero_dollar_receipt(monkeypatch)
    lp.test_products_workspace_download_and_existing_card_labels()

def test_b15_spreadsheet_safety():
    for prefix in ('+', '-', '@', '\t'):
        for column in ('sku', 'brand', 'url'):
            lp.test_products_csv_neutralizes_formula_prefixes(prefix, column)
    product.test_every_extra_csv_column_retains_formula_protection()
    lp.test_product_url_normalization_applies_to_projection_and_saved_csv(
        'https://placeholder.example/item?placeholder=query#fragment', 'https://placeholder.example/item')
    lp.test_product_url_normalization_applies_to_projection_and_saved_csv('javascript:placeholder', None)


@pytest.mark.asyncio
async def test_b16_priced_list_receipt(monkeypatch):
    await costs.test_show_export_and_csv_share_ledger_totals_and_tenant_scope(monkeypatch, False)


@pytest.mark.asyncio
async def test_b17_unknown_list_cost(monkeypatch):
    await costs.test_show_export_and_csv_share_ledger_totals_and_tenant_scope(monkeypatch, 'missing')

def test_b18_shared_cost_and_fixed_decimals():
    costs.test_shared_ledger_rows_leave_both_cost_cells_blank_without_allocating_cost()
    costs.test_csv_costs_always_use_fixed_point_and_preserve_known_zeroes()


@pytest.mark.asyncio
async def test_b19_confirmed_crm_handoff(monkeypatch):
    await lists.test_base_corridor_authority_requires_own_confirmed_card(monkeypatch)
    await lists.test_duplicates_by_email_or_website_and_within_card_are_skipped(monkeypatch)


@pytest.mark.asyncio
async def test_b20_crm_unavailable(monkeypatch):
    await lists.test_no_binding_sends_nothing_and_returns_each_record(monkeypatch)


@pytest.mark.asyncio
async def test_b21_email_and_contact_quality(monkeypatch):
    await contact.test_pipeline_passes_site_and_raw_phones_country_and_provenance()
    await contact.test_product_records_csv_and_apollo_snapshot_retain_quality(monkeypatch)
    await contact.test_reserved_mx_never_requests_and_discovery_agrees("example.invalid")


@pytest.mark.asyncio
async def test_b22_phone_metadata_candidate_and_approval():
    await wave.test_contacts_candidate_evals_offline()
    wave.test_phone_metadata_preserves_evidence('+12025550123', 'US', True, 'fixed-or-mobile', 'US')
    wave.test_phone_metadata_preserves_evidence('123', 'US', False, 'unknown', None)

def test_b23_own_site_social_presence():
    readiness.test_social_links_from_html_keep_each_page_and_date_in_records_and_csv()


@pytest.mark.asyncio
async def test_b24_mit_technology_detection():
    await signals.test_fingerprints_and_booking_quote_actions_have_evidence()
    await signals.test_approved_pass_runs_after_scrape_and_reaches_verify_and_export()
    await signals.test_unapproved_optional_pass_leaves_pipeline_exactly_unchanged()


@pytest.mark.asyncio
async def test_b25_online_sales_and_newest_year():
    await signals.test_shopify_action_and_conflicting_sales_statement()
    await signals.test_newest_dates_ignore_future_and_non_article_dates()
    await signals.test_false_sales_verifies_but_archived_or_undated_signals_do_not()


@pytest.mark.asyncio
async def test_b26_dc_small_campaign(audit_db, monkeypatch):
    await readiness.test_dc_campaign_through_confirmed_cards_collection_audit_and_download(audit_db, monkeypatch, 3)


@pytest.mark.asyncio
async def test_b27_campaign_through_reviewed_audit_report(audit_db, monkeypatch):
    await readiness.test_dc_campaign_through_confirmed_cards_collection_audit_and_download(audit_db, monkeypatch, 200)


@pytest.mark.asyncio
async def test_b28_audit_command_confirmation_and_owned_upload(corridor):
    await audit_commands.test_start_requires_confirm_and_returns_store_result(corridor)
    await audit_commands.test_review_binding_attachment_owner_and_unchanged_csv(corridor)
    audit_commands.test_workspace_audit_download_preserves_bytes_and_status()


@pytest.mark.asyncio
async def test_b29_audit_reproducibility_and_unsure(audit_db):
    await audit.test_seeded_sample_saved_sources_round_trip_and_accuracy(audit_db)
    audit.test_no_resolved_verdicts_is_not_zero_accuracy()


@pytest.mark.asyncio
async def test_b30_audit_immutable_evidence(audit_db):
    await audit.test_checked_csv_rejects_damage_atomically_and_preserves_formula_escaping(audit_db)


@pytest.mark.asyncio
async def test_b31_source_reliability(audit_db):
    await audit.test_review_recomputes_platform_scores_and_route_is_guarded(audit_db)
    reliability.test_known_counts_all_sources_and_no_identifying_output()


@pytest.mark.asyncio
async def test_b32_confidence_histogram(audit_db):
    await audit.test_histogram_boundaries_campaign_scope_missing_scores_and_unverified(audit_db)


@pytest.mark.asyncio
async def test_b33_apollo_comparison(monkeypatch):
    wave.test_apollo_counts_field_agreement_and_unmatched_rows()
    await wave.test_apollo_read_owned_upload_saved_list_and_zero_receipt(monkeypatch)
    wave.test_apollo_card_labels_and_read_adapter(monkeypatch)

def test_b34_apollo_ambiguity_and_invalid_csv():
    wave.test_apollo_ambiguous_domains_and_unverified_evidence_do_not_match()
    for text in ('', 'a,a\n1,2', 'a,b\n1', 'a\n1,2'):
        wave.test_invalid_apollo_csv(text)

def test_b35_ffl_package_and_new_vertical_template(tmp_path):
    wave.test_ffl_manifest_preserves_every_existing_asset_byte_for_byte()
    wave.test_new_vertical_scaffold_is_empty_and_never_overwrites(tmp_path)

def test_b36_context_comparison_budget(monkeypatch):
    context.test_only_identity_is_sent()
    context.test_budget_and_ledger(monkeypatch)
    context.test_no_ledger_means_no_network(monkeypatch)


@pytest.mark.asyncio
async def test_b37_founder_trial_boundary(monkeypatch):
    await trial.test_founder_proxy_replaces_credentials_and_ignores_input(monkeypatch)
    await trial.test_latest_completed_platform_selection_is_bounded(monkeypatch)


@pytest.mark.asyncio
async def test_b38_public_source_review_candidates(monkeypatch, tmp_path):
    gold.test_four_public_candidates_and_deduplication()
    await asyncio.to_thread(gold.test_http_requires_exact_room_key_before_read, monkeypatch)
    await nightly.test_code_builds_file_and_public_list_only_labels(monkeypatch, tmp_path)


@pytest.mark.asyncio
async def test_b39_public_site_block_and_identity():
    await public.test_one_truthful_identity_and_public_cookies_never_forwarded()
    await public.test_block_stops_get_browser_and_future_calls_for_same_tenant(403, '')

def test_b40_workspace_tenant_and_origin_boundary():
    origin.test_base_product_proxy_origin_and_tenant_boundary()
    proxy.test_base_proxy_boundary()

def test_b41_plugins_off():
    ui('B41')

def test_b42_plugin_key():
    ui('B42')

def test_b43_plugin_file():
    ui('B43')

def test_b44_plugin_source_link():
    ui('B44')

def test_b45_plugin_mcp():
    ui('B45')


def test_b46_search_records():
    ui('B46')


def test_b47_ask_base():
    ui('B47')


@pytest.mark.asyncio
async def test_b48_sequential_reference_campaign(database):
    await db.test_fifty_states_are_submitted_one_after_another(database)


@pytest.mark.asyncio
async def test_b49_saved_apollo_comparison(monkeypatch):
    await product.test_apollo_import_retains_the_base_snapshot(monkeypatch)


@pytest.mark.asyncio
async def test_b50_recorded_costs_and_receipt_history(database, monkeypatch):
    await db.test_status_prices_precise_receipts_founder_only_and_history(database, monkeypatch)


@pytest.mark.asyncio
async def test_b51_base_case_study_evidence(report_api):
    await reports.test_base_verified_confidence_and_apollo_use_real_evidence(report_api)
    await scoreboard.test_scoreboard_is_tenant_scoped_and_reuses_saved_snapshots()


@pytest.mark.asyncio
async def test_b52_report_access_and_empty_figures(report_api):
    reports.test_fixed_template_has_every_figure_and_period_zeros('base')
    await reports.test_tenant_and_founder_access_cannot_be_overridden_by_query_or_headers(report_api)


@pytest.mark.asyncio
async def test_b53_report_audit_measurement(report_api, monkeypatch):
    await reports.test_optional_audit_uses_upstream_measurement_and_only_this_tenants_verdicts(report_api, monkeypatch)


@pytest.mark.asyncio
async def test_b54_business_data_estimates():
    from skala import score_case
    relative = 'tank/skills/base.business_data/2.0.1'
    module = contact.load(relative + '/run.py')
    cases = [json.loads(line) for line in (ROOT / relative / 'evals/cases.jsonl').read_text().splitlines()]
    for case in cases:
        result = await module.run(case['input'], None)
        ok, reason = score_case(case['expected'], result, case.get('tolerance', 'exact'))
        assert ok, (case['name'], reason)
        assert result['confidence'] <= 60
    thin = await module.run({'name': 'Founder Store', 'description': '', 'categories': [], 'services': []}, None)
    assert thin['size_band'] is None and thin['confidence'] == 0


@pytest.mark.timeout(60)
def test_b55_large_pages_do_not_stall_or_lose_evidence():
    for case in limits.CASES:
        limits.test_large_page_keeps_own_contacts_and_later_page(case)
    limits.test_candidate_preserves_existing_evals_and_approved_package()


def test_sheet_has_exactly_one_fixture_case_per_row():
    sheet = (ROOT / 'docs/acceptance/base.md').read_text()
    rows = re.findall(r'^\| (B\d\d) \|', sheet, flags=re.M)
    cases = [name[5:8].upper() for name, value in globals().items()
             if re.match(r'^test_b\d\d_', name) and callable(value)]
    assert len(rows) == len(set(rows)) == 55
    assert rows == cases

    register = (ROOT / 'docs/ops/FOUNDER-SETTINGS.md').read_text()
    for line in sheet.splitlines():
        if re.match(r'^\| B\d\d \|', line):
            settings = line.split('|')[-2].strip()
            assert settings == 'none' or all(name.strip() in register for name in settings.split(','))
    # Validate the exact command JSON in the sheet against today's real adapters.
    # IDs/identity placeholders stand for actual prior results, never literal input.
    import command
    from uuid import uuid4
    actor = command.Actor(uuid4(), 'placeholder-founder', True, frozenset({'base'}))
    substitutions = {'<LIST>': str(uuid4()), '<UPLOAD>': str(uuid4()),
        '<CAMPAIGN>': str(uuid4()), '<AUDIT>': str(uuid4()),
        '<OWN_RECORD_ID>': str(uuid4()), '<BUSINESS_NAME>': 'Founder Store',
        '<OWN_PUBLIC_WEBSITE>': 'https://placeholder.invalid/'}
    for match in re.finditer(r'Run (base\.[a-z_.]+) with (\{)', sheet):
        tail = sheet[match.start(2):]
        for key, value in substitutions.items():
            tail = tail.replace(key, value)
        args, _ = json.JSONDecoder().raw_decode(tail)
        command.validate_action(command.PlannedAction(tool=match[1], arguments=args), actor)
