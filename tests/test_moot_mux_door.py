"""Offline contract tests for Tank-controlled Moot Mux door (no live Mux, no paid calls)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))

from moot_media import (  # noqa: E402
    MootActor,
    create_upload,
    handle_media_request,
    match_media_path,
    playback_access,
    upload_status,
)
from moot_media_store import MemoryOwnershipStore  # noqa: E402
from moot_mux import (  # noqa: E402
    PLAYBACK_POLICY,
    FakeMuxProvider,
    MuxNotConfigured,
    SignedPlaybackUnconfigured,
    credentials_from_env,
    credentials_present,
    signing_configured,
)


TENANT = "11111111-1111-1111-1111-111111111111"
USER = "user_alice"
OTHER = "user_bob"
HEARING = "22222222-2222-2222-2222-222222222222"


async def allow(_t, _u, _h):
    return True


async def deny(_t, _u, _h):
    return False


def test_credentials_presence_and_fail_closed(monkeypatch):
    monkeypatch.delenv("MOOT_MUX_TOKEN_ID", raising=False)
    monkeypatch.delenv("MOOT_MUX_TOKEN_SECRET", raising=False)
    assert credentials_present() is False
    with pytest.raises(MuxNotConfigured):
        credentials_from_env()
    monkeypatch.setenv("MOOT_MUX_TOKEN_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("MOOT_MUX_TOKEN_SECRET", "x" * 48)
    assert credentials_present() is True
    tid, sec = credentials_from_env()
    assert tid.endswith("0001")
    assert len(sec) == 48
    assert signing_configured() is False


def test_match_media_path_shapes():
    assert match_media_path(f"moot/hearings/{HEARING}/media/uploads") == {
        "hearing_id": HEARING, "kind": "uploads", "resource_id": "",
    }
    assert match_media_path(f"moot/hearings/{HEARING}/media/uploads/upload_abc")["resource_id"] == "upload_abc"
    assert match_media_path(f"moot/hearings/{HEARING}/media/assets") is None
    assert match_media_path("moot/hearings") is None


@pytest.mark.asyncio
async def test_create_upload_signed_only_and_isolated():
    provider = FakeMuxProvider()
    store = MemoryOwnershipStore()
    actor = MootActor(TENANT, USER)
    created = await create_upload(
        actor=actor,
        hearing_id=HEARING,
        cors_origin="https://zenas.tervory.com",
        provider=provider,
        store=store,
        hearing_allowed=allow,
        test=True,
    )
    assert created["playback_policy"] == PLAYBACK_POLICY
    assert created["upload_id"]
    assert created["upload_url"].startswith("https://")
    assert "stream.mux.com" not in created["upload_url"]

    # Hearing gate denial
    with pytest.raises(Exception) as denied:
        await create_upload(
            actor=actor,
            hearing_id=HEARING,
            cors_origin="https://zenas.tervory.com",
            provider=provider,
            store=store,
            hearing_allowed=deny,
        )
    assert denied.value.code == "not_found"

    # Cross-user isolation on status
    provider.complete_upload(created["upload_id"])
    status = await upload_status(
        actor=actor, hearing_id=HEARING, upload_id=created["upload_id"],
        provider=provider, store=store,
    )
    assert status["status"] == "asset_created"
    assert status["asset_id"]

    other = MootActor(TENANT, OTHER)
    with pytest.raises(Exception) as cross:
        await upload_status(
            actor=other, hearing_id=HEARING, upload_id=created["upload_id"],
            provider=provider, store=store,
        )
    assert cross.value.code == "not_found"

    # Playback fails closed without signing secrets
    record = await store.by_upload(created["upload_id"])
    assert record and record.playback_ids
    with pytest.raises(SignedPlaybackUnconfigured) as play:
        await playback_access(
            actor=actor,
            hearing_id=HEARING,
            playback_id=record.playback_ids[0],
            store=store,
            environ={},
        )
    assert play.value.required_names == (
        "MOOT_MUX_SIGNING_KEY_ID",
        "MOOT_MUX_SIGNING_PRIVATE_KEY",
    )


@pytest.mark.asyncio
async def test_handle_media_request_contract():
    provider = FakeMuxProvider()
    store = MemoryOwnershipStore()
    actor = MootActor(TENANT, USER)
    path = f"moot/hearings/{HEARING}/media/uploads"
    status, body = await handle_media_request(
        method="POST",
        path=path,
        actor=actor,
        body={"cors_origin": "https://zenas.tervory.com"},
        provider=provider,
        store=store,
        hearing_allowed=allow,
        allow_test_uploads=True,
    )
    assert status == 201
    assert body["playback_policy"] == "signed"
    upload_id = body["upload_id"]
    provider.complete_upload(upload_id)
    status, body = await handle_media_request(
        method="GET",
        path=f"{path}/{upload_id}",
        actor=actor,
        body=None,
        provider=provider,
        store=store,
    )
    assert status == 200
    assert body["asset_id"]
    record = await store.by_upload(upload_id)
    status, body = await handle_media_request(
        method="GET",
        path=f"moot/hearings/{HEARING}/media/playback/{record.playback_ids[0]}",
        actor=actor,
        body=None,
        provider=provider,
        store=store,
        environ={},
    )
    assert status == 503
    assert body["error"] == "signed_playback_unconfigured"
    assert "MOOT_MUX_SIGNING_KEY_ID" in body["required_secrets"]


def test_compose_passthrough_tank_only():
    compose = (ROOT / "docker-compose.yml").read_text()
    za = (ROOT / "docker-compose.za.yml").read_text()
    for text in (compose, za):
        assert "MOOT_MUX_TOKEN_ID: ${MOOT_MUX_TOKEN_ID:-}" in text
        assert "MOOT_MUX_TOKEN_SECRET: ${MOOT_MUX_TOKEN_SECRET:-}" in text
    # Not on hermes / litellm / agent rooms in main compose
    hermes = compose.split("\n  hermes:\n", 1)[1].split("\n  local-model", 1)[0]
    assert "MOOT_MUX_TOKEN" not in hermes
