"""One executable offline scenario per Trigger founder row; real product boundaries.

Reuse the shipped fixture harnesses, real SQL, ASGI and MockTransport. All model,
provider and email boundaries are substitutes; browsers can reach only loopback.
"""
import ast
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
for folder in ('trigger_first_build', 'trigger_second_build', 'trigger_gate2', 'trigger_m1',
               'trigger_m2', 'trigger_bot_b1', 'trigger_bot_b3', 'trigger_w4'):
    sys.path.insert(0, str(ROOT / 'tests' / folder))

import test_trigger as writing
import test_second as voice
import test_gate2 as gate
import test_trigger_w1 as learning
import test_trigger_crm as crm
import test_marketing as marketing
import test_m1_storage as storage
import test_m1_queue as queue
import test_m1_metrics as metrics
import test_m1_oauth_review as oauth
import test_meta as facebook
import test_engine as engine
import test_database as sources
import test_b1_review as bot_review
import test_retention as retention
import test_whatsapp as whatsapp
import test_console_widget as console
import test_wave4_workspace as workspace

# Import fixtures explicitly, as in test_tisan.py: their dependency graph is real.
env = voice.env
m1 = marketing.m1
m2 = facebook.m2
b3 = whatsapp.b3
database = sources.database
w4 = console.w4
crm_setup = crm.setup

ROWS = tuple(f'R{i:02}' for i in range(1, 57))


@pytest.fixture(autouse=True)
def required_disposable_database():
    assert os.environ.get('POOL_SCHEMA_DATABASE_URL'), 'Trigger acceptance requires disposable local Postgres; never production'


