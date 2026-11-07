"""The shared stack itself uses real Hermes, PostgreSQL and Qdrant local mode."""
import pytest


@pytest.mark.asyncio
async def test_shared_stack_isolation_and_signed_client(gate78_memory):
    stack = await gate78_memory("opli")
    owner = stack.client("placeholder-owner")
    other = stack.client("placeholder-other-user")
    row = await owner.remember(stack.tenant, "placeholder private answer", "opli.receipt",
                               "urn:placeholder:gate78")
    assert row["id"] in {r["id"] for r in await owner.records(stack.tenant)}
    assert row["id"] not in {r["id"] for r in await other.records(stack.tenant)}
    assert not await owner.recall(stack.other_tenant, "placeholder private answer")
    await owner.forget(row["id"], stack.tenant)
    assert not await owner.recall(stack.tenant, "placeholder private answer")
    assert ("POST", "/memories") in stack.calls
    assert ("GET", "/records") in stack.calls
    assert ("POST", "/recall") in stack.calls
    assert all(not path.startswith("/v1/memory") for _, path in stack.calls)
