"""Real SQL reservations and revoked membership; provider transport stays fake."""

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from moot_media import MootActor, create_upload, handle_media_request
from moot_media_store import MemoryOwnershipStore, PostgresOwnershipStore
from moot_mux import FakeMuxProvider, MuxError
from test_moot_mux_door import _ephemeral_signing_env
from test_train1 import database

__all__ = ["database"]
TENANT = "11111111-1111-1111-1111-111111111111"
HEARING = "22222222-2222-2222-2222-222222222222"
USER = "placeholder-media-user"


async def allow(*_):
    return True


@pytest_asyncio.fixture(params=["memory", "postgres"])
async def ownership(request, database):
    pool, _ = database
    return (
        MemoryOwnershipStore()
        if request.param == "memory"
        else PostgresOwnershipStore(lambda: pool)
    )


class YieldingProvider(FakeMuxProvider):
    async def create_direct_upload(self, **kwargs):
        await asyncio.sleep(0.02)
        return await super().create_direct_upload(**kwargs)


def arguments(store, provider, **changes):
    return (
        dict(
            actor=MootActor(TENANT, USER),
            hearing_id=HEARING,
            cors_origin="https://zenas.tervory.com",
            provider=provider,
            store=store,
            hearing_allowed=allow,
            test=True,
            idempotency_key=str(uuid4()),
        )
        | changes
    )


@pytest.mark.asyncio
async def test_concurrent_identical_requests_make_one_provider_write(ownership):
    provider = YieldingProvider()
    args = arguments(ownership, provider)
    results = await asyncio.gather(
        *(create_upload(**args) for _ in range(20)), return_exceptions=True
    )
    delivered = [r for r in results if isinstance(r, dict)]
    assert delivered and provider.create_calls == 1
    assert {r["upload_id"] for r in delivered} == {delivered[0]["upload_id"]}
    assert all(
        isinstance(r, dict)
        or (isinstance(r, MuxError) and r.code == "upload_pending_or_uncertain")
        for r in results
    )
    assert (await create_upload(**args))["upload_id"] == delivered[0]["upload_id"]
    assert provider.create_calls == 1
    with pytest.raises(MuxError, match="idempotency_conflict"):
        await create_upload(**(args | {"cors_origin": "https://app.tervory.com"}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "limit,code",
    [
        ("MOOT_MUX_UPLOAD_RATE_PER_MIN", "rate_limited"),
        ("MOOT_MUX_DAILY_UPLOAD_CAP", "upload_budget_exhausted"),
    ],
)
async def test_concurrent_distinct_requests_cannot_exceed_cap(ownership, limit, code):
    provider = YieldingProvider()
    env = {
        "MOOT_MUX_UPLOAD_RATE_PER_MIN": "100",
        "MOOT_MUX_DAILY_UPLOAD_CAP": "100",
        limit: "2",
    }
    results = await asyncio.gather(
        *(
            create_upload(**arguments(ownership, provider, environ=env))
            for _ in range(20)
        ),
        return_exceptions=True,
    )
    assert provider.create_calls == 2
    assert sum(isinstance(r, dict) for r in results) == 2
    assert sum(isinstance(r, MuxError) and r.code == code for r in results) == 18


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["provider_response_lost", "ownership_save_failed"])
async def test_uncertain_write_survives_store_restart_without_retry(
    ownership, database, monkeypatch, failure
):
    provider = YieldingProvider()
    args = arguments(ownership, provider)
    if failure == "provider_response_lost":
        original = provider.create_direct_upload

        async def lost(**kwargs):
            await original(**kwargs)
            raise TimeoutError("placeholder lost response")

        monkeypatch.setattr(provider, "create_direct_upload", lost)
    else:

        async def unavailable(*_):
            raise RuntimeError("placeholder database unavailable")

        monkeypatch.setattr(ownership, "complete_upload", unavailable)
    with pytest.raises(MuxError, match="upload_pending_or_uncertain"):
        await create_upload(**args)
    assert provider.create_calls == 1
    if isinstance(ownership, PostgresOwnershipStore):
        pool, _ = database
        args["store"] = PostgresOwnershipStore(lambda: pool)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tank.moot_upload_requests WHERE tenant_id=$1::uuid AND user_id=$2",
                TENANT,
                USER,
            )
            assert row["upload_id"] is None
            marker = next(iter(provider.uploads.values()))["new_asset_settings"][
                "passthrough"
            ]
            assert marker == "moot-request:" + str(row["request_id"])
    with pytest.raises(MuxError, match="upload_pending_or_uncertain"):
        await create_upload(**args)
    assert provider.create_calls == 1


@pytest.mark.asyncio
async def test_revoked_membership_refuses_all_media_access(ownership):
    provider = YieldingProvider()
    args = arguments(ownership, provider)
    created = await create_upload(**args)
    provider.complete_upload(created["upload_id"])
    path = f"moot/hearings/{HEARING}/media"

    async def request(resource, gate=allow):
        env, _, _ = _ephemeral_signing_env()
        return await handle_media_request(
            method="GET",
            path=path + resource,
            actor=args["actor"],
            body=None,
            provider=provider,
            store=ownership,
            hearing_allowed=gate,
            environ=env,
        )

    status, _ = await request("/uploads/" + created["upload_id"])
    assert status == 200
    record = await ownership.by_upload(created["upload_id"], tenant_id=TENANT)

    async def revoked(*_):
        return False

    for resource in [
        "/uploads/" + record.upload_id,
        "/assets/" + record.asset_id,
        "/playback/" + record.playback_ids[0],
    ]:
        status, body = await request(resource, revoked)
        assert status == 404 and body == {"error": "not_found"}
    with pytest.raises(MuxError, match="not_found"):
        await create_upload(**(args | {"hearing_allowed": revoked}))
    assert provider.create_calls == 1
    assert await ownership.by_upload(record.upload_id, tenant_id=str(uuid4())) is None


@pytest.mark.asyncio
async def test_revocation_during_provider_read_does_not_release_upload_url(
    ownership, monkeypatch
):
    provider = YieldingProvider()
    args = arguments(ownership, provider)
    created = await create_upload(**args)
    permitted = True

    async def gate(*_):
        return permitted

    original = provider.retrieve_upload

    async def retrieve(upload_id):
        nonlocal permitted
        data = await original(upload_id)
        permitted = False
        return data

    monkeypatch.setattr(provider, "retrieve_upload", retrieve)
    status, body = await handle_media_request(
        method="GET",
        path=f"moot/hearings/{HEARING}/media/uploads/{created['upload_id']}",
        actor=args["actor"],
        body=None,
        provider=provider,
        store=ownership,
        hearing_allowed=gate,
    )
    assert status == 404 and "upload_url" not in body


@pytest.mark.asyncio
async def test_missing_idempotency_or_membership_gate_never_writes():
    provider, store = YieldingProvider(), MemoryOwnershipStore()
    with pytest.raises(MuxError, match="invalid_idempotency_key"):
        await create_upload(**arguments(store, provider, idempotency_key=None))
    status, _ = await handle_media_request(
        method="POST",
        path=f"moot/hearings/{HEARING}/media/uploads",
        actor=MootActor(TENANT, USER),
        body={"cors_origin": "https://zenas.tervory.com"},
        provider=provider,
        store=store,
        idempotency_key=str(uuid4()),
    )
    assert status == 404 and provider.create_calls == 0
