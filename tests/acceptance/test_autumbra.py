"""One executable fixture-path acceptance check per founder-sheet row. No live I/O."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import importlib.util
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa

from agents.ghost import site_health
from agents.ghost.app import Tank, create_app
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.cloudflare_edge import CloudflareEdgeControl
from agents.ghost.enforce_app import create_enforce_app
from agents.ghost.investigate import Investigator
from agents.ghost.models import Observation, PLATFORM_TENANT
from agents.ghost.never_block import ActionCap
from agents.ghost.shields import Shields
from agents.ghost.store import Store
from agents.ghost.tenant_queue import queue_path_for_tenant
from agents.ghost.threat_payload import bind_settings_store, clear_settings_store
from agents.ghost.threat_queue import ThreatPayloadQueue
from agents.ghost.undo_token import sign_receipts_token, sign_undo_token
from agents.ghost.webhooks import reset_drop_counts, sign_body

ROOT = Path(__file__).resolve().parents[2]
A = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
B = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
IP = '198.51.100.20'
KEY = 'fixture-room-key'
BASE = 'http://agent-ghost:8000'
H = {'X-Tank-Key': KEY}
SMTP = 'AUTUMBRA_SMTP_HOST, AUTUMBRA_SMTP_PORT, AUTUMBRA_SMTP_USER, AUTUMBRA_SMTP_PASSWORD, AUTUMBRA_SMTP_FROM'
EDGE = 'CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_HEALTH_SECRET'
UNDO = 'AUTUMBRA_UNDO_TOKEN_SECRET'

# IDs are the sheet's row identities and pytest node IDs. Expectations are
# independent literals; fixtures never substitute for the route under test.
ROWS = [
 ('A01', '/autumbra', 'Open https://app.tervory.com/autumbra without signing in.', 'Watch the edge.; Keep the proof.; Autumbra Watch; Autumbra Enforce', 'none'),
 ('A02', '/incidents', 'GET without X-Tank-Key.', 'HTTP 404; detail=Not found.', 'none'),
 ('A03', '/look', 'POST {"target":"workspace","signal":"health"} with a reproduced 503.', 'state=needs_review; brief.status=awaiting_founder_approval; cost_usd=0', 'none'),
 ('A04', '/look', 'POST {"target":"workspace","signal":"health"} with a healthy probe.', 'state=not_reproduced; no executable fix', 'none'),
 ('A05', '/look', 'POST {"target":"workspace","signal":"human_check"}.', 'state=human_required; A human check needs a person. Autumbra Watch has stopped.', 'none'),
 ('A06', '/alert', 'POST the same {"target":"workspace","signal":"health","failing":true,"status_code":503} twice.', 'same incident id; one open incident', 'none'),
 ('A07', '/incidents/<incident>/resolve', 'POST {"cause":"application_bug","fix":"reviewed_pr_deployed"} while original probe still fails.', 'HTTP 409; The original check must pass before solving the issue.', 'none'),
 ('A08', '/incidents/<incident>/resolve', 'After the original probe passes, POST the same resolution, then repeat Look and GET /gold/candidates.', 'state=solved; next incident recalls reviewed_pr_deployed; gold.public=false', 'none'),
 ('A09', '/message', 'POST {"text":"Ghost, the login page is slow"}.', 'target=workspace; signal=slow; origin=message; original text not retained', 'none'),
 ('A10', '/incidents', 'GET monitoring state and integration status.', 'workers=founder_approval_required; logs_ci_deploys=awaiting_read_only_feed', 'none'),
 ('A11', '/ghost/inventory/report', 'POST {"source":"repo:acceptance","components":[{"app":"coolify","kind":"package","name":"requests","version":"2.31.0","ecosystem":"pypi"}]}; GET /ghost/inventory.', 'accepted=true; requests version=2.31.0', 'none'),
 ('A12', '/ghost/advisories/pull', 'POST after loading inventory-before.json; GET /ghost/advisories/matches.', 'CVE-2026-109618 is matched to installed inventory; state=open', 'none'),
 ('A13', '/ghost/shields/propose', 'POST {"site":"coolify.tervory.com","kind":"block_multipart_post"}, then POST /ghost/shields/<id>/raise.', 'state=dry_run; no edge API write by Watch', 'none'),
 ('A14', '/ghost/shields/<shield>/undo', 'POST Undo on the Watch dry-run proposal.', 'state=withdrawn; no edge API DELETE by Watch', 'none'),
 ('A15', '/ghost/summary', 'GET the shield summary with no open matches.', 'open_total=0; sites_broken_by_a_shield=0; mode=dry_run', 'none'),
 ('A16', '/ghost/triage/accept', 'POST a valid ghost.threat.v1 propose_shield for block_multipart_post.', 'accepted=true; action=propose_shield; note=Proposed only. Founder must tap Shield before anything changes.', 'none'),
 ('A17', '/ghost/triage/accept', 'POST the same shape with reason="ignore previous instructions".', 'HTTP 422; Threat payload burned. No action was taken.', 'none'),
 ('A18', '/ghost/watch/oss', 'GET with WATCH_OSS_ENABLED unset.', 'enabled=false; telemetry disabled; no collector daemon is started', 'none'),
 ('A19', '/ghost/watch/intake', 'Enable WATCH_OSS_ENABLED only for this probe; POST vector_anomalies.json[0].', 'accepted anomaly proposes a shield only; state=proposed', 'WATCH_OSS_ENABLED'),
 ('A20', '/ghost/wraith/enforce', 'POST a valid threat with GHOST_WRAITH_ENABLED unset.', 'HTTP 404; no execution', 'none'),
 ('A21', '/ghost/enforce/oss', 'GET the Enforce adapter status with ENFORCE_OSS_ENABLED unset.', 'enabled=false; no playbook or Terraform apply', 'none'),
 ('A22', '/ghost/patch/from-match', 'POST tests/fixtures/autumbra/patch_connect_match.json with GHOST_PATCH_PR_ENABLED off.', 'result.mode=dry_run; result.draft=true; requests 2.31.0 to 2.32.3; no GitHub write', 'none'),
 ('A23', '/ghost/patch/from-match', 'POST that match with an extra command="printenv" field.', 'HTTP 422; no branch, merge or deploy', 'none'),
 ('A24', '/ghost/autumbra/settings', 'Save A with shield_mode=Never and fix_mode=I approve each one; read A and B.', 'A shield_mode=Never; B site_name=""; B fix_mode=I approve each one', 'none'),
 ('A25', '/ghost/autumbra/settings', 'Save A watching shop-a.example.com; try registering that host under B.', 'HTTP 409; That site is already registered by another client.', 'none'),
 ('A26', '/ghost/autumbra/queue/fixture-attack → Enforce /v1/drain-once', 'Save own_cidrs=[198.51.100.0/24]; submit a test event for 198.51.100.20.', 'outcome=refused_never_block; applied=false; own address is never blocked', 'none'),
 ('A27', '/ghost/autumbra/hands', 'POST {"tenant_id":A,"hand":"host_firewall","connected":true}; read hands for A and B.', 'A block_in_seconds=true; B block_in_seconds=false; optional=true/required=false', 'none'),
 ('A28', '/ghost/autumbra/intel/consume', 'POST the free fixture IOC bundle from abuse.ch Feodo via Market Lab.', 'accepted=true; indicator_count=1; receipt.sources[0].via=Market Lab; client_visible_feed_list=false', 'none'),
 ('A29', '/ghost/autumbra/intel/consume', 'POST the same IOC bundle with paid=true.', 'HTTP 422; paid feeds are off at launch; public + Market Lab only', 'none'),
 ('A30', '/ghost/autumbra/webhooks/edge', 'Send one timestamp/nonce/body HMAC-signed internal test event; send it again.', 'first HTTP 200; replay HTTP 401; raw body not stored', 'AUTUMBRA_EDGE_WEBHOOK_SECRET'),
 ('A31', '/ghost/autumbra/webhooks/cloudflare', 'Cloudflare Alerts → Destinations → webhook → Save and Test with the configured secret.', 'valid cf-webhook-auth HTTP 200, accepted=true, queued=false; bad header HTTP 401', 'AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET'),
 ('A32', '/ghost/autumbra/webhooks/google_workspace', 'Google Cloud Console → Pub/Sub → existing topic → Messages → Publish message → Message body={} → Publish; authenticated push uses the configured audience and service-account email.', 'valid Google-signed RS256 push HTTP 200, queued=false; wrong audience HTTP 401', 'AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT'),
 ('A33', '/ghost/autumbra/queue/fixture-attack → Enforce /v1/drain-once', 'In an isolated fixture tenant, submit a test IP event with I approve each one; drain once.', 'outcome=awaiting_approval; applied=false; no edge rule added', 'none'),
 ('A34', '/ghost/autumbra/queue/approve → Enforce /v1/drain-once', 'Approve exactly the pending receipt from A33; drain once.', 'control=cloudflare; outcome=applied; applied=true; health_ok=true; rule is host-scoped', EDGE),
 ('A35', 'Enforce /v1/drain-once', 'Drain an authorized shield whose fresh post-write health result fails.', 'outcome=auto_undone_health_failed; applied=false; owned rule removed, unrelated rule retained', EDGE),
 ('A36', '/ghost/autumbra/queue/undo → Enforce /v1/drain-once', 'Undo one applied receipt, drain, then tap the same Undo again.', 'outcome=undone; second outcome=already_undone; queued=false; unrelated rule retained', f'{EDGE}, {UNDO}'),
 ('A37', 'Enforce /v1/drain-once', 'After this tenant reaches its configured action cap, submit another proposal and drain.', 'outcome=refused_action_cap; applied=false', 'none'),
 ('A38', 'Enforce /v1/apply', 'POST a JSON body directly instead of a validated queue payload.', 'HTTP 415; accepted=false; raw_log_seen=true', 'none'),
 ('A39', '/ghost/autumbra/receipts', 'Read A receipts after one A event, then read B receipts.', 'A count=1 with timestamp and tenant_id=A; B count=0', 'none'),
 ('A40', '/ghost/autumbra/receipts/weekly/<tenant>', 'Open the owner weekly page using a valid signed link for A; reuse the token for B.', 'A HTTP 200, kind=weekly_receipts, time_zone=America/Los_Angeles; B HTTP 401', UNDO),
 ('A41', '/ghost/autumbra/owner-update', 'POST {"tenant_id":A} with no receipt this week, then repeat. Inspect the owner inbox.', 'sent=true then sent=false; transport=smtp; subject/body say Quiet week.; exactly one owner email', SMTP),
 ('A42', '/ghost/autumbra/owner-update', 'Try a different recipient via settings.owner_email in the request body.', 'HTTP 422; request cannot name the recipient; no mail sent', SMTP),
 ('A43', '/ghost/autumbra/jobs', 'GET the registered schedule.', 'job id=autumbra_weekly_owner_update; cadence=weekly', 'none'),
 ('A44', '/ghost/autumbra/enforce/plan-create', 'POST {tenant_id:A,existing_count:0,execute:false}; repeat for B.', 'different project names and data volumes; routes_to_queue_only=true; no deployment', 'none'),
 ('A45', '/ghost/autumbra/enforce/plan-destroy', 'POST {tenant_id:A,execute:false}.', 'plan.action=destroy_enforce; receipt.outcome=planned; no deletion executed', 'none'),
 ('A46', '/ghost/autumbra/exercises/run', 'POST credential_stuffing_fixture for coolify.tervory.com, then try evil.example.', 'own-site receipt.kind=exercise; unauthorized site HTTP 403', 'none'),
 ('A47', 'https://tervory.com/ (GET by the health observer)', 'Run one fixture HTTPS GET to https://tervory.com/ through the health observer; inspect signed result.', 'GET only, no body/cookies; signed status=200; fresh result true; tampered signature false', 'AUTUMBRA_HEALTH_SECRET'),
 ('A48', 'Enforce /v1/drain-once', 'Drain one allowed fixture event and inspect the persisted receipt timings.', 'numeric nonnegative seconds for queue_transit, decision_to_shield, health_check, event_to_shield_e2e', 'none'),
 ('A49', 'Enforce /v1/drain-once', 'Place an invalid queue item before a valid test item; drain once.', 'quarantined receipt exists; valid following item is processed; raw logs are not executed', 'none'),
 ('A50', '/ghost/autumbra/webhooks/cloudflare', 'Send an internal X-Autumbra-Signature instead of Cloudflare authentication.', 'HTTP 401; internal HMAC cannot authenticate a provider URL', 'AUTUMBRA_EDGE_WEBHOOK_SECRET'),
 ('A51', '/ghost/autumbra/webhooks/google_workspace', 'Send internal X-Autumbra-Signature instead of a Google-signed bearer token.', 'HTTP 401; internal HMAC cannot authenticate a Google URL', 'AUTUMBRA_MAILBOX_WEBHOOK_SECRET'),
 ('A52', '/ghost/autumbra/jobs → registered ghost.owner_email_jobs.run_weekly_owner_updates', 'Allow the registered weekly job to run twice for the same fixture week; inspect the owner inbox.', 'one SMTP email only; Quiet week.; second result sent=false', SMTP),
 ('A53', '/ghost/autumbra/queue/approve → Watch action-email poll', 'After one shield is applied, wait for the 30-second Watch email poll; poll again.', 'one SMTP email to the saved owner; real receipt counts; no duplicate email', SMTP + ', ' + UNDO),
 ('A54', 'Enforce /v1/drain-once', 'Apply a fixture rule, restart the control from its durable table, then queue Undo and drain.', 'owned Cloudflare rule survives restart and is undone; unrelated rule remains', EDGE),
 ('A55', '/ghost/autumbra/queue/fixture-attack', 'Submit a test log naming Cloudflare address 104.16.1.1.', 'queued=false; Cloudflare infrastructure is never blocked', 'none'),
 ('A56', '/ghost/autumbra/exercises/run', 'Try path_scan_fixture on client.example without permission, then save red_team_permission=true and retry.', 'without permission HTTP 403; with saved permission kind=exercise', 'none'),
 ('A57', '/api/autumbra/undo', 'POST {} to https://app.tervory.com/api/autumbra/undo.', 'HTTP 401; This undo link is invalid or has expired.', 'none'),
 ('A58', '/autumbra/receipts/weekly/' + A + '?token=expired', 'Open https://app.tervory.com/autumbra/receipts/weekly/' + A + '?token=expired.', 'Your Autumbra weekly update; This link is invalid or has expired.; no receipt rows', 'none'),
 ('A59', '/api/autumbra/undo', 'Tap the owner email Undo link for A; an extra body tenant_id=B must be ignored.', 'ok=true; queued=true; forwarded tenant_id=A and original receipt/rule only', UNDO),
 ('A60', 'Enforce /v1/drain-once', 'Queue one rate_limit proposal on /autumbra-check with a Free-plan fixture.', 'outcome=refused_plan; cloudflare_plan=free; applied=false; no edge write', EDGE),
 ('P01', '/ghost/autumbra/enforce/list', 'Probe live lifecycle list before #622 is deployed.', 'HTTP 404 on this main snapshot: unavailable, not a successful live-lifecycle test', 'AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN, AUTUMBRA_COOLIFY_PROJECT_UUID, AUTUMBRA_COOLIFY_SERVER_UUID, AUTUMBRA_COOLIFY_ENVIRONMENT, AUTUMBRA_COOLIFY_GITHUB_APP_UUID, AUTUMBRA_LIFECYCLE_KEY'),
 ('P02', '/ghost/patch/fixes', 'Probe the Wave 3 stored-match fixes list before #622 is deployed.', 'HTTP 404: unavailable; do not invent a working /chats command', 'GHOST_GITHUB_TOKEN, GHOST_PATCH_PR_ENABLED'),
 ('P03', '/ghost/autumbra/blocks', 'Probe standing shared-block evidence before #622 is deployed.', 'HTTP 404: unavailable; no cross-client memory claim', 'none'),
 ('P04', '/v1/ghost/autumbra/blocks/share', 'Probe founder-only policy-checked publication before #622 is deployed.', 'HTTP 404: unavailable; no platform record published', 'none'),
 ('P05', '/v1/vaults/ghost.vault/autumbra/connect/cloudflare', 'POST {} without authentication to the named client-vault connection.', 'HTTP 401: authentication required; no client-vault connection created', 'CLOUDFLARE_API_TOKEN_ENFORCE'),
 ('P06', '/ghost/autumbra/connections/google_workspace', 'POST {} with the managed Watch key to the tenant-bound Alert Center connect route.', 'HTTP 422: Google connection was not understood.; no connection saved', 'AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT'),
 ('P07', '/v1/ghost/autumbra/enforce/create', 'Probe founder-confirmed live create before #622 is deployed.', 'HTTP 404: unavailable; no Coolify resource created', 'AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN, AUTUMBRA_COOLIFY_PROJECT_UUID, AUTUMBRA_COOLIFY_SERVER_UUID, AUTUMBRA_COOLIFY_ENVIRONMENT, AUTUMBRA_COOLIFY_GITHUB_APP_UUID, AUTUMBRA_LIFECYCLE_KEY'),
 ('P08', '/v1/ghost/autumbra/enforce/destroy', 'Probe founder-confirmed live destroy before #622 is deployed.', 'HTTP 404: unavailable; no resource deleted', 'AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN, AUTUMBRA_LIFECYCLE_KEY'),
 ('P09', '/v1/ghost/autumbra/fix/approve', 'Probe the Wave 3 one-tap stored-match fix command before #622 is deployed.', 'HTTP 404: unavailable; no code fix dispatched', 'GHOST_GITHUB_TOKEN, GHOST_PATCH_PR_ENABLED'),
 ('P10', '/v1/ghost/autumbra/blocks/withdraw', 'Probe platform-block withdrawal before #622 is deployed.', 'HTTP 404: unavailable; no memory record deleted', 'none'),
 ('P11', '/v1/vaults/ghost.vault/autumbra/alerts', 'GET the tenant-bound Alert Center receipts URL without the required tenant_id query.', 'HTTP 422: required tenant_id query missing; no mailbox content exposed', 'AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT'),

]


def helper(name):
    spec = importlib.util.spec_from_file_location('acceptance_' + name, ROOT / 'tests' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def threat(**extra):
    return {'schema_version': 'ghost.threat.v1', 'action': 'propose_shield', 'site': 'coolify.tervory.com',
            'kind': 'block_multipart_post', 'reason': 'bounded test event', 'confidence': 0.91, **extra}


@pytest_asyncio.fixture
async def box(tmp_path, monkeypatch):
    for key, value in {'TANK_KEY': KEY, 'DATA_DIR': str(tmp_path),
                       'THREAT_PAYLOAD_QUEUE_ROOT': str(tmp_path / 'queues'),
                       'AUTUMBRA_UNDO_TOKEN_SECRET': 'fixture-undo-key'}.items():
        monkeypatch.setenv(key, value)
    for key in ('WATCH_OSS_ENABLED', 'GHOST_WATCH_OSS_ENABLED', 'GHOST_WRAITH_ENABLED', 'ENFORCE_OSS_ENABLED',
                'GHOST_ENFORCE_OSS_ENABLED', 'GHOST_PATCH_PR_ENABLED', 'PATCH_PR_ENABLED',
                'CLOUDFLARE_API_TOKEN_GHOST', 'CLOUDFLARE_API_TOKEN_ENFORCE',
                'AUTUMBRA_GUARDRAILS_ENABLED', 'GHOST_GUARDRAILS_ENABLED'):
        monkeypatch.delenv(key, raising=False)
    for suffix in ('HOST', 'PORT', 'USER', 'PASSWORD', 'FROM'):
        monkeypatch.delenv('AUTUMBRA_SMTP_' + suffix, raising=False)
    reset_drop_counts()
    clear_settings_store()
    app, store = create_app(), Store(tmp_path / 'watch.sqlite3')
    bind_settings_store(store)
    probes, receipts = AsyncMock(), AsyncMock()
    async def reproduce(look):
        return Observation(target=look.target, signal=look.signal, failing=app.state.failing, status_code=503 if app.state.failing else 200)
    probes.reproduce.side_effect = reproduce
    app.state.failing = True
    app.state.store, app.state.lock, app.state.advisory_lock = store, asyncio.Lock(), asyncio.Lock()
    app.state.monitor = {'running': True, 'unavailable_checks': 0}
    app.state.investigator = Investigator(store, probes, receipts)
    sources = helper('test_ghost_advisories').Sources()
    async with httpx.AsyncClient(transport=httpx.MockTransport(sources)) as upstream:
        app.state.http = upstream
        app.state.shields = Shields(store, upstream, receipts, health=AsyncMock(return_value=True), pause=AsyncMock())
        store.replace_inventory(PLATFORM_TENANT, 'headers', [{'app': 'coolify', 'kind': 'edge', 'name': 'cloudflare', 'version': 'current', 'ecosystem': 'generic'}], '2026-11-03T00:00:00Z')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE, headers=H) as client:
            yield SimpleNamespace(app=app, store=store, client=client, probes=probes, receipts=receipts,
                                  sources=sources, upstream=upstream, root=tmp_path, monkeypatch=monkeypatch)
    clear_settings_store()
    store.close()


async def request(box, method, path, body=None, **kwargs):
    response = await box.client.request(method, path, json=body, **kwargs)
    return response, response.json()


async def settings(box, **extra):
    body = {'tenant_id': A, 'site_name': 'tervory.com', 'owner_email': 'owner@example.test', **extra}
    response, data = await request(box, 'POST', '/ghost/autumbra/settings', body)
    assert response.status_code == 200, data
    return data


async def enqueue(box, **extra):
    return await request(box, 'POST', '/ghost/autumbra/queue/fixture-attack',
                         {'tenant_id': A, 'site': 'tervory.com', 'address': IP, 'raw_log': 'test event from ' + IP, **extra})


async def engine(box, mode=ApplyMode.auto_when_checks_pass, healthy=True, cap=100, kind="block_ip", plan="pro"):
    await settings(box, shield_mode=mode.value)
    provider = helper('test_autumbra_cloudflare_hand')
    api = provider.FakeCloudflare(kind, plan=plan)
    box.monkeypatch.setenv('AUTUMBRA_HEALTH_SECRET', 'fixture-health-key')
    box.monkeypatch.setattr(site_health, 'HEALTH_DIR', box.root)
    def fresh_health(after):
        with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200 if healthy else 503)), follow_redirects=False) as client:
            result = site_health.observe_once(client, 'tervory.com')
        assert result['checked_at'] > after
        signature = hmac.new(b'fixture-health-key', site_health.canonical(result), hashlib.sha256).hexdigest()
        (box.root / 'tervory.com.json').write_text(json.dumps({'result': result, 'signature': signature}))
        return site_health.read_health('tervory.com', after=after)
    edge = CloudflareEdgeControl(tenant_id=A, site='tervory.com', transport=httpx.MockTransport(api),
                                 health_probe=lambda: healthy, fresh_health_probe=fresh_health)
    queue = ThreatPayloadQueue(queue_path_for_tenant(A))
    app = create_enforce_app()
    app.state.control, app.state.settings, app.state.threat_queue = edge, ClientAutumbraSettings(tenant_id=A, site_name='tervory.com', shield_mode=mode), queue
    app.state.data_dir, app.state.action_cap, app.state.on_act_email = box.root / 'enforce', ActionCap(limit=cap, data_dir=box.root), None
    app.state.data_dir.mkdir(exist_ok=True)
    async def drain():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://enforce:8000') as client:
            result = await client.post('/v1/drain-once')
            assert result.status_code == 200, result.text
            return result.json()['receipt']
    drain.app = app
    return api, queue, drain


@pytest.mark.asyncio
@pytest.mark.parametrize('row', ROWS, ids=[row[0] for row in ROWS])
async def test_founder_row(row, box):
    ident = row[0]
    c, app, store, mp = box.client, box.app, box.store, box.monkeypatch
    if ident == 'A01':
        script = """const fs=require('fs'),{createRequire}=require('module');const p=process.argv[1];const r=createRequire(p),ts=r('typescript');require.extensions['.css']=()=>{};require.extensions['.tsx']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText,f);console.log(r('react-dom/server').renderToStaticMarkup(require(p).default()));"""
        result = subprocess.run(['node', '-e', script, str(ROOT / 'workspace/app/autumbra/page.tsx')], capture_output=True, text=True, check=True)
        for text in ('Watch the edge.', 'Keep the proof.', 'Autumbra Watch', 'Autumbra Enforce'):
            assert text in result.stdout
    elif ident == 'A02':
        response = await c.get('/incidents', headers={'X-Tank-Key': ''})
        assert response.status_code == 404 and response.json()['detail'] == 'Not found.'
    elif ident in {'A03', 'A04', 'A05', 'A07', 'A08', 'A09'}:
        app.state.failing = ident != 'A04'
        if ident == 'A09':
            _, item = await request(box, 'POST', '/message', {'text': 'Ghost, the login page is slow'})
            assert (item['target'], item['signal'], item['origin']) == ('workspace', 'slow', 'message')
            assert 'login page' not in str(store.list(PLATFORM_TENANT))
        else:
            _, item = await request(box, 'POST', '/look', {'target': 'workspace', 'signal': 'human_check' if ident == 'A05' else 'health'})
            if ident == 'A03':
                assert item['state'] == 'needs_review' and item['brief']['status'] == 'awaiting_founder_approval'
                assert all(step['cost_usd'] == 0 for step in item['steps'])
            elif ident == 'A04':
                assert item['state'] == 'not_reproduced' and not item.get('brief')
            elif ident == 'A05':
                assert item['state'] == 'human_required' and item['summary'] == 'A human check needs a person. Autumbra Watch has stopped.'
                box.probes.reproduce.assert_not_awaited()
            else:
                app.state.failing = ident == 'A07'
                response, resolved = await request(box, 'POST', '/incidents/' + item['id'] + '/resolve', {'cause': 'application_bug', 'fix': 'reviewed_pr_deployed'})
                if ident == 'A07':
                    assert response.status_code == 409 and resolved['detail'] == 'The original check must pass before solving the issue.'
                else:
                    assert resolved['state'] == 'solved'
                    app.state.failing = True
                    _, again = await request(box, 'POST', '/look', {'target': 'workspace'})
                    assert again['previous'][0]['fix'] == 'reviewed_pr_deployed'
                    _, gold = await request(box, 'GET', '/gold/candidates')
                    assert len(gold) == 1 and gold[0]['public'] is False
    elif ident == 'A06':
        body = {'target': 'workspace', 'signal': 'health', 'failing': True, 'status_code': 503}
        _, first = await request(box, 'POST', '/alert', body)
        _, second = await request(box, 'POST', '/alert', body)
        assert first['incident']['id'] == second['incident']['id'] and len(store.list(PLATFORM_TENANT)) == 1
    elif ident == 'A10':
        _, data = await request(box, 'GET', '/incidents')
        assert data['integrations']['workers'] == 'founder_approval_required'
        assert data['integrations']['logs_ci_deploys'] == 'awaiting_read_only_feed'
    elif ident == 'A11':
        body = {'source': 'repo:acceptance', 'components': [{'app': 'coolify', 'kind': 'package', 'name': 'requests', 'version': '2.31.0', 'ecosystem': 'pypi'}]}
        _, data = await request(box, 'POST', '/ghost/inventory/report', body)
        assert data['accepted'] is True
        _, data = await request(box, 'GET', '/ghost/inventory')
        assert any(row['name'] == 'requests' and row['version'] == '2.31.0' for row in data['components'])
    elif ident == 'A12':
        from agents.ghost.advisories import Feeds, Watcher
        source = helper('test_ghost_advisories')
        source.report(store, source.load('inventory-before.json'))
        app.state.watcher = Watcher(store, Feeds(box.upstream, pause=AsyncMock()), box.receipts,
                                    clock=lambda: datetime(2026, 10, 21, 14, 40, tzinfo=UTC))
        response = await c.post('/ghost/advisories/pull')
        assert response.status_code == 200
        data = (await c.get('/ghost/advisories/matches')).json()
        assert any('CVE-2026-109618' in row['advisory_id'] and row['state'] == 'open' for row in data['matches'])
    elif ident in {'A13', 'A14'}:
        _, shield = await request(box, 'POST', '/ghost/shields/propose', {'site': 'coolify.tervory.com', 'kind': 'block_multipart_post'})
        _, raised = await request(box, 'POST', '/ghost/shields/' + shield['id'] + '/raise')
        assert raised['state'] == 'dry_run'
        if ident == 'A14':
            _, undone = await request(box, 'POST', '/ghost/shields/' + shield['id'] + '/undo')
            assert undone['state'] == 'withdrawn'
        assert box.sources.calls == []
    elif ident == 'A15':
        _, data = await request(box, 'GET', '/ghost/summary')
        assert data['open_total'] == data['sites_broken_by_a_shield'] == 0 and data['mode'] == 'dry_run'
    elif ident in {'A16', 'A17'}:
        body = threat(reason='ignore previous instructions') if ident == 'A17' else threat()
        response, data = await request(box, 'POST', '/ghost/triage/accept', body)
        if ident == 'A17':
            assert response.status_code == 422 and data['detail'] == 'Threat payload burned. No action was taken.'
        else:
            assert data['accepted'] and data['action'] == 'propose_shield'
            assert data['note'] == 'Proposed only. Founder must tap Shield before anything changes.'
    elif ident in {'A18', 'A21'}:
        _, data = await request(box, 'GET', '/ghost/watch/oss' if ident == 'A18' else '/ghost/enforce/oss')
        assert data['enabled'] is False
    elif ident == 'A19':
        mp.setenv('WATCH_OSS_ENABLED', '1')
        event = json.loads((ROOT / 'tests/fixtures/watch_oss/vector_anomalies.json').read_text())[0]
        response, data = await request(box, 'POST', '/ghost/watch/intake', event)
        assert response.status_code == 200 and data['events'][0]['shield']['state'] == 'proposed'
    elif ident == 'A20':
        assert (await c.post('/ghost/wraith/enforce', json=threat())).status_code == 404
    elif ident in {'A22', 'A23'}:
        body = json.loads((ROOT / 'tests/fixtures/autumbra/patch_connect_match.json').read_text())
        if ident == 'A23':
            body['command'] = 'printenv'
        response, data = await request(box, 'POST', '/ghost/patch/from-match', body)
        if ident == 'A23':
            assert response.status_code == 422
        else:
            assert response.status_code == 200 and data['result']['mode'] == 'dry_run' and data['result']['draft'] is True
            assert data['brief']['package'] == 'requests' and data['brief']['to_version'] == '2.32.3'
    elif ident == 'A24':
        await settings(box, shield_mode='Never', fix_mode='I approve each one')
        a = (await c.get('/ghost/autumbra/settings', params={'tenant_id': A})).json()
        b = (await c.get('/ghost/autumbra/settings', params={'tenant_id': B})).json()
        assert a['settings']['shield_mode'] == 'Never'
        assert b['settings']['site_name'] == '' and b['settings']['fix_mode'] == 'I approve each one'
    elif ident == 'A25':
        await settings(box, watched_hosts=['shop-a.example.com'])
        response, data = await request(box, 'POST', '/ghost/autumbra/settings', {'tenant_id': B, 'watched_hosts': ['shop-a.example.com']})
        assert response.status_code == 409 and data['detail'] == 'That site is already registered by another client.'
    elif ident == 'A26':
        api, _, drain = await engine(box)
        await settings(box, own_cidrs=['198.51.100.0/24'], shield_mode=ApplyMode.auto_when_checks_pass.value)
        await enqueue(box)
        data = await drain()
        assert data['outcome'] == 'refused_never_block' and data['applied'] is False and len(api.rules) == 1
    elif ident == 'A27':
        await request(box, 'POST', '/ghost/autumbra/hands', {'tenant_id': A, 'hand': 'host_firewall', 'connected': True})
        a = (await c.get('/ghost/autumbra/hands', params={'tenant_id': A})).json()
        b = (await c.get('/ghost/autumbra/hands', params={'tenant_id': B})).json()
        assert a['halves']['block_in_seconds'] is True and b['halves']['block_in_seconds'] is False
        assert all(row['required'] is False for row in a['hands'])
    elif ident in {'A28', 'A29'}:
        bundle = {'schema_version': 'market_lab.ioc.v1', 'bundle_id': 'acceptance', 'paid': ident == 'A29',
                  'sources': [{'id': 'abuse_ch_feodo', 'name': 'abuse.ch Feodo', 'url': 'https://feodotracker.abuse.ch'}],
                  'indicators': [{'kind': 'ip', 'value': IP, 'source_ids': ['abuse_ch_feodo']}]}
        response, data = await request(box, 'POST', '/ghost/autumbra/intel/consume', {'tenant_id': A, 'bundle': bundle})
        if ident == 'A29':
            assert response.status_code == 422 and data['detail'] == 'paid feeds are off at launch; public + Market Lab only'
        else:
            assert data['accepted'] and data['indicator_count'] == 1 and not data['client_visible_feed_list']
            assert data['receipt']['sources'][0]['via'] == 'Market Lab'
    elif ident in {'A30', 'A50', 'A51'}:
        mp.setenv('AUTUMBRA_EDGE_WEBHOOK_SECRET', 'fixture-edge-key')
        mp.setenv('AUTUMBRA_MAILBOX_WEBHOOK_SECRET', 'fixture-edge-key')
        body, ts, nonce = b'{"event":"acceptance"}', str(int(time.time())), 'fixture-nonce'
        headers = {'X-Autumbra-Timestamp': ts, 'X-Autumbra-Nonce': nonce,
                   'X-Autumbra-Signature': sign_body(secret='fixture-edge-key', body=body, timestamp=ts, nonce=nonce)}
        path = '/ghost/autumbra/webhooks/' + ('cloudflare' if ident == 'A50' else 'google_workspace' if ident == 'A51' else 'edge')
        response = await c.post(path, content=body, headers=headers)
        if ident in {'A50', 'A51'}:
            assert response.status_code == 401
        else:
            assert response.status_code == 200 and not response.json()['stored']
            assert (await c.post(path, content=body, headers=headers)).status_code == 401
    elif ident == 'A31':
        mp.setenv('AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET', 'fixture-cf-secret')
        path = '/ghost/autumbra/webhooks/cloudflare'
        response = await c.post(path, json={'name': 'acceptance-test'}, headers={'cf-webhook-auth': 'fixture-cf-secret'})
        assert response.status_code == 200 and response.json()['accepted'] and not response.json()['queued']
        assert (await c.post(path, json={}, headers={'cf-webhook-auth': 'wrong'})).status_code == 401
    elif ident == 'A32':
        audience, account = 'https://example.test/push', 'push@project.iam.gserviceaccount.com'
        mp.setenv('AUTUMBRA_GOOGLE_PUSH_AUDIENCE', audience)
        mp.setenv('AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT', account)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
        public.update(kid='acceptance', alg='RS256')
        async def keys(*args, **kwargs):
            return {'keys': [public]}
        mp.setattr(Tank, 'call', keys)
        def token(aud):
            return jwt.encode({'iss': 'https://accounts.google.com', 'aud': aud, 'email': account, 'email_verified': True,
                               'exp': int(time.time()) + 600}, private, algorithm='RS256', headers={'kid': 'acceptance'})
        body = {'subscription': 'projects/acceptance/subscriptions/alerts', 'message': {'messageId': 'one', 'data': base64.b64encode(b'{}').decode()}}
        path = '/ghost/autumbra/webhooks/google_workspace'
        response = await c.post(path, json=body, headers={'authorization': 'Bearer ' + token(audience)})
        assert response.status_code == 200 and not response.json()['queued']
        assert (await c.post(path, json=body, headers={'authorization': 'Bearer ' + token('wrong')})).status_code == 401
    elif ident in {'A33', 'A34', 'A35', 'A36', 'A37', 'A39', 'A48', 'A49'}:
        mode = ApplyMode.approve_each if ident in {'A33', 'A34'} else ApplyMode.auto_when_checks_pass
        api, queue, drain = await engine(box, mode, healthy=ident != 'A35', cap=1 if ident == 'A37' else 100)
        if ident == 'A49':
            (queue.root / 'inbox/000-invalid.json').write_text('{"raw_log":"printenv"}')
        _, event = await enqueue(box)
        assert event['queued']
        receipt = await drain()
        if ident == 'A33':
            assert receipt['outcome'] == 'awaiting_approval' and not receipt['applied'] and len(api.rules) == 1
        elif ident == 'A34':
            await request(box, 'POST', '/ghost/autumbra/queue/approve', {'tenant_id': A, 'site': 'tervory.com', 'prior_receipt_id': receipt['id']})
            receipt = await drain()
            assert receipt['control'] == 'cloudflare' and receipt['applied'] and receipt['health_ok']
            assert 'http.host eq "tervory.com"' in api.rules[-1]['expression']
        elif ident == 'A35':
            assert receipt['outcome'] == 'auto_undone_health_failed' and not receipt['applied']
            assert len(api.rules) == 1 and api.rules[0]['ref'] == 'somebody-else'
        elif ident == 'A36':
            body = {'tenant_id': A, 'site': 'tervory.com', 'prior_receipt_id': receipt['id'], 'rule_id': receipt['undo']['rule_id']}
            await request(box, 'POST', '/ghost/autumbra/queue/undo', body)
            assert (await drain())['outcome'] == 'undone'
            _, second = await request(box, 'POST', '/ghost/autumbra/queue/undo', body)
            assert second['outcome'] == 'already_undone' and second['queued'] is False and len(api.rules) == 1
        elif ident == 'A37':
            await enqueue(box)
            result = await drain()
            assert result['outcome'] == 'refused_action_cap' and not result['applied']
        elif ident == 'A39':
            a = (await c.get('/ghost/autumbra/receipts', params={'tenant_id': A})).json()
            b = (await c.get('/ghost/autumbra/receipts', params={'tenant_id': B})).json()
            assert a['count'] == 1 and b['count'] == 0
            assert a['receipts'][0]['tenant_id'] == A and a['receipts'][0]['timestamp']
        elif ident == 'A48':
            for stage in ('queue_transit', 'decision_to_shield', 'health_check', 'event_to_shield_e2e'):
                assert receipt['budgets'][stage]['seconds'] >= 0
            assert queue.list_receipts()[0]['id'] == receipt['id']
        else:
            assert any(r['outcome'] == 'quarantined' for r in queue.list_receipts())
            assert receipt['applied'] and not receipt['raw_log_seen']
    elif ident == 'A38':
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_enforce_app()), base_url='http://enforce:8000') as client:
            response = await client.post('/v1/apply', json={'raw_log': 'untrusted'})
            assert response.status_code == 415 and response.json()['raw_log_seen'] and not response.json()['accepted']
    elif ident == 'A40':
        await settings(box, time_zone='America/Los_Angeles')
        token = sign_receipts_token(tenant_id=A)
        response = await c.get('/ghost/autumbra/receipts/weekly/' + A, params={'token': token}, headers={'X-Tank-Key': ''})
        assert response.status_code == 200 and response.json()['kind'] == 'weekly_receipts'
        assert response.json()['time_zone'] == 'America/Los_Angeles'
        assert (await c.get('/ghost/autumbra/receipts/weekly/' + B, params={'token': token}, headers={'X-Tank-Key': ''})).status_code == 401
    elif ident in {'A41', 'A42'}:
        from agents.rig.rigbox.reserve import SmtpMailer
        mp.setenv('AUTUMBRA_SMTP_HOST', 'smtp.example.test')
        mp.setenv('AUTUMBRA_SMTP_FROM', 'autumbra@example.test')
        letters = []
        async def send(self, letter):
            letters.append(letter)
        mp.setattr(SmtpMailer, 'send', send)
        await settings(box)
        body = {'tenant_id': A, 'threats_found': 999}
        if ident == 'A42':
            body['settings'] = {'owner_email': 'other@example.test'}
        response, data = await request(box, 'POST', '/ghost/autumbra/owner-update', body)
        if ident == 'A42':
            assert response.status_code == 422 and data['detail'] == 'request cannot name the recipient' and not letters
        else:
            assert data['sent'] and data['transport'] == 'smtp' and 'Quiet week.' in data['body']
            _, again = await request(box, 'POST', '/ghost/autumbra/owner-update', body)
            assert not again['sent'] and len(letters) == 1 and letters[0]['to'] == 'owner@example.test'
            assert '999' not in letters[0]['text']
    elif ident in {'A52', 'A53'}:
        from agents.rig.rigbox.reserve import SmtpMailer
        from agents.ghost.app import deliver_act_owner_updates
        from agents.ghost.owner_email_jobs import run_weekly_owner_updates
        from agents.ghost.smtp_email import transport_status
        mp.setenv('AUTUMBRA_SMTP_HOST', 'smtp.example.test')
        mp.setenv('AUTUMBRA_SMTP_FROM', 'autumbra@example.test')
        letters = []
        async def send(self, letter):
            letters.append(letter)
        mp.setattr(SmtpMailer, 'send', send)
        assert transport_status() == 'smtp'
        if ident == 'A52':
            cfg = ClientAutumbraSettings(tenant_id=A, site_name='tervory.com', owner_email='owner@example.test')
            first = await asyncio.to_thread(run_weekly_owner_updates, [cfg], receipts_by_tenant={A: []})
            second = await asyncio.to_thread(run_weekly_owner_updates, [cfg], receipts_by_tenant={A: []})
            assert first[0]['sent'] and not second[0]['sent'] and 'Quiet week.' in letters[0]['text']
        else:
            _, _, drain = await engine(box)
            await enqueue(box)
            assert (await drain())['applied']
            await deliver_act_owner_updates(app)
            await deliver_act_owner_updates(app)
        assert len(letters) == 1 and letters[0]['to'] == 'owner@example.test'
    elif ident == 'A43':
        _, data = await request(box, 'GET', '/ghost/autumbra/jobs')
        assert any(row['id'] == 'autumbra_weekly_owner_update' and row['cadence'] == 'weekly' for row in data['jobs'])
    elif ident in {'A44', 'A45'}:
        if ident == 'A44':
            _, a = await request(box, 'POST', '/ghost/autumbra/enforce/plan-create', {'tenant_id': A, 'existing_count': 0, 'execute': False})
            _, b = await request(box, 'POST', '/ghost/autumbra/enforce/plan-create', {'tenant_id': B, 'existing_count': 1, 'execute': False})
            assert a['plan']['project'] != b['plan']['project']
            assert a['plan']['isolation']['routes_to_queue_only'] is True
            assert a['plan']['volume'] != b['plan']['volume']
        else:
            response, data = await request(box, 'POST', '/ghost/autumbra/enforce/plan-destroy', {'tenant_id': A, 'execute': False})
            assert response.status_code == 200 and data['plan']['action'] == 'destroy_enforce' and data['receipt']['outcome'] == 'planned'
    elif ident == 'A46':
        body = {'exercise_id': 'credential_stuffing_fixture', 'target_site': 'coolify.tervory.com'}
        response, data = await request(box, 'POST', '/ghost/autumbra/exercises/run', body)
        assert response.status_code == 200 and data['kind'] == 'exercise'
        assert (await c.post('/ghost/autumbra/exercises/run', json={**body, 'target_site': 'evil.example'})).status_code == 403
    elif ident == 'A47':
        mp.setenv('AUTUMBRA_HEALTH_SECRET', 'fixture-health-key')
        mp.setattr(site_health, 'HEALTH_DIR', box.root)
        seen = []
        def health(request):
            seen.append(request)
            return httpx.Response(200)
        with httpx.Client(transport=httpx.MockTransport(health), follow_redirects=False) as http:
            result = site_health.observe_once(http, 'tervory.com')
        assert result['status'] == 200 and seen[0].method == 'GET' and not seen[0].content and 'cookie' not in seen[0].headers
        signature = hmac.new(b'fixture-health-key', site_health.canonical(result), hashlib.sha256).hexdigest()
        path = box.root / 'tervory.com.json'
        path.write_text(json.dumps({'result': result, 'signature': signature}))
        assert site_health.read_health('tervory.com') is True
        path.write_text(json.dumps({'result': result, 'signature': 'forged'}))
        assert site_health.read_health('tervory.com') is False
    elif ident == 'A54':
        from agents.ghost.durable_shields import load_control
        api, _, drain = await engine(box)
        await enqueue(box)
        receipt = await drain()
        restored = load_control(box.root / 'enforce', tenant_id=A)
        assert restored.blocked[receipt['undo']['rule_id']]['control'] == 'cloudflare'
        replacement = CloudflareEdgeControl(tenant_id=A, site='tervory.com', transport=httpx.MockTransport(api))
        replacement.blocked.update(restored.blocked)
        drain.app.state.control = replacement
        await request(box, 'POST', '/ghost/autumbra/queue/undo', {'tenant_id': A, 'site': 'tervory.com',
                      'prior_receipt_id': receipt['id'], 'rule_id': receipt['undo']['rule_id']})
        assert (await drain())['outcome'] == 'undone' and len(api.rules) == 1
    elif ident == 'A55':
        await settings(box)
        _, data = await enqueue(box, address='104.16.1.1', raw_log='test from 104.16.1.1')
        assert data['queued'] is False
    elif ident == 'A56':
        await settings(box, site_name='client.example', watched_hosts=['client.example'])
        body = {'tenant_id': A, 'exercise_id': 'path_scan_fixture', 'target_site': 'client.example'}
        assert (await c.post('/ghost/autumbra/exercises/run', json=body)).status_code == 403
        await settings(box, site_name='client.example', watched_hosts=['client.example'], red_team_permission=True)
        assert (await c.post('/ghost/autumbra/exercises/run', json=body)).json()['kind'] == 'exercise'
    elif ident in {'A57', 'A58', 'A59'}:
        token = sign_undo_token(tenant_id=A, receipt_id=A, rule_id='c'*32, site='tervory.com') if ident == 'A59' else ''
        assert node_public_path(ident, token)['ok'] is True
    elif ident == 'A60':
        from agents.ghost.threat_payload import accept_threat_payload
        api, queue, drain = await engine(box, kind='rate_limit', plan='free')
        queue.put(accept_threat_payload({'schema_version': 'ghost.threat.v1', 'action': 'propose_shield',
                  'site': 'tervory.com', 'tenant_id': A, 'kind': 'rate_limit', 'path': '/autumbra-check',
                  'reason': 'bounded rate event', 'confidence': 0.9}))
        result = await drain()
        assert result['outcome'] == 'refused_plan' and result['cloudflare_plan'] == 'free' and not result['applied']
        assert all(method == 'GET' for method, _ in api.calls)
    elif ident in {'P01', 'P02', 'P03', 'P06'}:
        response = await c.request('POST' if ident == 'P06' else 'GET', row[1], json={})
        assert response.status_code == (422 if ident == 'P06' else 404)
        if ident == 'P06':
            assert response.json()['detail'] == 'Google connection was not understood.'
    elif ident in {'P04', 'P05', 'P07', 'P08', 'P09', 'P10', 'P11'}:
        from fastapi import FastAPI
        if ident != 'P05' and ident != 'P11':
            from ghost_routes import router
        else:
            from vault_routes import build_router
            router = build_router(SimpleNamespace())
        app = FastAPI()
        app.include_router(router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank:8000') as client:
            assert (await client.request('GET' if ident == 'P11' else 'POST', row[1], json={})).status_code == ({'P05': 401, 'P11': 422}.get(ident, 404))
    else:
        raise AssertionError('Row has no executable path: ' + ident)


def test_sheet_has_exactly_one_fixture_case_per_row():
    sheet = (ROOT / 'docs/acceptance/autumbra.md').read_text()
    assert re.findall(r'^\| (A\d\d|P\d\d) \|', sheet, flags=re.M) == [row[0] for row in ROWS]


def node_public_path(ident, token):
    """Run the actual Next page/handler with fixture external boundaries, not HTML copies."""
    script = r"""
