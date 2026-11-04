"""Provider connect, post-write HTTPS health and real-adapter receipt contracts."""
import json

import httpx
import pytest
from test_autumbra_cloudflare_hand import TENANT, FakeCloudflare, edge, payload

from agents.ghost import site_health as health
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.speed_budgets import stamp_budget
from agents.ghost.threat_queue import ThreatPayloadQueue, enforce_drain_once


@pytest.mark.parametrize('status', [200, 302, 503])
def test_real_adapter_post_shield_get_records_probe_and_undo(status, monkeypatch, tmp_path):
    import hashlib
    import hmac
    monkeypatch.setenv('AUTUMBRA_HEALTH_URL', 'https://tervory.com/autumbra-health')
    monkeypatch.setenv(health.SECRET_ENV, 'placeholder-health-signing')
    monkeypatch.setattr(health, 'HEALTH_DIR', tmp_path)
    requests = []
    def get_health(request):
        requests.append(request)
        assert request.method == 'GET' and str(request.url) == 'https://tervory.com/autumbra-health'
        assert request.content == b'' and 'Authorization' not in request.headers
        return httpx.Response(status, headers={'Location': 'https://other.example/private'})
    api = FakeCloudflare('block_ip')
    control = edge(api)
    def post_write(after):
        assert api.rules  # The HTTPS GET must follow the confirmed write.
        with httpx.Client(transport=httpx.MockTransport(get_health), follow_redirects=False) as client:
            result = health.observe_once(client, 'tervory.com')
        assert result['checked_at'] > after
        signature = hmac.new(b'placeholder-health-signing', health.canonical(result), hashlib.sha256).hexdigest()
        (tmp_path / 'tervory.com.json').write_text(json.dumps({'result': result, 'signature': signature}))
        return health.read_health('tervory.com', after=after)
    control._fresh_health_probe = post_write
    queue = ThreatPayloadQueue(tmp_path / 'queue')
    queue.put(payload('block_ip'))
    settings = ClientAutumbraSettings(tenant_id=TENANT, shield_mode=ApplyMode.auto_when_checks_pass)
    receipt = enforce_drain_once(queue, settings=settings, control=control, data_dir=tmp_path)
    assert len(requests) == 1
    assert receipt['health_probe']['status'] == status
    assert receipt['health_probe']['url'] == 'https://tervory.com/autumbra-health'
    assert receipt['health_ok'] is (status == 200)
    assert receipt['measurement_path'] == 'real_edge'
    assert len(receipt['edge_requests']) >= 3
    assert all(row['seconds'] >= 0 and row['status'] == 200 for row in receipt['edge_requests'])
    assert receipt['budgets']['event_to_shield_e2e']['seconds'] >= receipt['budgets']['decision_to_shield']['seconds']
    assert receipt['budgets']['health_check']['within_budget'] is True
    assert receipt['speed_budget_summary']['health_check']['status'] == 'passed'
    if status != 200:
        assert receipt['outcome'] == 'auto_undone_health_failed' and receipt['applied'] is False
        assert len(api.rules) == 1 and api.rules[0]["ref"] == "somebody-else"
        assert any(row['method'] == 'DELETE' for row in receipt['auto_undo']['edge_requests'])
    else:
        assert receipt['applied'] is True and api.rules
    assert queue.list_receipts()[0] == receipt


@pytest.mark.parametrize('url', ['http://tervory.com/health', 'https://other.example/health',
                               'https://user@tervory.com/health', 'https://tervory.com/?token=x'])
def test_client_health_url_cannot_expand_egress(url, monkeypatch):
    monkeypatch.setenv('AUTUMBRA_HEALTH_URL', url)
    with pytest.raises(ValueError):
        health.health_url('tervory.com')


def test_every_receipt_has_budget_status_and_slow_stages_are_not_hidden(tmp_path):
    queue = ThreatPayloadQueue(tmp_path)
    refused = {'id': 'placeholder-refused', 'outcome': 'refused', 'applied': False}
    queue.write_receipt(refused)
    assert all(row['status'] == 'not_run' for row in refused['speed_budget_summary'].values())
    slow = {'id': 'placeholder-slow', 'control': 'cloudflare'}
    stamp_budget(slow, stage='decision_to_shield', seconds=12.5)
    queue.write_receipt(slow)
    assert slow['budgets']['decision_to_shield']['within_budget'] is False
    assert slow['speed_budget_summary']['decision_to_shield']['status'] == 'exceeded'


def test_failed_real_edge_attempt_keeps_measured_receipt(tmp_path):
    from agents.ghost.cloudflare_edge import CloudflareEdgeError
    def unavailable(request):
        raise httpx.ConnectError('private transport detail', request=request)
    control = edge(unavailable)
    queue = ThreatPayloadQueue(tmp_path / 'queue')
    queue.put(payload('block_ip'))
    settings = ClientAutumbraSettings(tenant_id=TENANT, shield_mode=ApplyMode.auto_when_checks_pass)
    with pytest.raises(CloudflareEdgeError):
        enforce_drain_once(queue, settings=settings, control=control, data_dir=tmp_path)
    receipt = queue.list_receipts()[0]
    assert receipt['outcome'] == 'edge_unconfirmed' and receipt['edge_state'] == 'unconfirmed'
    assert receipt['measurement_path'] == 'real_edge'
    assert receipt['edge_requests'][0]['status'] is None
    assert receipt['budgets']['edge_attempt']['seconds'] >= 0
    assert 'private transport detail' not in json.dumps(receipt)
