"""Authenticated Moot media gateway on Tank. Tenant/user/hearing isolated."""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable
from uuid import UUID

from moot_media_store import AsyncOwnershipStore, MediaRecord, MemoryOwnershipStore
from moot_mux import (
    PLAYBACK_POLICY,
    MuxError,
    MuxNotConfigured,
    MuxProvider,
    SignedPlaybackUnconfigured,
    provider_from_env,
    require_signed_playback_ready,
)

HEARING_UUID = re.compile(
    r"^moot/hearings/([0-9a-fA-F-]{36})/media/(uploads|assets|playback)(?:/([0-9A-Za-z_-]{1,80}))?$"
)

HearingGate = Callable[[str, str, str], Awaitable[bool]]


class MootActor:
    __slots__ = ("tenant_id", "user_id", "founder")

    def __init__(self, tenant_id: str, user_id: str, founder: bool = False):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.founder = founder


DEFAULT_STORE: AsyncOwnershipStore = MemoryOwnershipStore()


def match_media_path(path: str) -> dict[str, str] | None:
    cleaned = (path or "").strip().strip("/")
    matched = HEARING_UUID.fullmatch(cleaned)
    if not matched:
        return None
    hearing_id, kind, resource_id = matched.group(1), matched.group(2), matched.group(3)
    if kind in {"assets", "playback"} and not resource_id:
        return None
    if kind == "uploads" and resource_id is None:
        return {"hearing_id": hearing_id, "kind": kind, "resource_id": ""}
    return {"hearing_id": hearing_id, "kind": kind, "resource_id": resource_id or ""}


def passthrough_for(actor: MootActor, hearing_id: str) -> str:
    return f"moot:{actor.tenant_id}:{hearing_id}:{actor.user_id}"[:255]


async def _owned(record: MediaRecord | None, actor: MootActor, hearing_id: str) -> MediaRecord:
    if record is None:
        raise MuxError("not_found", 404)
    if record.tenant_id != actor.tenant_id or record.hearing_id != hearing_id:
        raise MuxError("not_found", 404)
    if record.user_id != actor.user_id and not actor.founder:
        raise MuxError("not_found", 404)
    return record