const fs=require('fs'),path=require('path'),Module=require('module'),{createRequire}=require('module');
const root=process.argv[1],id=process.argv[2],token=process.argv[3];
const req=createRequire(path.join(root,'workspace/package.json')),ts=req('typescript'),assert=require('assert/strict');
for(const ext of ['.ts','.tsx']) require.extensions[ext]=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText,f);
const original=Module._load;
Module._load=function(name,parent,main){
 if(id==='A58' && name==='@/lib/autumbra-receipts-access') return {mayReadWeeklyReceipts:async()=>false};
 if(id==='A58' && name==='@/lib/autumbra-weekly') return {loadWeeklyReceipts:async()=>{throw Error('unauthorized read');}};
 if(name.startsWith('@/')) return original.call(this,path.join(root,'workspace',name.slice(2)),parent,main);
 return original.call(this,name,parent,main);
};
process.env.AUTUMBRA_UNDO_TOKEN_SECRET='fixture-undo-key';process.env.TANK_API_KEY='placeholder-workspace-key';process.env.TANK_URL='http://tank:8000';
(async()=>{
 if(id==='A58'){
  const page=require(path.join(root,'workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx')).default;
  const html=req('react-dom/server').renderToStaticMarkup(await page({params:Promise.resolve({tenant:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}),searchParams:Promise.resolve({token:'expired'})}));
  assert(html.includes('Your Autumbra weekly update'));assert(html.includes('This link is invalid or has expired.'));assert(!html.includes('<li'));
 }else{
  let calls=0;
  global.fetch=async(url,opts)=>{calls++;assert.equal(url,'http://tank:8000/v1/ghost/autumbra/queue/undo');
    const body=JSON.parse(opts.body);assert.equal(body.tenant_id,'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');
    assert.equal(body.prior_receipt_id,body.tenant_id);assert.equal(body.rule_id,'c'.repeat(32));
    return new Response(JSON.stringify({queued:true}),{status:200});};
  const route=require(path.join(root,'workspace/app/api/autumbra/undo/route.ts'));
  const response=await route.POST(new Request('https://app.tervory.com/api/autumbra/undo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(token?{token,tenant_id:'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'}:{})}));
  const body=await response.json();
  if(id==='A57'){assert.equal(response.status,401);assert.equal(body.detail,'This undo link is invalid or has expired.');assert.equal(calls,0);}
  else{assert.equal(response.status,200);assert.equal(body.ok,true);assert.equal(body.queued,true);assert.equal(calls,1);}
 }
 console.log(JSON.stringify({ok:true}));
})().catch(e=>{console.error(e);process.exit(1);});
"""
    result = subprocess.run(['node', '-e', script, str(ROOT), ident, token], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
