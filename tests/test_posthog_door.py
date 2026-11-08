"""Offline contract tests for Tank PostHog door (no live PostHog calls)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))

from posthog_door import (
    API_KEY_NAME,
    ALLOWED_EVENT_NAMES,
    FakePosthogProvider,
    PosthogError,
    PosthogNotConfigured,
    capture_event,
    credentials_present,
    opaque_distinct_id,
    sanitize_properties,
    status_payload,
)


TENANT = "11111111-1111-1111-1111-111111111111"
USER = "user_alice"


def test_fail_closed_without_key(monkeypatch):
    monkeypatch.delenv(API_KEY_NAME, raising=False)
    assert credentials_present() is False
    status = status_payload({})
    assert status["configured"] is False
    assert API_KEY_NAME in status["required_secrets"]


def test_opaque_distinct_id_stable_and_not_raw():
    a = opaque_distinct_id(TENANT, USER)
    b = opaque_distinct_id(TENANT, USER)
    assert a == b
    assert TENANT not in a
    assert USER not in a
    assert a.startswith("ph_")


def test_sanitize_drops_pii_and_unknown_keys():
    cleaned = sanitize_properties(
        {
            "outcome": "ok",
            "email": "a@b.com",
            "name": "Alice",
            "error_code": "not_found",
            "secret_token": "x" * 50,
            "playback_policy": "signed",
        }
    )
    assert cleaned["outcome"] == "ok"
    assert cleaned["error_code"] == "not_found"
    assert cleaned["playback_policy"] == "signed"
    assert "email" not in cleaned
    assert "name" not in cleaned
    assert "secret_token" not in cleaned
    assert cleaned["product"] == "tank"


@pytest.mark.asyncio
async def test_capture_allowlist_and_fake_provider():
    fake = FakePosthogProvider()
    with pytest.raises(PosthogError) as bad:
        await capture_event(
            event="not.an.allowed.event",
            tenant_id=TENANT,
            user_id=USER,
            provider=fake,
        )
    assert bad.value.code == "event_not_allowed"
    result = await capture_event(
        event="tank.media.upload_created",
        tenant_id=TENANT,
        user_id=USER,
        properties={"outcome": "ok", "email": "leak@example.com", "test": True},
        provider=fake,
        environ={},
    )
    assert result["ok"] is True
    assert len(fake.events) == 1
    assert fake.events[0]["event"] == "tank.media.upload_created"
    assert "email" not in fake.events[0]["properties"]
    assert fake.events[0]["properties"]["test"] is True
    assert fake.events[0]["distinct_id"].startswith("ph_")


@pytest.mark.asyncio
async def test_require_configured_raises():
    with pytest.raises(PosthogNotConfigured):
        await capture_event(
            event="tank.health.posthog_probe",
            tenant_id=TENANT,
            user_id=USER,
            environ={},
            require_configured=True,
        )


def test_compose_passthrough_names_documented():
    compose = (ROOT / "docker-compose.yml").read_text()
    za = (ROOT / "docker-compose.za.yml").read_text()
    for text in (compose, za):
        assert "POSTHOG_PROJECT_API_KEY: ${POSTHOG_PROJECT_API_KEY:-}" in text
        assert "POSTHOG_HOST: ${POSTHOG_HOST:-}" in text
    hermes = compose.split("\n  hermes:\n", 1)[1].split("\n  local-model", 1)[0]
    assert "POSTHOG_" not in hermes
    assert "tank.media.upload_created" in ALLOWED_EVENT_NAMES
