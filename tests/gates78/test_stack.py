"""The shared stack itself uses real Hermes, PostgreSQL and Qdrant local mode."""
import asyncpg
import pytest
from gate78_contract import PRODUCTS


@pytest.mark.asyncio
@pytest.mark.parametrize("product", PRODUCTS)
async def test_shared_stack_isolation_and_signed_client(gate78_memory, product):
    stack = await gate78_memory(product)
    owner = stack.client("placeholder-owner")
    other = stack.client("placeholder-other-user")
    row = await owner.remember(stack.tenant, "placeholder private answer", stack.agent + ".placeholder",
                               "urn:placeholder:gate78")
    assert row["id"] in {r["id"] for r in await owner.records(stack.tenant)}
    assert row["id"] in {r["id"] for r in await owner.recall(stack.tenant, "placeholder private answer")}
    assert row["agent"] == stack.agent
    with pytest.raises(asyncpg.CheckViolationError):
        await stack.records.pool.execute(
            f"UPDATE {stack.records.schema(stack.agent)}.memory_records SET agent='placeholder_other'"
        )
    assert row["id"] not in {r["id"] for r in await other.records(stack.tenant)}
    assert not await other.recall(stack.tenant, "placeholder private answer")
    assert not await owner.recall(stack.other_tenant, "placeholder private answer")
    await owner.forget(row["id"], stack.tenant)
    assert not await owner.recall(stack.tenant, "placeholder private answer")
    assert ("POST", "/memories") in stack.calls
    assert ("GET", "/records") in stack.calls
    assert ("POST", "/recall") in stack.calls
    assert all(not path.startswith("/v1/memory") for _, path in stack.calls)
