"""Rulesets API contract and sealed Enforce integration. No real network transport."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from agents.ghost.cloudflare_edge import CloudflareEdgeControl, CloudflareEdgeError
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.durable_shields import load_control, load_pending
from agents.ghost.enforce_apply import apply_from_payload, approve_pending, select_control, undo_from_payload
from agents.ghost.fixture_edge import FixtureEdgeControl
from agents.ghost.threat_payload import accept_threat_payload

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ZONE, RULESET, RULE, OTHER = "a" * 32, "b" * 32, "c" * 32, "d" * 32
REF = "enforce-" + "e" * 16


class FakeCloudflare:
    """Checks the exact wire contract and keeps an unrelated rule for Undo proof."""

    def __init__(self, kind="rate_limit", missing=False):
        self.kind, self.missing = kind, missing
        self.calls = []
        self.rules = [{"id": OTHER, "ref": "somebody-else", "expression": "true"}]

    def __call__(self, request):
        assert request.url.scheme == "https"
        assert request.url.host == "api.cloudflare.com"
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        base = f"/client/v4/zones/{ZONE}/rulesets"
        if method == "GET" and path == "/client/v4/zones":
            assert request.url.params == httpx.QueryParams({"name": "tervory.com"})
            result = [{"name": "tervory.com", "id": ZONE}]
        elif method == "GET" and "/phases/" in path:
            phase = "http_ratelimit" if self.kind == "rate_limit" else "http_request_firewall_custom"
            assert path == base + f"/phases/{phase}/entrypoint"
            if self.missing:
                return httpx.Response(404, json={"success": False, "result": None})
            result = {"id": RULESET, "rules": self.rules}
        elif method == "POST":
            body = json.loads(request.content)
            if self.missing:
                assert path == base
                assert set(body) == {"name", "kind", "phase", "rules"}
                phase = "http_ratelimit" if self.kind == "rate_limit" else "http_request_firewall_custom"
                assert body["name"] == "Autumbra " + phase
                assert body["kind"] == "zone" and body["phase"] == phase
                assert len(body["rules"]) == 1
                body = body["rules"][0]
            else:
                assert path == base + f"/{RULESET}/rules"
            ref = body["ref"]
            expected = {"ref": ref, "description": "Autumbra shield " + ref, "enabled": True,
                        "action": "block"}
            if self.kind == "rate_limit":
                expected.update(
                    expression='(http.host eq "tervory.com" and starts_with(http.request.uri.path, "/autumbra-check"))',
                    ratelimit={"characteristics": ["cf.colo.id", "ip.src"], "period": 10,
                               "requests_per_period": 20, "mitigation_timeout": 10},
                )
            else:
                expected["expression"] = '(http.host eq "tervory.com" and ip.src eq 198.51.100.20)'
            assert body == expected
            self.rules.append({**body, "id": RULE})
            result = {"id": RULESET, "rules": self.rules}
        elif method == "GET" and path == base + f"/{RULESET}":
            assert not request.content
            result = {"id": RULESET, "rules": self.rules}
        elif method == "DELETE":
            assert path == base + f"/{RULESET}/rules/{RULE}"
            assert not request.content
            self.rules = [r for r in self.rules if r["id"] != RULE]
            result = {"id": RULESET, "rules": self.rules}
        else:
            pytest.fail(f"Unexpected Cloudflare request: {method} {path}")
        return httpx.Response(200, json={"success": True, "result": result})


def edge(api, health=lambda: True):
    return CloudflareEdgeControl(tenant_id=TENANT, site="tervory.com",
                                 transport=httpx.MockTransport(api), health_probe=health)


def settings(mode=ApplyMode.auto_when_checks_pass):
    return ClientAutumbraSettings(tenant_id=TENANT, site_name="tervory.com", shield_mode=mode)


def payload(kind="rate_limit", **extra):
    raw = {"schema_version": "ghost.threat.v1", "action": "propose_shield", "site": "tervory.com",
           "kind": kind, "reason": "own site check", "tenant_id": TENANT}
    raw.update({"path": "/autumbra-check"} if kind == "rate_limit" else {"address": "198.51.100.20"})
    return accept_threat_payload({**raw, **extra})


def undo_payload(receipt):
    return accept_threat_payload({"schema_version": "ghost.threat.v1", "action": "undo_shield",
                                 "site": "tervory.com", "tenant_id": TENANT,
                                 "rule_id": receipt["undo"]["rule_id"],
                                 "prior_receipt_id": receipt["id"]})


@pytest.mark.parametrize("kind", ["rate_limit", "block_ip"])
@pytest.mark.parametrize("missing", [False, True])
def test_apply_and_exact_owned_rule_undo(kind, missing):
    api = FakeCloudflare(kind, missing)
    control = edge(api)
    if kind == "rate_limit":
        row = control.apply_rate_limit(site="tervory.com", path="/autumbra-check", ref=REF)
    else:
        row = control.apply_block_ip(site="tervory.com", address="198.51.100.20", ref=REF)
    assert row["rule_id"] == RULE and control.health_check() is True
    control.undo(RULE)
    assert control.list_blocked() == []
    assert [r["id"] for r in api.rules] == [OTHER]
    before = list(api.calls)
    with pytest.raises(LookupError):
        control.undo(OTHER)
    assert api.calls == before
    control.close()


@pytest.mark.parametrize("site", ["example.com", "tervory.com.evil.com", "eviltervory.com", "tervory.com:443",
                                   "https://tervory.com", "tervory.com/", "bad..tervory.com"])
def test_other_zone_refused_before_request(site):
    with pytest.raises(ValueError):
        CloudflareEdgeControl(tenant_id=TENANT, site=site,
                              transport=httpx.MockTransport(lambda _: pytest.fail("network attempted")))


def test_control_cannot_apply_to_another_site_or_inject_expression():
    api = FakeCloudflare()
    control = edge(api)
    with pytest.raises(ValueError):
        control.apply_rate_limit(site="app.tervory.com", path="/autumbra-check", ref=REF)
    with pytest.raises(ValueError):
        control.apply_rate_limit(site="tervory.com", path='/x") or true', ref=REF)
    with pytest.raises(ValueError):
        control.apply_block_ip(site="tervory.com", address="1.2.3.4 or true", ref=REF)
    assert api.calls == []


def test_non_mock_transport_is_sealed():
    with httpx.HTTPTransport() as transport:
        with pytest.raises(CloudflareEdgeError, match="egress is not approved"):
            CloudflareEdgeControl(tenant_id=TENANT, site="tervory.com", transport=transport)


@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize("site", ["tervory.com", "example.com"])
def test_runtime_stays_fixture_without_approved_egress(monkeypatch, configured, site):
    # This is a dummy marker, never a credential; no value is read from the host.
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN_ENFORCE", "offline-test-marker" if configured else "")
    monkeypatch.setattr(httpx.Client, "request", lambda *a, **k: pytest.fail("real network attempted"))
    fixture = FixtureEdgeControl(tenant_id=TENANT)
    assert select_control(site=site, settings=settings(), control=fixture) is fixture
    receipt = apply_from_payload(payload("block_ip"), settings=settings(), control=fixture)
    assert receipt["control"] == "fixture_edge" and receipt["applied"] is True
    assert "offline-test-marker" not in json.dumps(receipt)


@pytest.mark.parametrize("kind", ["rate_limit", "block_ip"])
def test_enforce_payload_apply_durable_restore_and_undo(kind, tmp_path):
    api = FakeCloudflare(kind)
    control = edge(api)
    receipt = apply_from_payload(payload(kind), settings=settings(), control=control, data_dir=tmp_path)
    assert receipt["control"] == receipt["undo"]["control"] == "cloudflare"
    assert receipt["applied"] is True and receipt["raw_log_seen"] is False
    restored = load_control(tmp_path, tenant_id=TENANT)
    fresh = edge(api)
    fresh.blocked.update(restored.blocked)
    undone = undo_from_payload(undo_payload(receipt), settings=settings(), control=fresh, data_dir=tmp_path)
    assert undone["outcome"] == "undone" and undone["control"] == "cloudflare"
    assert load_control(tmp_path, tenant_id=TENANT).list_blocked() == []
    assert [r["id"] for r in api.rules] == [OTHER]


@pytest.mark.parametrize("kind", ["rate_limit", "block_ip"])
def test_approval_and_report_only_do_not_write_until_approved(kind, tmp_path):
    api = FakeCloudflare(kind)
    control = edge(api)
    report = apply_from_payload(payload(kind), settings=settings(ApplyMode.never), control=control)
    assert report["outcome"] == "report_only" and not api.calls
    pending = apply_from_payload(payload(kind), settings=settings(ApplyMode.approve_each),
                                 control=control, data_dir=tmp_path)
    assert pending["outcome"] == "awaiting_approval" and not api.calls
    approval = accept_threat_payload({"schema_version": "ghost.threat.v1", "action": "approve_shield",
                                     "site": "tervory.com", "tenant_id": TENANT,
                                     "prior_receipt_id": pending["id"]})
    receipt = approve_pending(approval, settings=settings(), control=control, data_dir=tmp_path)
    assert receipt["applied"] is True and receipt["control"] == "cloudflare"
    assert load_pending(tmp_path) == {}


@pytest.mark.parametrize("probe", [None, lambda: False])
def test_missing_or_failed_health_automatically_undoes(probe, tmp_path):
    api = FakeCloudflare()
    control = edge(api, health=probe)
    receipt = apply_from_payload(payload(), settings=settings(), control=control, data_dir=tmp_path)
    assert receipt["outcome"] == "auto_undone_health_failed"
    assert receipt["health_ok"] is False and receipt["applied"] is False
    assert receipt["auto_undo"]["control"] == "cloudflare"
    assert [r["id"] for r in api.rules] == [OTHER]


def test_undo_refuses_changed_ownership():
    api = FakeCloudflare()
    control = edge(api)
    control.apply_rate_limit(site="tervory.com", path="/autumbra-check", ref=REF)
    api.rules[-1]["ref"] = "somebody-else"
    with pytest.raises(CloudflareEdgeError, match="ownership"):
        control.undo(RULE)
    assert not any(method == "DELETE" for method, _ in api.calls)
    assert control.list_blocked()


@pytest.mark.parametrize("response", [httpx.Response(403, json={"errors": ["not exposed"]}),
                                       httpx.Response(200, json={"success": False, "result": None}),
                                       httpx.Response(302, headers={"Location": "https://example.com"}),
                                       httpx.Response(200, text="not json")])
def test_api_errors_are_fixed_and_redirects_not_followed(response):
    calls = []
    def handler(request):
        calls.append(request)
        return response
    control = edge(handler)
    with pytest.raises(CloudflareEdgeError, match="^Cloudflare request failed.$") as exc:
        control.apply_rate_limit(site="tervory.com", path="/autumbra-check", ref=REF)
    assert "not exposed" not in str(exc.value) and len(calls) == 1
    assert not control.list_blocked()


def test_raw_input_never_reaches_control_and_never_block_is_preserved():
    api = FakeCloudflare("block_ip")
    control = edge(api)
    with pytest.raises(TypeError):
        apply_from_payload({"raw_log": "dirty input"}, settings=settings(), control=control)
    cfg = settings()
    cfg.own_cidrs = ["198.51.100.0/24"]
    receipt = apply_from_payload(payload("block_ip"), settings=cfg, control=control)
    assert receipt["outcome"] == "refused_never_block" and not api.calls


def test_other_tenant_cannot_use_cloudflare_control():
    api = FakeCloudflare()
    other = ClientAutumbraSettings(tenant_id="another-tenant")
    with pytest.raises(ValueError, match="client and site"):
        apply_from_payload(payload(), settings=other, control=edge(api))
    assert not api.calls


def test_fixture_cannot_claim_to_undo_a_persisted_cloudflare_rule(tmp_path):
    api = FakeCloudflare()
    receipt = apply_from_payload(payload(), settings=settings(), control=edge(api), data_dir=tmp_path)
    fixture = load_control(tmp_path, tenant_id=TENANT)
    undone = undo_from_payload(undo_payload(receipt), settings=settings(), control=fixture, data_dir=tmp_path)
    assert undone["outcome"] == "undo_failed" and fixture.list_blocked()
    assert not any(method == "DELETE" for method, _ in api.calls)


def test_watch_has_no_credential_read_or_cloudflare_import():
    root = Path(__file__).resolve().parents[1] / "agents/ghost"
    for name in ("app.py", "shields.py", "webhooks.py", "threat_payload.py"):
        text = (root / name).read_text()
        assert "CLOUDFLARE_API_TOKEN_ENFORCE" not in text
        assert "import CloudflareEdgeControl" not in text
