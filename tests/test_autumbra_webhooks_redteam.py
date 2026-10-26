"""Signed webhooks and red-team exercises."""
import hashlib
import hmac
import time

import pytest

from agents.ghost.client_settings import ClientAutumbraSettings
from agents.ghost.red_team import list_exercises, run_exercise, run_own_sites_exercise_pass, OWN_SITES
from agents.ghost.webhooks import (
    CF_SECRET_ENV,
    WebhookRejected,
    accept_signed,
    drop_counts,
    reset_drop_counts,
)


def test_unsigned_webhook_dropped_never_stored(monkeypatch):
    reset_drop_counts()
    monkeypatch.setenv(CF_SECRET_ENV, "test-secret")
    with pytest.raises(WebhookRejected):
        accept_signed("cloudflare", b'{"event":1}', signature=None)
    assert drop_counts()["cloudflare"] >= 1


def test_signed_webhook_accepted_not_stored(monkeypatch):
    reset_drop_counts()
    secret = "test-secret"
    monkeypatch.setenv(CF_SECRET_ENV, secret)
    body = b'{"event":"waf"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    envelope = accept_signed("cloudflare", body, signature=sig, timestamp=str(int(time.time())))
    assert envelope["accepted"] is True and envelope["stored"] is False


def test_red_team_own_sites_and_permission():
    exercises = list_exercises()
    assert any(e["id"] == "forged_webhook_fixture" for e in exercises)
    receipt = run_exercise(
        "credential_stuffing_fixture",
        target_site="coolify.tervory.com",
        fixture_log="stuffing from 203.0.113.9 against /login",
    )
    assert receipt["kind"] == "exercise"
    assert receipt["addresses_seen"] == ["203.0.113.9"]
    with pytest.raises(PermissionError):
        run_exercise("path_scan_fixture", target_site="evil.example")
    # Client with written permission + matching site.
    settings = ClientAutumbraSettings(
        tenant_id="00000000-0000-0000-0000-0000000000ee",
        site_name="client.example",
        red_team_permission=True,
    )
    ok = run_exercise("path_scan_fixture", target_site="client.example", settings=settings)
    assert ok["kind"] == "exercise"


def test_own_sites_exercise_pass_receipts_marked_exercise():
    receipts = run_own_sites_exercise_pass()
    assert len(receipts) == len(OWN_SITES)
    assert {r["target_site"] for r in receipts} == set(OWN_SITES)
    assert all(r["kind"] == "exercise" for r in receipts)
