"""Standalone 50k benchmark against ephemeral local Postgres; no outside network."""
import asyncio
import json
import os
import resource
import time
import tracemalloc
from pathlib import Path
from uuid import uuid4

import asyncpg
import pgserver
from base_lists import FindArgs, Store
from base_product_fixtures import AT, finished, raw
from fastapi import HTTPException

from agents.base.engines.ffl.reference import project


async def benchmark(uri):
    pool = await asyncpg.create_pool(uri, min_size=1, max_size=1)
    tenant = uuid4()
    seed = finished(project(raw(state="DC")))
    seed["raw"]["_base_reference"].update(source_url="https://reference.example/list", checked_at=AT)
    seed["raw"]["_base_reference"]["address"]["city"] = "Washington"
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA agent_base")
        await conn.execute("CREATE TABLE agent_base.records(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                           "tenant_id uuid,raw jsonb,profile jsonb,passes jsonb,status text,updated_at timestamptz)")
        await conn.execute("INSERT INTO agent_base.records(tenant_id,raw,profile,passes,status,updated_at) "
                           "SELECT $1,$2::jsonb,$3::jsonb,$4::jsonb,'done',$5::timestamptz "
                           "FROM generate_series(1,$6::int)", tenant, json.dumps(seed["raw"]),
                           json.dumps(seed["profile"]), json.dumps(seed["passes"]),
                           __import__('datetime').datetime.fromisoformat(AT), 50000)
    store = Store(pool)
    filters = FindArgs(state="DC", city="Washington", licence_type="01", has_website=True,
                       checked_on_or_after=AT[:10])
    metrics = {}
    for operation in ("find", "save"):
        tracemalloc.start()
        started = time.perf_counter()
        if operation == "find":
            found = await store.find(tenant, filters)
            assert found["total"] == 50000 and len(found["records"]) == 20
        else:
            try:
                await store.save(tenant, "invented", filters)
                raise AssertionError("oversized save was accepted")
            except HTTPException as error:
                assert error.status_code == 422 and error.detail == {"total": 50000}
        metrics[operation] = {"seconds": round(time.perf_counter()-started, 3),
                              "peak_python_mib": round(tracemalloc.get_traced_memory()[1]/1024/1024, 3),
                              "peak_client_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 3)}
        tracemalloc.stop()
    await pool.close()
    print(json.dumps({"records": 50000, "database": "ephemeral local PostgreSQL", "metrics": metrics}))


if __name__ == "__main__":
    server = pgserver.get_server(Path(__file__).resolve().parents[1] / '.git' / ('b4-scale-' + str(os.getpid())), cleanup_mode='delete')
    try:
        asyncio.run(benchmark(server.get_uri()))
    finally:
        server.cleanup()