def browser(relative):
    """Execute the existing real React/browser harness, with artifacts in TMPDIR."""
    script = r'''
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const filename=process.argv[1],out=process.env.TRIGGER_EVIDENCE_DIR;
fs.mkdirSync(out,{recursive:true});
let source=fs.readFileSync(filename,'utf8');
source=source.replaceAll("executablePath:'/usr/bin/chromium'",'executablePath:process.env.READ1_CHROMIUM_EXECUTABLE || undefined');
source=source.replaceAll('executablePath: "/usr/bin/google-chrome"','executablePath:process.env.READ1_CHROMIUM_EXECUTABLE || undefined');
source=source.replace('const evidence = path.join(__dirname, "evidence");','const evidence = process.env.TRIGGER_EVIDENCE_DIR;');
source=source.replaceAll("path:path.join(__dirname,",'path:path.join(process.env.TRIGGER_EVIDENCE_DIR,');
const m=new Module(filename);m.filename=filename;m.paths=Module._nodeModulePaths(path.dirname(filename));m._compile(source,filename);
'''
    output = Path(os.environ.get('TMPDIR', ROOT / '.tmp')) / 'trigger-acceptance' / Path(relative).parent.name
    tools = os.environ.get('TRIGGER_BROWSER_TOOLS', str(ROOT / 'agents/tisan/templates/next-site/node_modules'))
    result = subprocess.run(['node', '-e', script, str(ROOT / relative)], cwd=ROOT,
        env={**os.environ, 'TRIGGER_BROWSER_TOOLS': tools, 'TRIGGER_EVIDENCE_DIR': str(output)},
        capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS' in result.stdout


def test_r01_responsive_pages_and_widget():
    workspace.test_server_actions_and_public_transport()
    workspace.test_tank_paths_reject_ssrf_inputs_before_any_fetch()
    browser('tests/trigger_w4/browser.cjs')


@pytest.mark.asyncio
async def test_r02_free_check_and_receipt(monkeypatch):
    await writing.test_check_calls_only_internal_checker_and_preserves_text()
    await writing.test_adapter_http_tenant_ownership_and_zero_receipt(monkeypatch)


@pytest.mark.asyncio
async def test_r03_confirmed_writing_with_voice(env):
    await gate.test_verified_admin_write_check_feedback_stay_in_own_tenant(env)


@pytest.mark.asyncio
async def test_r04_long_document(env):
    await gate.test_long_attached_document_checked_once_with_whole_text_offsets(env)


@pytest.mark.asyncio
async def test_r05_legal_handoff(monkeypatch):
    await writing.test_zenas_handoff_keeps_result_notice_and_scope(monkeypatch)


@pytest.mark.asyncio
async def test_r06_voice_preview_confirm_history_rollback(env):
    await voice.test_preview_confirm_history_rollback_and_repeat(env)


@pytest.mark.asyncio
async def test_r07_voice_cancel_stale_and_tenant_guard(env):
    await voice.test_cancel_and_stale_preview_never_overwrite(env)


@pytest.mark.asyncio
async def test_r08_feedback_and_private_learning(env):
    await voice.test_house_write_records_private_pending_pair_then_feedback(env)


@pytest.mark.asyncio
async def test_r09_accepted_copy_for_tisan(env, monkeypatch, tmp_path):
    await gate.test_accepted_copy_resolves_tenant_reference_and_escapes_generated_body(env, monkeypatch, tmp_path)


def test_r10_responsive_writing_and_voice_cards():
    browser('tests/trigger_first_build/browser.cjs')
    browser('tests/trigger_second_build/browser.cjs')


@pytest.mark.asyncio
async def test_r11_client_leads(crm_setup, monkeypatch):
    await crm.test_admin_read_uses_only_actor_binding_and_receipts(crm_setup, monkeypatch, 'leads')
    crm_setup.dependency_overrides[crm.command.identity] = lambda: crm.FOUNDER
    await crm.test_pinned_lead_pagination_and_detail(crm_setup, monkeypatch)


@pytest.mark.asyncio
async def test_r12_client_contacts(crm_setup, monkeypatch):
    await crm.test_admin_read_uses_only_actor_binding_and_receipts(crm_setup, monkeypatch, 'contacts')
    crm_setup.dependency_overrides[crm.command.identity] = lambda: crm.FOUNDER
    await crm.test_read_projection_and_explicit_auth(crm_setup, monkeypatch)


@pytest.mark.asyncio
async def test_r13_client_estimates(crm_setup, monkeypatch):
    await crm.test_admin_read_uses_only_actor_binding_and_receipts(crm_setup, monkeypatch, 'estimates')


@pytest.mark.asyncio
async def test_r14_client_invoices(crm_setup, monkeypatch):
    await crm.test_admin_read_uses_only_actor_binding_and_receipts(crm_setup, monkeypatch, 'invoices')
    crm_setup.dependency_overrides[crm.command.identity] = lambda: crm.FOUNDER
    await crm.test_invoice_read_uses_native_records_and_excludes_public_tokens(crm_setup, monkeypatch)


@pytest.mark.asyncio
async def test_r15_crm_confirmed_write(crm_setup, monkeypatch):
    await crm.test_admin_write_confirm_and_tenant_mismatch(crm_setup, monkeypatch)


@pytest.mark.asyncio
async def test_r16_crm_organisation_attestation(crm_setup, monkeypatch):
    await crm.test_wrong_or_missing_authenticated_org_never_leaks_or_writes(crm_setup, monkeypatch, str(crm.OTHER))


@pytest.mark.asyncio
async def test_r17_gbp_oauth_location(m1, monkeypatch, caplog):
    async def pages(tenant, url, field, **kwargs):
        assert tenant == voice.TENANT
        return [{'name': 'accounts/123'}] if field == 'accounts' else [{'name': 'locations/456', 'title': 'placeholder profile'}]
    m1.google.pages = AsyncMock(side_effect=pages)
    choices = await marketing.api.execute('gbp.locations', None, m1.actor, uuid4())
    assert choices['locations'] == [{'location': marketing.LOCATION, 'title': 'placeholder profile'}]
    _, card = await gate.card_for(m1.env, 'trigger.gbp.location.select',
        {'location': marketing.LOCATION}, user='founder')
    result = await voice.confirm(m1.env, card, user='founder')
    assert result['status'] == 'confirmed' and result['result']['location'] == marketing.LOCATION
    await marketing.test_oauth_state_user_tenant_pkce_refresh_only_and_disconnect(m1, monkeypatch, caplog)


@pytest.mark.asyncio
async def test_r18_meta_oauth_and_pages(m2, caplog):
    await facebook.test_state_single_use_user_tenant_bound_and_real_vault_is_scoped(m2, caplog)


@pytest.mark.asyncio
async def test_r19_meta_page_selection(m2, caplog):
    await facebook.test_page_selection_is_owned_generation_bound_and_never_returns_credentials(m2, caplog)


@pytest.mark.asyncio
async def test_r20_gbp_disconnect(m1, monkeypatch):
    await oauth.test_disconnect_erases_only_successful_or_already_revoked_token(m1, monkeypatch, 200, {}, True)


@pytest.mark.asyncio
async def test_r21_meta_disconnect(m2):
    await facebook.test_disconnect_revokes_then_clears_and_retains_token_on_refusal(m2, False)


@pytest.mark.asyncio
async def test_r22_post_confirmed_draft_approve_schedule(m1):
    await storage.test_actual_confirmed_w1_create_approve_and_schedule_cards(m1)


@pytest.mark.asyncio
async def test_r23_post_edit_invalidates_approval(m1):
    await marketing.test_gbp_none_limit_schedules_only_once_approved_and_edit_returns_draft(m1)


@pytest.mark.asyncio
async def test_r24_gbp_due_publish_once(m1):
    await marketing.test_two_publishers_and_restart_never_double_post_and_record_zero_receipt(m1)


@pytest.mark.asyncio
async def test_r25_facebook_due_publish_once(m2):
    await facebook.test_due_facebook_publishes_once_keeps_id_link_and_code_receipt(m2)


@pytest.mark.asyncio
async def test_r26_uncertain_delivery_reconciles(m2):
    await facebook.test_possibly_sent_or_crashed_send_never_automatically_repeats(m2, 'crash')


@pytest.mark.asyncio
async def test_r27_meta_terminal_refusal(m2, caplog):
    await facebook.test_meta_refusal_fails_once_with_sanitised_message(m2, caplog)


@pytest.mark.asyncio
async def test_r28_meta_bounded_backoff(m2):
    await facebook.test_known_transient_meta_refusals_backoff_at_most_three_attempts(m2, 429)


@pytest.mark.asyncio
async def test_r29_other_channels_scheduled_only(m2):
    await facebook.test_other_channels_and_disconnected_page_never_claimed(m2)


def test_r30_calendar_explicit_zone_and_dst():
    console.test_calendar_rejects_ambiguous_and_nonexistent_wall_time_without_guessing()


@pytest.mark.asyncio
async def test_r31_cancel_and_counts(m1):
    await queue.test_known_failure_allows_explicit_retry_and_uncertain_state_can_be_cancelled(m1)
    m1.google.request.side_effect = None
    await metrics.test_published_count_uses_existing_figure_and_receipt_bounds(m1)


@pytest.mark.asyncio
async def test_r32_gbp_reviews_reply(m1):
    await storage.test_review_cursor_draft_labels_customer_text_and_reuses_w1(m1)
    reply = await m1.env.pool.fetchrow('SELECT id,revision FROM tank.trigger_gbp_replies WHERE tenant_id=$1', voice.TENANT)
    for _ in range(2):
        _, card = await gate.card_for(m1.env, 'trigger.gbp.reply.send',
            {'reply_id': str(reply['id']), 'expected_revision': reply['revision']}, user='founder')
        result = await voice.confirm(m1.env, card, user='founder')
        assert result['status'] == 'confirmed' and result['result']['state'] == 'sent'
    m1.google.request.assert_awaited_once()
    assert m1.google.request.await_args.args[1] == 'PUT'


@pytest.mark.asyncio
async def test_r33_owned_document_source(database, monkeypatch):
    await sources.test_document_preview_binds_actual_owned_attachment_not_model_text(database, monkeypatch)


@pytest.mark.asyncio
async def test_r34_source_removal_and_tenant_isolation(database):
    await sources.test_hybrid_index_rechecks_tenant_staleness_and_source_removal(database)


@pytest.mark.asyncio
async def test_r35_approved_faq_code_receipt():
    await engine.test_approved_faq_has_zero_model_calls_and_code_receipt()


@pytest.mark.asyncio
async def test_r36_widget_sourced_answer(w4, monkeypatch):
    await console.test_widget_projects_grounded_answer_without_internal_metadata(w4, monkeypatch)


@pytest.mark.asyncio
async def test_r37_widget_handover_outside_hours(w4):
    await console.test_outside_hours_hands_over_and_never_routes_a_model(w4)


@pytest.mark.asyncio
async def test_r38_settings_confirm_snapshot_and_replay(w4):
    await console.test_settings_propose_is_not_write_and_confirm_snapshot_is_tenant_bound(w4)
    await console.test_settings_confirm_replay_writes_once_and_other_user_cannot_confirm(w4)


@pytest.mark.asyncio
async def test_r39_widget_privacy_notice(w4):
    await console.test_public_config_does_not_leak_private_settings_or_other_tenant(w4)
    await console.test_notice_checked_before_contact_write_and_names_preserved(w4)


@pytest.mark.asyncio
async def test_r40_lead_capture(w4):
    await console.test_notice_checked_before_contact_write_and_names_preserved(w4)


@pytest.mark.asyncio
async def test_r41_quote_capture(w4):
    await console.test_quote_title_quantity_request_are_captured_without_model_or_live_send(w4)


@pytest.mark.asyncio
async def test_r42_human_inbox_reply(w4):
    await console.test_human_reply_poll_requires_exact_conversation_and_visitor(w4)


@pytest.mark.asyncio
async def test_r43_website_embed_origin_and_revocation(database, monkeypatch):
    await bot_review.test_keys_rotate_origin_normalizes_and_remove_revokes(database, monkeypatch)
    await engine.test_robots_disallow_same_site_only_and_per_page_limit()


@pytest.mark.asyncio
async def test_r44_whatsapp_verification(b3, monkeypatch):
    await whatsapp.test_signature_before_parsing_challenge_unknown_and_caps(b3, monkeypatch)


@pytest.mark.asyncio
async def test_r45_whatsapp_faq_dedupe_stats(b3, caplog):
    await whatsapp.test_faq_zero_cost_private_identity_dedupe_and_stats(b3, caplog)


@pytest.mark.asyncio
async def test_r46_whatsapp_cap_and_local_month(b3, monkeypatch):
    await whatsapp.test_999_1000_then_handover_and_concurrent_boundary(b3)
    b3.bot.retrieve.side_effect = None
    b3.cloud.calls.clear()
    b3.mail.send.reset_mock()
    await whatsapp.test_timezone_local_month_boundaries_and_not_utc(b3, monkeypatch)


@pytest.mark.asyncio
async def test_r47_whatsapp_fail_closed(b3, monkeypatch):
    with monkeypatch.context() as scoped:
        await whatsapp.test_missing_invalid_timezone_window_and_token_handover_no_generation(b3, scoped)
    await whatsapp.test_failed_send_and_crash_never_refund_or_replay(b3)


@pytest.mark.asyncio
async def test_r48_retention(database, monkeypatch):
    fresh = await retention.conversation(database, sources.A, 1)
    await retention.test_confirmed_lead_and_quote_survive_unconfirmed_drafts_are_deleted(database, monkeypatch)
    assert await database.fetchval('SELECT 1 FROM tank.trigger_bot_conversations WHERE tenant_id=$1 AND id=$2', sources.A, fresh) == 1


def test_r49_format_lengths():
    learning.test_formats_and_exact_counts_preserve_truncation()
    learning.test_instagram_caption_official_character_limit()


@pytest.mark.asyncio
async def test_r50_accepted_examples(env):
    await learning.test_learning_accepted_own_tenant_format_only_and_rank(env)


@pytest.mark.asyncio
async def test_r51_revise(env):
    await learning.test_revise_confirm_parent_and_original_snapshot(env)


@pytest.mark.asyncio
async def test_r52_voice_from_changes(env):
    await learning.test_voice_learn_preview_cancel_confirm_and_literal_rules(env)


@pytest.mark.asyncio
async def test_r53_catalogue_batch(env, monkeypatch):
    await learning.test_batch_25_receipts_feedback_and_case_study_provenance(env, monkeypatch)


@pytest.mark.asyncio
async def test_r54_scorecard(env):
    learning.test_scorecard_period_boundaries_and_rates()
    await learning.test_scorecard_get_zero_receipt_and_tenant_permissions(env)


@pytest.mark.asyncio
async def test_r55_bot_feedback_review_stats(w4):
    from trigger_bot_contract import Feedback
    from trigger_bot_api import execute
    conversation, message = uuid4(), uuid4()
    await w4.pool.execute('INSERT INTO tank.trigger_bot_conversations(tenant_id,id,visitor_id) VALUES($1,$2,$3)', console.A, conversation, uuid4())
    await w4.pool.execute('''INSERT INTO tank.trigger_bot_messages(tenant_id,id,conversation_id,question,outcome)
        VALUES($1,$2,$3,'placeholder question','handed_over')''', console.A, message, conversation)
    actor = SimpleNamespace(tenant_id=console.A)
    result = await execute('feedback', Feedback(message_id=message, status='bad', correct_answer='placeholder correction'), actor, uuid4())
    assert result['faq_draft_id']
    assert len((await execute('review', None, actor, uuid4()))['messages']) == 1
    assert (await execute('stats', None, actor, uuid4()))['weeks'][0]['bad_answers'] == 1
    row = await w4.pool.fetchrow('SELECT state,data FROM tank.trigger_bot_drafts WHERE tenant_id=$1', console.A)
    assert row['state'] == 'draft' and 'placeholder correction' in row['data']


@pytest.mark.asyncio
async def test_r56_draft_activation_once(w4, monkeypatch):
    from fastapi import HTTPException
    from trigger_bot_api import confirm_draft
    from trigger_bot_contract import ConfirmDraft
    from trigger_bot_api import digest
    import trigger_crm
    monkeypatch.setattr(trigger_crm, 'binding', lambda actor: None)
    crm_write = AsyncMock(return_value={'id': str(uuid4())})
    monkeypatch.setattr(trigger_crm, 'confirmed_bot_lead', crm_write)
    w4.bot.has_rig = AsyncMock(return_value=True)
    w4.runtime._rig_call = AsyncMock(return_value=__import__('httpx').Response(200, json={'id': 'placeholder-quote'}))
    for kind in ('lead', 'quote'):
        draft = uuid4()
        data = {'contact': {'name': 'placeholder person', 'email': 'placeholder@example.invalid'}, 'notice_version': 'placeholder-v1'}
        await w4.pool.execute('INSERT INTO tank.trigger_bot_drafts(tenant_id,id,kind,data) VALUES($1,$2,$3,$4::jsonb)', console.A, draft, kind, json.dumps(data))
        args = ConfirmDraft(draft_id=draft, expected_digest=digest(data))
        with pytest.raises(HTTPException) as refused:
            await confirm_draft(w4.bot, SimpleNamespace(tenant_id=console.A), kind+'.confirm',
                ConfirmDraft(draft_id=draft, expected_digest='placeholder-stale-digest'), uuid4())
        assert refused.value.status_code == 409
        assert await w4.pool.fetchval('SELECT state FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND id=$2', console.A, draft) == 'draft'
        assert crm_write.await_count == (1 if kind == 'quote' else 0)
        results = await asyncio.gather(*(confirm_draft(w4.bot, SimpleNamespace(tenant_id=console.A),
            kind+'.confirm', args, uuid4()) for _ in range(2)), return_exceptions=True)
        assert len([r for r in results if isinstance(r, dict) and r.get('state') == 'confirmed']) == 1
        assert len([r for r in results if isinstance(r, HTTPException) and r.status_code == 409]) == 1
        with pytest.raises(HTTPException):
            await confirm_draft(w4.bot, SimpleNamespace(tenant_id=console.A), kind+'.confirm', args, uuid4())
    crm_write.assert_awaited_once()
    w4.runtime._rig_call.assert_awaited_once()


def test_sheet_has_exactly_one_fixture_case_per_row():
    sheet = (ROOT / 'docs/acceptance/trigger.md').read_text()
    ids = re.findall(r'^\| (R\d\d) \|', sheet, flags=re.M)
    tree = ast.parse(Path(__file__).read_text())
    cases = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and re.match(r'test_r\d\d_', node.name)]
    assert ids == list(ROWS) == [node.name[5:8].upper() for node in cases]
    assert len(set(ids)) == len(ids)
    assert all(not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                       and d.func.attr == 'parametrize' for d in node.decorator_list) for node in cases)
    names = (ROOT / 'docs/ops/FOUNDER-SETTINGS.md').read_text()
    for setting in set(re.findall(r'\b(?:TRIGGER_|SMTP_)[A-Z_]+\b', sheet)):
        assert setting in names, setting
