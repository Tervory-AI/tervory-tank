"""Offline contract tests for Tank-controlled Moot Mux door (no live Mux, no paid calls)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))

from moot_media import (
    MootActor,
    create_upload,
    handle_media_request,
    match_media_path,
    playback_access,
    upload_status,
)
from moot_media_store import MemoryOwnershipStore
from moot_mux import (
    PLAYBACK_POLICY,
    FakeMuxProvider,
    MuxError,
    MuxNotConfigured,
    SignedPlaybackUnconfigured,
    credentials_from_env,
    credentials_present,
    mint_playback_jwt,
    normalize_cors_origin,
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


def _ephemeral_signing_env():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    kid = "test_kid_" + uuid4().hex[:12]
    env = {
        "MOOT_MUX_SIGNING_KEY_ID": kid,
        "MOOT_MUX_SIGNING_PRIVATE_KEY": base64.b64encode(pem).decode(),
    }
    return env, key.public_key(), kid


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
        "hearing_id": HEARING,
        "kind": "uploads",
        "resource_id": "",
    }
    assert (
        match_media_path(f"moot/hearings/{HEARING}/media/uploads/upload_abc")[
            "resource_id"
        ]
        == "upload_abc"
    )
    assert match_media_path(f"moot/hearings/{HEARING}/media/assets") is None
    assert match_media_path("moot/hearings") is None


def test_cors_origin_allowlist():
    assert (
        normalize_cors_origin("https://zenas.tervory.com/")
        == "https://zenas.tervory.com"
    )
    assert normalize_cors_origin("https://app.tervory.com") == "https://app.tervory.com"
    with pytest.raises(MuxError) as forbidden:
        normalize_cors_origin("https://evil.example")
    assert forbidden.value.code == "cors_origin_forbidden"
    with pytest.raises(MuxError) as bad:
        normalize_cors_origin("not-a-url")
    assert bad.value.code == "invalid_cors_origin"


def test_mint_playback_jwt_offline_contract():
    import time

    env, public, kid = _ephemeral_signing_env()
    issued = int(time.time())
    token = mint_playback_jwt("playback_abc123", environ=env, ttl_s=600, now=issued)
    claims = jwt.decode(token, public, algorithms=["RS256"], audience="v")
    assert claims["sub"] == "playback_abc123"
    assert claims["aud"] == "v"
    assert claims["exp"] == issued + 600
    header = jwt.get_unverified_header(token)
    assert header["kid"] == kid
    assert header["alg"] == "RS256"
    with pytest.raises(SignedPlaybackUnconfigured):
        mint_playback_jwt("playback_abc123", environ={})


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
        idempotency_key=str(uuid4()),
    )
    assert created["playback_policy"] == PLAYBACK_POLICY
    assert created["upload_id"]
    assert created["upload_url"].startswith("https://")
    assert "stream.mux.com" not in created["upload_url"]

    with pytest.raises(Exception) as denied:
        await create_upload(
            actor=actor,
            hearing_id=HEARING,
            cors_origin="https://zenas.tervory.com",
            provider=provider,
            store=store,
            hearing_allowed=deny,
            idempotency_key=str(uuid4()),
        )
    assert denied.value.code == "not_found"

    provider.complete_upload(created["upload_id"])
    status = await upload_status(
        actor=actor,
        hearing_id=HEARING,
        upload_id=created["upload_id"],
        provider=provider,
        store=store,
        hearing_allowed=allow,
    )
    assert status["status"] == "asset_created"
    assert status["asset_id"]

    other = MootActor(TENANT, OTHER)
    with pytest.raises(Exception) as cross:
        await upload_status(
            actor=other,
            hearing_id=HEARING,
            upload_id=created["upload_id"],
            provider=provider,
            store=store,
            hearing_allowed=allow,
        )
    assert cross.value.code == "not_found"

    record = await store.by_upload(created["upload_id"], tenant_id=TENANT)
    assert record and record.playback_ids
    with pytest.raises(SignedPlaybackUnconfigured) as play:
        await playback_access(
            actor=actor,
            hearing_id=HEARING,
            playback_id=record.playback_ids[0],
            store=store,
            environ={},
            hearing_allowed=allow,
        )
    assert play.value.required_names == (
        "MOOT_MUX_SIGNING_KEY_ID",
        "MOOT_MUX_SIGNING_PRIVATE_KEY",
    )


@pytest.mark.asyncio
async def test_playback_jwt_success_and_non_owner_denied():
    provider = FakeMuxProvider()
    store = MemoryOwnershipStore()
    actor = MootActor(TENANT, USER)
    env, public, kid = _ephemeral_signing_env()
    created = await create_upload(
        actor=actor,
        hearing_id=HEARING,
        cors_origin="https://zenas.tervory.com",
        provider=provider,
        store=store,
        hearing_allowed=allow,
        test=True,
        idempotency_key=str(uuid4()),
    )
    provider.complete_upload(created["upload_id"])
    await upload_status(
        actor=actor,
        hearing_id=HEARING,
        upload_id=created["upload_id"],
        provider=provider,
        store=store,
        hearing_allowed=allow,
    )
    record = await store.by_upload(created["upload_id"], tenant_id=TENANT)
    pid = record.playback_ids[0]
    access = await playback_access(
        actor=actor,
        hearing_id=HEARING,
        playback_id=pid,
        store=store,
        environ=env,
        ttl_s=120,
        hearing_allowed=allow,
    )
    assert access["playback_policy"] == "signed"
    assert access["playback_url"].startswith(
        f"https://stream.mux.com/{pid}.m3u8?token="
    )
    claims = jwt.decode(access["token"], public, algorithms=["RS256"], audience="v")
    assert claims["sub"] == pid
    assert jwt.get_unverified_header(access["token"])["kid"] == kid
    other = MootActor(TENANT, OTHER)
    with pytest.raises(MuxError) as cross:
        await playback_access(
            actor=other,
            hearing_id=HEARING,
            playback_id=pid,
            store=store,
            environ=env,
            hearing_allowed=allow,
        )
    assert cross.value.code == "not_found"


@pytest.mark.asyncio
async def test_idempotency_and_rate_guard():
    provider = FakeMuxProvider()
    store = MemoryOwnershipStore()
    actor = MootActor(TENANT, USER)
    first = await create_upload(
        actor=actor,
        hearing_id=HEARING,
        cors_origin="https://zenas.tervory.com",
        provider=provider,
        store=store,
        hearing_allowed=allow,
        test=True,
        idempotency_key="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    second = await create_upload(
        actor=actor,
        hearing_id=HEARING,
        cors_origin="https://zenas.tervory.com",
        provider=provider,
        store=store,
        hearing_allowed=allow,
        test=True,
        idempotency_key="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert first["upload_id"] == second["upload_id"]
    assert provider.create_calls == 1
    # Force rate limit with tiny cap
    with pytest.raises(MuxError) as capped:
        await create_upload(
            actor=actor,
            hearing_id=HEARING,
            cors_origin="https://zenas.tervory.com",
            provider=provider,
            store=store,
            hearing_allowed=allow,
            test=True,
            environ={
                "MOOT_MUX_UPLOAD_RATE_PER_MIN": "1",
                "MOOT_MUX_DAILY_UPLOAD_CAP": "100",
            },
            idempotency_key=str(uuid4()),
        )
    assert capped.value.code == "rate_limited"


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
        idempotency_key=str(uuid4()),
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
        idempotency_key=str(uuid4()),
        hearing_allowed=allow,
    )
    assert status == 200
    assert body["asset_id"]
    record = await store.by_upload(upload_id, tenant_id=TENANT)
    status, body = await handle_media_request(
        method="GET",
        path=f"moot/hearings/{HEARING}/media/playback/{record.playback_ids[0]}",
        actor=actor,
        body=None,
        provider=provider,
        store=store,
        environ={},
        idempotency_key=str(uuid4()),
        hearing_allowed=allow,
    )
    assert status == 503
    assert body["error"] == "signed_playback_unconfigured"
    assert "MOOT_MUX_SIGNING_KEY_ID" in body["required_secrets"]
    # Forbidden cors via handle
    status, body = await handle_media_request(
        method="POST",
        path=path,
        actor=actor,
        body={"cors_origin": "https://evil.example"},
        provider=provider,
        store=store,
        hearing_allowed=allow,
        allow_test_uploads=True,
        idempotency_key=str(uuid4()),
    )
    assert status == 403
    assert body["error"] == "cors_origin_forbidden"


def test_compose_passthrough_tank_only():
    compose = (ROOT / "docker-compose.yml").read_text()
    za = (ROOT / "docker-compose.za.yml").read_text()
    for text in (compose, za):
        assert "MOOT_MUX_TOKEN_ID: ${MOOT_MUX_TOKEN_ID:-}" in text
        assert "MOOT_MUX_TOKEN_SECRET: ${MOOT_MUX_TOKEN_SECRET:-}" in text
        assert "MOOT_MUX_SIGNING_KEY_ID: ${MOOT_MUX_SIGNING_KEY_ID:-}" in text
        assert "MOOT_MUX_SIGNING_PRIVATE_KEY: ${MOOT_MUX_SIGNING_PRIVATE_KEY:-}" in text
    hermes = compose.split("\n  hermes:\n", 1)[1].split("\n  local-model", 1)[0]
    assert "MOOT_MUX_TOKEN" not in hermes
    assert "MOOT_MUX_SIGNING" not in hermes
    schema = (ROOT / "tank" / "schema.sql").read_text()
    assert "tank.moot_media" in schema