def public_upload_view(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("new_asset_settings") if isinstance(data.get("new_asset_settings"), dict) else {}
    policies = settings.get("playback_policies") or data.get("playback_policies") or [PLAYBACK_POLICY]
    return {
        "upload_id": data.get("id"),
        "status": data.get("status"),
        "upload_url": data.get("url"),
        "timeout": data.get("timeout"),
        "asset_id": data.get("asset_id"),
        "playback_policy": PLAYBACK_POLICY if PLAYBACK_POLICY in policies else "unknown",
        "test": bool(data.get("test") or settings.get("test")),
    }


def public_asset_view(data: dict[str, Any]) -> dict[str, Any]:
    playback_ids = []
    for row in data.get("playback_ids") or []:
        if isinstance(row, dict) and row.get("id"):
            playback_ids.append({"id": row["id"], "policy": row.get("policy") or PLAYBACK_POLICY})
    return {
        "asset_id": data.get("id"),
        "status": data.get("status"),
        "duration": data.get("duration"),
        "playback_ids": playback_ids,
        "upload_id": data.get("upload_id"),
        "test": bool(data.get("test")),
    }


async def create_upload(
    *,
    actor: MootActor,
    hearing_id: str,
    cors_origin: str,
    provider: MuxProvider,
    store: AsyncOwnershipStore,
    hearing_allowed: HearingGate,
    test: bool = False,
) -> dict[str, Any]:
    UUID(hearing_id)
    UUID(actor.tenant_id)
    if not cors_origin or len(cors_origin) > 200:
        raise MuxError("invalid_cors_origin", 422)
    if not await hearing_allowed(actor.tenant_id, actor.user_id, hearing_id):
        raise MuxError("not_found", 404)
    marker = passthrough_for(actor, hearing_id)
    created = await provider.create_direct_upload(
        cors_origin=cors_origin, passthrough=marker, test=test
    )
    upload_id = str(created.get("id") or "")
    if not upload_id:
        raise MuxError("mux_upstream_error", 502)
    await store.save(
        MediaRecord(
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            hearing_id=hearing_id,
            upload_id=upload_id,
            passthrough=marker,
        )
    )
    return public_upload_view(created)


async def upload_status(
    *,
    actor: MootActor,
    hearing_id: str,
    upload_id: str,
    provider: MuxProvider,
    store: AsyncOwnershipStore,
) -> dict[str, Any]:
    record = await _owned(await store.by_upload(upload_id), actor, hearing_id)
    data = await provider.retrieve_upload(upload_id)
    asset_id = data.get("asset_id")
    if isinstance(asset_id, str) and asset_id:
        asset = await provider.retrieve_asset(asset_id)
        playback_ids = [
            str(row["id"])
            for row in (asset.get("playback_ids") or [])
            if isinstance(row, dict) and row.get("id")
        ]
        await store.bind_asset(record.upload_id, asset_id, playback_ids)
    return public_upload_view(data)


async def asset_status(
    *,
    actor: MootActor,
    hearing_id: str,
    asset_id: str,
    provider: MuxProvider,
    store: AsyncOwnershipStore,
) -> dict[str, Any]:
    await _owned(await store.by_asset(asset_id), actor, hearing_id)
    return public_asset_view(await provider.retrieve_asset(asset_id))


async def playback_access(
    *,
    actor: MootActor,
    hearing_id: str,
    playback_id: str,
    store: AsyncOwnershipStore,
    environ: dict | None = None,
) -> dict[str, Any]:
    await _owned(await store.by_playback(playback_id), actor, hearing_id)
    require_signed_playback_ready(environ)
    raise SignedPlaybackUnconfigured()


def error_payload(exc: MuxError) -> dict[str, Any]:
    body: dict[str, Any] = {"error": exc.code}
    if isinstance(exc, SignedPlaybackUnconfigured):
        body["required_secrets"] = list(exc.required_names)
        body["playback_policy"] = PLAYBACK_POLICY
    if isinstance(exc, MuxNotConfigured):
        body["required_secrets"] = ["MOOT_MUX_TOKEN_ID", "MOOT_MUX_TOKEN_SECRET"]
    return body


async def always_allow_hearing(tenant_id: str, user_id: str, hearing_id: str) -> bool:
    return True


async def handle_media_request(
    *,
    method: str,
    path: str,
    actor: MootActor,
    body: dict[str, Any] | None,
    provider: MuxProvider | None = None,
    store: AsyncOwnershipStore | None = None,
    hearing_allowed: HearingGate | None = None,
    environ: dict | None = None,
    allow_test_uploads: bool = False,
) -> tuple[int, dict[str, Any]]:
    matched = match_media_path(path)
    if matched is None:
        return 404, {"error": "not_found"}
    hearing_id = matched["hearing_id"]
    kind = matched["kind"]
    resource_id = matched["resource_id"]
    store = store or DEFAULT_STORE
    hearing_allowed = hearing_allowed or always_allow_hearing
    try:
        if provider is None:
            provider = provider_from_env(environ)
        if method == "POST" and kind == "uploads" and not resource_id:
            cors = ""
            test = False
            if isinstance(body, dict):
                cors = str(body.get("cors_origin") or "").strip()
                test = bool(body.get("test")) and allow_test_uploads
            result = await create_upload(
                actor=actor,
                hearing_id=hearing_id,
                cors_origin=cors,
                provider=provider,
                store=store,
                hearing_allowed=hearing_allowed,
                test=test,
            )
            return 201, result
        if method == "GET" and kind == "uploads" and resource_id:
            return 200, await upload_status(
                actor=actor, hearing_id=hearing_id, upload_id=resource_id,
                provider=provider, store=store,
            )
        if method == "GET" and kind == "assets" and resource_id:
            return 200, await asset_status(
                actor=actor, hearing_id=hearing_id, asset_id=resource_id,
                provider=provider, store=store,
            )
        if method == "GET" and kind == "playback" and resource_id:
            return 200, await playback_access(
                actor=actor, hearing_id=hearing_id, playback_id=resource_id,
                store=store, environ=environ,
            )
        return 404, {"error": "not_found"}
    except MuxError as exc:
        return exc.status, error_payload(exc)
