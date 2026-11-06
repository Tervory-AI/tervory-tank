from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import time

import pytest

from agents.ghost import red_team, webhooks
from agents.ghost.client_settings import ClientAutumbraSettings


@pytest.mark.parametrize("exercise", ["forged_webhook_fixture", "path_scan_fixture", "outdated_package_fixture"])
def test_exercises_execute_checks_without_network_or_persisting_fixture_data(exercise):
    result = red_team.run_exercise(exercise, target_site="tervory.com")
    assert result["kind"] == "exercise"
    assert result["result"] in {"ran", "expected_drop"}
    assert result["checks"] and all(result["checks"].values())
    assert "raw_log" not in result


def test_exercise_detects_broken_signature_gate(monkeypatch):
    monkeypatch.setattr(webhooks, "signature_matches", lambda **kw: True)
    result = red_team.run_exercise("forged_webhook_fixture", target_site="tervory.com")
    assert result["result"] == "failed"
    assert result["checks"]["signature_rejected"] is False


def test_permission_without_bound_client_site_cannot_authorize_exercise():
    settings = ClientAutumbraSettings(tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", red_team_permission=True)
    with pytest.raises(PermissionError):
        red_team.run_exercise("path_scan_fixture", target_site="unrelated.example", settings=settings)


def test_concurrent_signed_replay_is_accepted_only_once(monkeypatch):
    webhooks.reset_drop_counts()
    secret, body, stamp, nonce = "exercise-key", b"{}", str(int(time.time())), "concurrent"
    original = webhooks.sign_body
    signature = original(secret=secret, body=body, timestamp=stamp, nonce=nonce)
    barrier = Barrier(2)

    def synchronized(**kwargs):
        barrier.wait(timeout=5)
        return original(**kwargs)

    monkeypatch.setattr(webhooks, "sign_body", synchronized)

    def attempt(_):
        try:
            webhooks._verify(body, secret=secret, timestamp=stamp, nonce=nonce, signature=signature, bucket="edge")
            return True
        except webhooks.WebhookRejected:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(attempt, range(2))) == [False, True]
    assert webhooks.drop_counts()["replay"] == 1
    webhooks.reset_drop_counts()
