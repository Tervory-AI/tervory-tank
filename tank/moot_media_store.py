"""Ownership records for Moot Mux media. Memory for tests; Postgres for Tank."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class MediaRecord:
    tenant_id: str
    user_id: str
    hearing_id: str
    upload_id: str
    asset_id: str | None = None
    playback_ids: list[str] = field(default_factory=list)
    passthrough: str = ""
    idempotency_key: str | None = None


class AsyncOwnershipStore(Protocol):
    async def save(self, record: MediaRecord) -> None: ...

    async def by_upload(self, upload_id: str) -> MediaRecord | None: ...

    async def by_asset(self, asset_id: str) -> MediaRecord | None: ...

    async def by_playback(self, playback_id: str) -> MediaRecord | None: ...

    async def by_idempotency(
        self, tenant_id: str, user_id: str, hearing_id: str, idempotency_key: str
    ) -> MediaRecord | None: ...

    async def bind_asset(self, upload_id: str, asset_id: str, playback_ids: list[str]) -> MediaRecord | None: ...

    async def count_uploads_since(self, tenant_id: str, user_id: str, since_epoch: float) -> int: ...


class MemoryOwnershipStore:
    def __init__(self) -> None:
        self._by_upload: dict[str, MediaRecord] = {}
        self._by_asset: dict[str, MediaRecord] = {}
        self._by_playback: dict[str, MediaRecord] = {}
        self._by_idem: dict[tuple[str, str, str, str], MediaRecord] = {}
        self._created_at: dict[str, float] = {}

    async def save(self, record: MediaRecord) -> None:
        import time
        self._by_upload[record.upload_id] = record
        self._created_at.setdefault(record.upload_id, time.time())
        if record.asset_id:
            self._by_asset[record.asset_id] = record
        for pid in record.playback_ids:
            self._by_playback[pid] = record
        if record.idempotency_key:
            self._by_idem[(record.tenant_id, record.user_id, record.hearing_id, record.idempotency_key)] = record

    async def by_upload(self, upload_id: str) -> MediaRecord | None:
        return self._by_upload.get(upload_id)

    async def by_asset(self, asset_id: str) -> MediaRecord | None:
        return self._by_asset.get(asset_id)

    async def by_playback(self, playback_id: str) -> MediaRecord | None:
        return self._by_playback.get(playback_id)

    async def by_idempotency(
        self, tenant_id: str, user_id: str, hearing_id: str, idempotency_key: str
    ) -> MediaRecord | None:
        return self._by_idem.get((tenant_id, user_id, hearing_id, idempotency_key))

    async def bind_asset(self, upload_id: str, asset_id: str, playback_ids: list[str]) -> MediaRecord | None:
        row = self._by_upload.get(upload_id)
        if row is None:
            return None
        row.asset_id = asset_id
        row.playback_ids = list(playback_ids)
        self._by_asset[asset_id] = row
        for pid in playback_ids:
            self._by_playback[pid] = row
        return row

    async def count_uploads_since(self, tenant_id: str, user_id: str, since_epoch: float) -> int:
        total = 0
        for upload_id, row in self._by_upload.items():
            if row.tenant_id == tenant_id and row.user_id == user_id and self._created_at.get(upload_id, 0) >= since_epoch:
                total += 1
        return total


def _row_to_record(row: Any) -> MediaRecord | None:
    if row is None:
        return None
    playback = row["playback_ids"]
    if isinstance(playback, str):
        playback = json.loads(playback)
    return MediaRecord(
        tenant_id=str(row["tenant_id"]),
        user_id=row["user_id"],
        hearing_id=str(row["hearing_id"]),
        upload_id=row["upload_id"],
        asset_id=row["asset_id"],
        playback_ids=list(playback or []),
        passthrough=row["passthrough"] or "",
        idempotency_key=row["idempotency_key"] if "idempotency_key" in row.keys() else None,
    )


class PostgresOwnershipStore:
    def __init__(self, pool_factory):
        self._pool = pool_factory

    async def save(self, record: MediaRecord) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """INSERT INTO tank.moot_media
                    (upload_id, tenant_id, user_id, hearing_id, asset_id, playback_ids, passthrough, idempotency_key)
                   VALUES ($1,$2::uuid,$3,$4::uuid,$5,$6::jsonb,$7,$8)
                   ON CONFLICT (upload_id) DO UPDATE SET
                     asset_id=COALESCE(EXCLUDED.asset_id, tank.moot_media.asset_id),
                     playback_ids=EXCLUDED.playback_ids,
                     updated_at=now()""",
                record.upload_id, record.tenant_id, record.user_id, record.hearing_id,
                record.asset_id, json.dumps(record.playback_ids), record.passthrough,
                record.idempotency_key,
            )

    async def by_upload(self, upload_id: str) -> MediaRecord | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tank.moot_media WHERE upload_id=$1", upload_id)
        return _row_to_record(row)

    async def by_asset(self, asset_id: str) -> MediaRecord | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tank.moot_media WHERE asset_id=$1", asset_id)
        return _row_to_record(row)

    async def by_playback(self, playback_id: str) -> MediaRecord | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tank.moot_media WHERE playback_ids ? $1", playback_id
            )
        return _row_to_record(row)

    async def by_idempotency(
        self, tenant_id: str, user_id: str, hearing_id: str, idempotency_key: str
    ) -> MediaRecord | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM tank.moot_media
                   WHERE tenant_id=$1::uuid AND user_id=$2 AND hearing_id=$3::uuid
                     AND idempotency_key=$4""",
                tenant_id, user_id, hearing_id, idempotency_key,
            )
        return _row_to_record(row)

    async def bind_asset(self, upload_id: str, asset_id: str, playback_ids: list[str]) -> MediaRecord | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE tank.moot_media SET asset_id=$2, playback_ids=$3::jsonb, updated_at=now()
                   WHERE upload_id=$1 RETURNING *""",
                upload_id, asset_id, json.dumps(playback_ids),
            )
        return _row_to_record(row)

    async def count_uploads_since(self, tenant_id: str, user_id: str, since_epoch: float) -> int:
        async with self._pool().acquire() as conn:
            return int(await conn.fetchval(
                """SELECT count(*) FROM tank.moot_media
                   WHERE tenant_id=$1::uuid AND user_id=$2
                     AND created_at >= to_timestamp($3)""",
                tenant_id, user_id, since_epoch,
            ) or 0)
