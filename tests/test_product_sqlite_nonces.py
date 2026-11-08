"""Private workers need durable replay checks without database credentials."""
import asyncio
import time

import pytest
from chassis.sqlite_nonces import SQLiteNonces
from chassis.user_assertion import SignedUser, sign_assertion, verify_assertion


@pytest.mark.asyncio
async def test_nonce_is_atomic_across_store_instances_and_restart(tmp_path):
    path = tmp_path / "placeholder-nonces.sqlite3"
    stores = [SQLiteNonces(path) for _ in range(12)]
    results = await asyncio.gather(*(store.claim("placeholder-tenant", "placeholder-nonce", time.time() + 60)
                                     for store in stores))
    assert sum(results) == 1
    assert not await SQLiteNonces(path).claim("placeholder-tenant", "placeholder-nonce", time.time() + 60)
    assert await SQLiteNonces(path).claim("placeholder-other-tenant", "placeholder-nonce", time.time() + 60)


@pytest.mark.asyncio
async def test_expired_nonce_is_refused_without_creating_storage(tmp_path):
    path = tmp_path / "placeholder-nonces.sqlite3"
    assert not await SQLiteNonces(path).claim("placeholder-tenant", "placeholder-nonce", time.time() - 1)
    assert not path.exists()


@pytest.mark.asyncio
async def test_shared_verifier_uses_durable_store_and_fails_closed(tmp_path):
    actor = SignedUser("11111111-1111-4111-8111-111111111111", "placeholder-user", "member")
    key = "placeholder-product-key"
    body = b'{"task":"placeholder"}'
    token = sign_assertion("rig", actor, "POST", "/delegate", body, key=key)
    store = SQLiteNonces(tmp_path / "placeholder-nonces.sqlite3")
    args = dict(key=key, product="rig", tenant_id=actor.tenant_id, method="POST",
                target="/delegate", body=body, consume_nonce=store.claim)
    assert await verify_assertion(token, **args) == actor
    with pytest.raises(PermissionError):
        await verify_assertion(token, **{**args, "consume_nonce": SQLiteNonces(store.path).claim})
    fresh = sign_assertion("rig", actor, "POST", "/delegate", body, key=key)
    unavailable = SQLiteNonces(tmp_path)  # A directory cannot be opened as a database.
    with pytest.raises(PermissionError):
        await verify_assertion(fresh, **{**args, "consume_nonce": unavailable.claim})
