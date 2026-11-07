"""One real Hermes/SQL/vector test stack shared by product scenarios.

Only embeddings use a deterministic test encoder. No memory or ownership fake.
Products wire their actual handlers to stack.http at the network boundary.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import sys
from urllib.parse import urlsplit

import httpx
import pytest
import pytest_asyncio

from chassis.memory import MemoryClient
from hermes.records import Records
from hermes.service import create_app
from hermes.store import InMemoryStore
from test_agent_memory_records import memory as sql_memory_fixture

# Existing contributions import their uniquely named fixture helpers directly.
# Packaging the tests avoids collisions with tests/test_<product>.py without a
# repository-wide pytest import-mode change or requiring owner file renames.
for helper_path in (Path(__file__).parent, Path(__file__).parent / "products"):
    if str(helper_path) not in sys.path:
        # Append: legacy acceptance modules import flat test_<product> helpers.
        # Putting the products directory first could redirect those imports to
        # the new suite even though pytest itself uses qualified module names.
        sys.path.append(str(helper_path))

from gate78_contract import PRODUCTS

sql_memory = sql_memory_fixture


@pytest.fixture
def gate78_database():
    url = os.environ.get("MEMORY_TEST_DATABASE_URL", "")
    if not url or urlsplit(url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Gate 7/8 requires a disposable loopback MEMORY_TEST_DATABASE_URL; missing infrastructure is not a pass")
    return url


@dataclass
class MemoryStack:
    product: str
    agent: str
    key: str
    tenant: str
    other_tenant: str
    records: Records
    http: httpx.AsyncClient
    app: object
    calls: list[tuple[str, str]]

    def client(self, user: str) -> MemoryClient:
        return MemoryClient("http://hermes", self.key, self.agent, self.http, user_id=user)


@pytest_asyncio.fixture
async def gate78_memory(gate78_database, sql_memory, monkeypatch):
    """Factory: `stack = await gate78_memory('trigger')`; one product per case.

    This fixture supplies infrastructure, never an authenticated product actor.
    Product tests must enter their real sign-in/request path to obtain that actor.
    """
    opened = []

    async def make(product: str) -> MemoryStack:
        if product not in PRODUCTS:
            raise ValueError("Unknown Gate 7/8 product")
        if opened:
            raise ValueError("Use one product per case to isolate SQL/vector fixtures")
        m = sql_memory
        agent = {"autumbra": "ghost", "market-lab": "market_lab"}.get(product, product)
        records = Records(m.pool, m.records.index, m.records.encoder, m.records.model, [agent])
        # Keep real agent kind/key configuration; point only its SQL namespace at
        # the unique, already-migrated schema owned and removed by sql_memory.
        records._schemas[agent] = m.records.schema(m.agent)
        key = "placeholder-gate78-product-key"
        monkeypatch.setenv("TANK_KEY_" + agent.upper(), key)
        app = create_app(InMemoryStore(), m.records.encoder, records=records)
        calls = []

        async def observe(request):
            calls.append((request.method, request.url.path))

        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://hermes",
                                 event_hooks={"request": [observe]})
        opened.append(http)
        return MemoryStack(product, agent, key, m.tenant, m.other, records, http, app, calls)

    try:
        yield make
    finally:
        for http in opened:
            await http.aclose()
