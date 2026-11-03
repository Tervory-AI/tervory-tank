"""Real HTTPS health observation after a confirmed edge write; no live network."""
import json

import httpx
import pytest
from test_autumbra_cloudflare_hand import TENANT, FakeCloudflare, edge, payload

from agents.ghost import site_health as health
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
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
    if status != 200:
        assert receipt['outcome'] == 'auto_undone_health_failed' and receipt['applied'] is False
        assert len(api.rules) == 1 and api.rules[0]["ref"] == "somebody-else"
    else:
        assert receipt['applied'] is True and api.rules
    assert queue.list_receipts()[0] == receipt


@pytest.mark.parametrize('url', ['http://tervory.com/health', 'https://other.example/health',
                               'https://user@tervory.com/health', 'https://tervory.com/?token=x'])
def test_client_health_url_cannot_expand_egress(url, monkeypatch):
    monkeypatch.setenv('AUTUMBRA_HEALTH_URL', url)
    with pytest.raises(ValueError):
        health.health_url('tervory.com')




def test_health_receipt_keeps_exact_sample_used_for_undo(monkeypatch):
    import time

    from agents.ghost.enforce_apply import _health_after_apply
    sample = {'site': 'tervory.com', 'url': 'https://tervory.com/', 'ok': False,
              'status': 503, 'ms': 2.0, 'checked_at': time.time()}
    reads = []
    def result(site):
        reads.append(site)
        # A later observer sample must not replace the failed sample in a receipt.
        return sample if len(reads) == 1 else {**sample, 'ok': True, 'status': 200}
    monkeypatch.setattr(health, '_read_result', result)
    control = edge(FakeCloudflare('block_ip'))
    captured = {}
    control.last_health_result = captured
    control._fresh_health_probe = lambda after: health.read_health('tervory.com', after=after, result_out=captured)
    assert _health_after_apply(control, {'applied_at': sample['checked_at'] - 1}) is False
    assert control.last_health_result == sample
    assert reads == ['tervory.com']
