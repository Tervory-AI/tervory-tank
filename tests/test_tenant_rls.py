"""Opt-in RLS proof on a NEW throwaway database, never a live database."""

import ast
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import subprocess
import runpy
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/_chassis"))
from chassis.db import ensure_schema  # noqa: E402
from tenant_db import TenantPool, tenant_scope  # noqa: E402

MIGRATIONS = ROOT / "db/migrations/tenant_rls"
AGENTS = ["template", "base", "ghost", "market_lab", "radix", "rig", "tiger", "tisan", "trigger", "zenas"]


def url_for(url, database, role=None):
    parts = urlsplit(url)
    if parts.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("RLS proof requires an explicitly configured local disposable Postgres")
    authority = f"{role}@{parts.hostname}:{parts.port or 5432}" if role else parts.netloc
    return urlunsplit((parts.scheme, authority, "/" + database, "", ""))


async def tiger_tables(conn):
    import importlib
    sys.path.insert(0, str(ROOT / "agents/tiger"))
    watch = importlib.import_module("watch")
    await watch.ensure_tables(conn, "agent_tiger")


@pytest.mark.asyncio
@pytest.mark.parametrize("room", ["rig", "zenas"])
async def test_room_schema_recovery_with_restricted_scoped_pool(room):
    """Real room DDL survives expected permission errors, including on reapply."""
    import importlib
    from chassis.tenant_db import TenantPool as RoomPool, tenant_scope as room_scope

    url = os.environ.get("RLS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RLS_TEST_DATABASE_URL explicitly opts into disposable Postgres tests")
    name = "room_startup_" + uuid4().hex
    role = name + "_agent"
    admin = await asyncpg.connect(url_for(url, "postgres"))
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
        await admin.execute(f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE')
        owner = await asyncpg.connect(url_for(url, name))
        try:
            await owner.execute(f'REVOKE CREATE ON DATABASE "{name}" FROM PUBLIC')
            await owner.execute(f'CREATE SCHEMA "agent_{room}" AUTHORIZATION "{role}"')
        finally:
            await owner.close()
        raw = await asyncpg.create_pool(url_for(url, name, role), min_size=1, max_size=1)
        try:
            assert not await raw.fetchval("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
            assert not await raw.fetchval("SELECT has_database_privilege(current_database(), 'CREATE')")
            # This exact denied statement aborts an enclosing checkout transaction.
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await raw.execute(f'CREATE SCHEMA IF NOT EXISTS "agent_{room}"')
            if room == "rig":
                sys.path.insert(0, str(ROOT / "agents/rig"))
                module = importlib.import_module("rigbox.store")
            else:
                module = importlib.import_module("agents.zenas.core.store")
            store = module.PgStore(RoomPool(raw))
            with room_scope(None, administrative=True):
                await store.apply_schema()
                await store.apply_schema()
            table = "products" if room == "rig" else "matters"
            assert await raw.fetchval(f'SELECT count(*) FROM "agent_{room}"."{table}"') == 0
            assert await raw.fetchval("SELECT current_setting('app.tenant_id', true)") in (None, "")
        finally:
            await raw.close()
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()


@pytest_asyncio.fixture
async def database():
    url = os.environ.get("RLS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RLS_TEST_DATABASE_URL explicitly opts into disposable Postgres tests")
    name = "rls_" + uuid4().hex
    tenant_role, founder_role = name + "_tenant", name + "_founder"
    admin = await asyncpg.connect(url_for(url, "postgres"))
    await admin.execute(f'CREATE DATABASE "{name}"')
    try:
        await admin.execute(f'CREATE ROLE "{tenant_role}" LOGIN NOSUPERUSER NOBYPASSRLS')
        await admin.execute(f'CREATE ROLE "{founder_role}" LOGIN NOSUPERUSER BYPASSRLS')
        owner = await asyncpg.connect(url_for(url, name))
        try:
            await owner.execute((ROOT / "tank/schema.sql").read_text())
            for agent in AGENTS:
                await ensure_schema(owner, agent)
                if agent == "tiger":
                    await tiger_tables(owner)
                if agent == "radix":
                    await owner.execute(runpy.run_path(str(ROOT / "agents/radix/passive_store.py"))["DDL"])
                path = ROOT / "agents" / ("_template" if agent == "template" else agent) / "schema.sql"
                await owner.execute(f'SET search_path TO "agent_{agent}",public')
                await owner.execute(path.read_text())
            await owner.execute("SET search_path TO public")
            for path in sorted(MIGRATIONS.glob("*.sql")):
                await owner.execute(path.read_text())
                await owner.execute(path.read_text())
            tables = await owner.fetch("""SELECT n.nspname AS schema,c.relname AS name,c.relrowsecurity,c.relforcerowsecurity
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                JOIN pg_attribute a ON a.attrelid=c.oid
                WHERE a.attname='tenant_id' AND NOT a.attisdropped AND c.relkind='r'
                AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY n.nspname,c.relname""")
            for schema in {row["schema"] for row in tables}:
                for role in (tenant_role, founder_role):
                    await owner.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
                    await owner.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
                    await owner.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"')
            raw = await asyncpg.create_pool(url_for(url, name, tenant_role), min_size=1, max_size=1)
            founder = await asyncpg.create_pool(url_for(url, name, founder_role), min_size=1, max_size=2)
            try:
                assert await raw.fetchval("SELECT current_user") == tenant_role
                assert not await raw.fetchval("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
                assert await founder.fetchval("SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user")
                yield SimpleNamespace(owner=owner, raw=raw, pool=TenantPool(raw), founder=founder, tables=tables, tenant_url=url_for(url, name, tenant_role), founder_url=url_for(url, name, founder_role))
            finally:
                await raw.close()
                await founder.close()
        finally:
            await owner.close()
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'DROP ROLE IF EXISTS "{tenant_role}"')
        await admin.execute(f'DROP ROLE IF EXISTS "{founder_role}"')
        await admin.close()


def sample(column, tenant, serial):
    kind = column["udt_name"]
    if column["column_name"] == "tenant_id":
        return tenant
    if kind == "uuid":
        return uuid4()
    if kind in {"text", "varchar", "bpchar"}:
        return str(serial) if kind == "bpchar" else "rls_" + uuid4().hex
    if kind in {"int2", "int4", "int8"}:
        return serial
    if kind in {"numeric", "float4", "float8"}:
        return serial / 1000
    if kind == "bool":
        return True
    if kind in {"json", "jsonb"}:
        return "{}"
    if kind in {"timestamp", "timestamptz"}:
        return datetime.now(timezone.utc) if kind == "timestamptz" else datetime.now()
    if kind == "date":
        return date.today()
    if kind == "bytea":
        return b"offline-rls"
    if kind.startswith("_"):
        return []
    raise AssertionError("Add a typed offline value for " + kind)


@pytest.mark.asyncio
async def test_every_actual_tenant_table(database):
    """Policy probes retain real tables/keys/types; business checks are separate.

    Only on this disposable database, remove domain CHECK constraints and seed
    with FK triggers disabled. This lets the same isolation matrix cover every
    relation without pretending to create valid business records or live data.
    Domain-only user triggers are disabled for these probes. Policies, column
    types, NOT NULL, PK and unique constraints stay in place.
    """
    a, b = uuid4(), uuid4()
    assert len(database.tables) > 100
    for table in database.tables:
        assert table["relrowsecurity"] and table["relforcerowsecurity"], dict(table)
        relation = f'"{table["schema"]}"."{table["name"]}"'
        checks = await database.owner.fetch("SELECT conname FROM pg_constraint WHERE conrelid=$1::regclass AND contype='c'", relation)
        for check in checks:
            await database.owner.execute(f'ALTER TABLE {relation} DROP CONSTRAINT "{check["conname"]}"')
        columns = await database.owner.fetch("""SELECT column_name,udt_name FROM information_schema.columns
            WHERE table_schema=$1 AND table_name=$2 AND is_generated='NEVER'
            AND (is_nullable='NO' OR column_name='tenant_id') ORDER BY ordinal_position""", table["schema"], table["name"])
        names = ",".join('"' + c["column_name"] + '"' for c in columns)
        insert = f'INSERT INTO {relation} ({names}) VALUES ({",".join("$"+str(i+1) for i in range(len(columns)))})'
        await database.owner.execute("SET session_replication_role=replica")
        try:
            for serial, tenant in enumerate((a, b), 101):
                await database.owner.execute(insert, *(sample(c, tenant, serial) for c in columns))
        finally:
            await database.owner.execute("SET session_replication_role=origin")
        await database.owner.execute(f"ALTER TABLE {relation} DISABLE TRIGGER USER")
        fresh = await asyncpg.connect(database.tenant_url)
        try:
            assert await fresh.fetchval("SELECT current_setting('app.tenant_id',true)") is None
            assert await fresh.fetchval(f"SELECT count(*) FROM {relation}") == 0
        finally:
            await fresh.close()
        async with database.raw.acquire() as conn:
            assert await conn.fetchval(f"SELECT count(*) FROM {relation}") == 0
        with tenant_scope(a):
            async with database.pool.acquire() as conn:
                assert await conn.fetchval(f"SELECT count(*) FROM {relation}") == 1
                assert await conn.fetchval(f"SELECT tenant_id FROM {relation}") == a
                assert await conn.execute(f"DELETE FROM {relation} WHERE tenant_id=$1", b) == "DELETE 0"
                assert await conn.execute(f"UPDATE {relation} SET tenant_id=$1 WHERE tenant_id=$2", a, b) == "UPDATE 0"
                for query, args in [(insert, [sample(c, b, 103) for c in columns]),
                                    (f"UPDATE {relation} SET tenant_id=$1 WHERE tenant_id=$2", [b, a])]:
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        async with conn.transaction():
                            await conn.execute(query, *args)
        async with database.raw.acquire() as reused:
            async with reused.transaction():
                await reused.execute("SELECT set_config('app.tenant_id','',true)")
                assert await reused.fetchval(f"SELECT count(*) FROM {relation}") == 0
        with tenant_scope(b):
            assert await database.pool.fetchval(f"SELECT count(*) FROM {relation}") == 1
        assert await database.founder.fetchval(f"SELECT count(*) FROM {relation} WHERE tenant_id=ANY($1::uuid[])", [a, b]) == 2
    print(f"RLS matrix: {len(database.tables)} actual tables across {len({r['schema'] for r in database.tables})} schemas; read/insert/update/delete, missing/empty/reused, founder bypass passed")


@pytest.mark.asyncio
async def test_transaction_scope_rollback_and_concurrency(database):
    a, b = uuid4(), uuid4()
    async def current(tenant):
        with tenant_scope(tenant):
            async with database.pool.acquire() as conn:
                await asyncio.sleep(0)
                return await conn.fetchval("SELECT current_setting('app.tenant_id',true)")
    assert await asyncio.gather(current(a), current(b)) == [str(a), str(b)]
    with pytest.raises(RuntimeError):
        with tenant_scope(a):
            async with database.pool.acquire() as conn:
                assert await conn.fetchval("SELECT current_setting('app.tenant_id',true)") == str(a)
                raise RuntimeError("offline rollback probe")
    assert await database.pool.fetchval("SELECT current_setting('app.tenant_id',true)") == ""


def test_migrations_are_never_in_startup():
    assert len(list(MIGRATIONS.glob("*.sql"))) == 13
    for path in [ROOT / "tank/schema.sql", ROOT / "tank/main.py", ROOT / "agents/_chassis/chassis/app.py"]:
        assert "migrations/tenant_rls" not in path.read_text()


def test_protected_routing_bodies_remain_unchanged():
    baseline = subprocess.check_output(["git", "show", "87610e4:tank/main.py"], cwd=ROOT, text=True)
    before = {n.name: n for n in ast.parse(baseline).body if isinstance(n, ast.AsyncFunctionDef)}
    after = {n.name: n for n in ast.parse((ROOT / "tank/main.py").read_text()).body if isinstance(n, ast.AsyncFunctionDef)}
    for name in ("run_route", "_cache_read", "_cache_write", "_run_task"):
        assert [ast.dump(n) for n in after[name].body] == [ast.dump(n) for n in before[name].body], name


@pytest.mark.asyncio
async def test_tank_route_cache_task_and_accepted_http_tenant(database, monkeypatch):
    from test_agent_chassis import TANK

    a, b, task_id = uuid4(), uuid4(), uuid4()
    seen = []
    class TrackedPool(TenantPool):
        @asynccontextmanager
        async def acquire(self, **kwargs):
            async with super().acquire(**kwargs) as conn:
                seen.append(await conn.fetchval("SELECT current_setting('app.tenant_id',true)"))
                yield conn

    monkeypatch.setattr(TANK, "_pool", TrackedPool(database.raw))
    monkeypatch.setattr(TANK, "_admin_pool", database.founder)
    request = TANK.RouteRequest(tenant_id=a, task_type="offline.rls", messages=[{"role": "user", "content": "Offline deterministic probe"}])
    class StopBeforeExecution(Exception):
        pass
    async def preflight(req, task):
        assert await TANK.pool().fetchval("SELECT current_setting('app.tenant_id',true)") == str(a)
        raise StopBeforeExecution()
    monkeypatch.setattr(TANK, "_check_route_task", preflight)
    with pytest.raises(StopBeforeExecution):
        await TANK.run_route(request)
    assert await TANK._cache_read(request, {"cache_scope": "tenant"}, ("context", "exact", "form")) is None
    await database.owner.execute("INSERT INTO tank.tasks(id,tenant_id,title,input) VALUES($1,$2,'Offline task','[]')", task_id, a)
    async def code_only(req, **kwargs):
        assert await TANK.pool().fetchval("SELECT current_setting('app.tenant_id',true)") == str(a)
        return SimpleNamespace(content="Offline code result", ledger_id=None)
    monkeypatch.setattr(TANK, "run_route", code_only)
    await TANK._run_task(task_id, request)
    assert await database.owner.fetchval("SELECT status FROM tank.tasks WHERE id=$1", task_id) == "done"
    for tenant in (a, b):
        await database.owner.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,rung,cost_usd)
            VALUES($1,'base','offline.rls','code',3,0)""", tenant)
    async def accepted_workspace():
        return None
    TANK.app.dependency_overrides[TANK.require_key] = accepted_workspace
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=TANK.app), base_url="http://offline") as client:
            response = await client.get("/v1/ledger/summary", params={"tenant_id": str(a)})
            assert response.status_code == 200, response.text
            assert response.json()["calls"] == 1
            assert response.json()["tenant_id"] == str(a)
    finally:
        TANK.app.dependency_overrides.clear()
    assert seen and set(seen) == {str(a)}
    assert await database.pool.fetchval("SELECT count(*) FROM tank.ledger") == 0


@pytest.mark.asyncio
async def test_batch_discovery_then_persisted_owner_execution(database, monkeypatch):
    from test_agent_chassis import TANK

    a, b = uuid4(), uuid4()
    monkeypatch.setattr(TANK, "_pool", database.pool)
    monkeypatch.setattr(TANK, "_admin_pool", database.founder)
    for tenant in (a, b):
        await database.owner.execute("""INSERT INTO tank.batches(id,tenant_id,region,task_type,model,count,provider)
            VALUES($1,$2,$3,'offline.rls','offline-code',1,'openai')""", uuid4(), tenant, TANK.box_region())
    owners = []
    async def offline_process(conn, batch):
        owners.append(batch["tenant_id"])
        assert await conn.fetchval("SELECT current_setting('app.tenant_id',true)") == str(batch["tenant_id"])
        assert await conn.fetchval("SELECT count(*) FROM tank.batches") == 1
        await conn.execute("UPDATE tank.batches SET status='completed' WHERE id=$1", batch["id"])
    monkeypatch.setattr(TANK, "_process_batch", offline_process)
    await TANK.process_batches_once()
    assert set(owners) == {a, b}
    assert await database.owner.fetchval("SELECT count(*) FROM tank.batches WHERE status='completed'") == 2


@pytest.mark.asyncio
async def test_chassis_accepts_job_tenant_and_worker_keeps_it(database):
    from chassis.app import create_app
    from chassis.tenant_db import TenantPool as RoomPool
    from chassis.worker import job_loop

    a, b = uuid4(), uuid4()
    room_raw = await asyncpg.create_pool(database.tenant_url, min_size=1, max_size=3)
    room_pool = RoomPool(room_raw)
    async def handler(ctx):
        assert await room_pool.fetchval("SELECT current_setting('app.tenant_id',true)") == str(a)
        assert await room_pool.fetchval("SELECT count(*) FROM agent_template.jobs") == 1
        return {"tenant": ctx.tenant_id}
    app = create_app("template", {"offline": handler})
    app.state.pool = room_pool
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        queued = await client.post("/jobs", json={"tenant_id": str(a), "kind": "offline"})
        assert queued.status_code == 201, queued.text
        job_id = UUID(queued.json()["id"])
        assert (await client.get(f"/jobs/{job_id}", params={"tenant_id": str(b)})).status_code == 404
    await database.owner.execute("""INSERT INTO agent_template.jobs(tenant_id,kind,run_at)
        VALUES($1,'offline',now()+interval '1 day')""", b)
    task = asyncio.create_task(job_loop(room_pool, "template", {"offline": handler},
        lambda job: SimpleNamespace(tenant_id=str(job["tenant_id"])), discovery_pool=database.founder))
    try:
        for _ in range(300):
            if await database.owner.fetchval("SELECT status FROM agent_template.jobs WHERE id=$1", job_id) == "done":
                break
            await asyncio.sleep(0.01)
        row = await database.owner.fetchrow("SELECT status,result FROM agent_template.jobs WHERE id=$1", job_id)
        assert row["status"] == "done"
        assert json.loads(row["result"])["tenant"] == str(a)
        assert await database.owner.fetchval("SELECT status FROM agent_template.jobs WHERE tenant_id=$1", b) == "queued"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert await room_pool.fetchval("SELECT count(*) FROM agent_template.jobs") == 0
    await room_raw.close()


@pytest.mark.asyncio
async def test_rig_authenticated_bootstrap_then_tenant_and_reset(database):
    from fastapi import FastAPI, Request
    sys.path.insert(0, str(ROOT / "agents/rig"))
    from chassis.tenant_db import TenantPool as RoomPool
    from rigbox.api import _auth, mount
    from rigbox.service import Service, hash_key
    from rigbox.store import PgStore

    a, b = uuid4(), uuid4()
    # Synthetic local fixture credentials, never sent outside ASGITransport.
    first, second = "rk_pub_offline_rls_first", "rk_pub_offline_rls_second"
    for tenant, key in ((a, first), (b, second)):
        await database.owner.execute("INSERT INTO agent_rig.keys(tenant_id,key_hash,kind,origins) VALUES($1,$2,'publishable',ARRAY['https://offline.invalid'])", tenant, hash_key(key))
    pool = RoomPool(database.raw, database.founder)
    store = PgStore(pool)
    assert await pool.fetchval("SELECT count(*) FROM agent_rig.keys") == 0
    assert (await store.key(hash_key(first)))["tenant_id"] == str(a)
    app = FastAPI()
    mount(app)
    app.state.rig = Service(store)

    @app.get("/offline-rls")
    async def accepted(request: Request):
        owner = await _auth(request)
        return {"tenant": owner["tenant_id"], "setting": await pool.fetchval("SELECT current_setting('app.tenant_id',true)"), "keys": await pool.fetchval("SELECT count(*) FROM agent_rig.keys")}

    @app.get("/offline-unset")
    async def unset():
        return {"keys": await pool.fetchval("SELECT count(*) FROM agent_rig.keys")}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        for tenant, key in ((a, first), (b, second)):
            response = await client.get("/offline-rls", headers={"X-Rig-Key": key, "Origin": "https://offline.invalid"})
            assert response.status_code == 200, response.text
            assert response.json() == {"tenant": str(tenant), "setting": str(tenant), "keys": 1}
            assert (await client.get("/offline-unset")).json() == {"keys": 0}
        assert (await client.get("/offline-rls", headers={"X-Rig-Key": first, "Origin": "https://wrong.invalid"})).status_code == 403
        assert (await client.get("/offline-unset")).json() == {"keys": 0}


@pytest.mark.asyncio
async def test_repeatable_read_options_preserved(database):
    tenant = uuid4()
    for pool in (database.pool,):
        with tenant_scope(tenant):
            async with pool.acquire(isolation="repeatable_read", readonly=True) as conn:
                assert await conn.fetchval("SHOW transaction_isolation") == "repeatable read"
                assert await conn.fetchval("SHOW transaction_read_only") == "on"
                assert await conn.fetchval("SELECT current_setting('app.tenant_id',true)") == str(tenant)
    assert await database.pool.fetchval("SELECT current_setting('app.tenant_id',true)") == ""


@pytest.mark.asyncio
async def test_worker_diagnostics_with_real_scoped_founder_pool(database, monkeypatch):
    """The real route must configure the outer scoped transaction, not a savepoint."""
    from fastapi import FastAPI
    import controls
    import workers_status
    from tenant_db import bind_tenant_endpoints

    monkeypatch.setenv("TANK_API_KEY", "offline-workspace-key")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-one")
    pool = TenantPool(database.raw, database.founder)
    monkeypatch.setattr(workers_status, "db", lambda: pool)
    at = datetime(2026, 10, 30, 18, 30, tzinfo=timezone.utc)
    await database.owner.execute(
        "INSERT INTO tank.workers_controls(tenant_id,name,value,updated_by,updated_at) "
        "VALUES($1,'workers_paused',true,'founder-one',$2)", controls.PLATFORM, at,
    )
    await database.owner.execute(
        "INSERT INTO tank.control_log(tenant_id,name,by_user,old_value,new_value,at) "
        "VALUES($1,'workers_paused','founder-one',false,true,$2)", controls.PLATFORM, at,
    )
    builds = []
    for tenant in (uuid4(), uuid4()):
        thread, build = uuid4(), uuid4()
        builds.append(build)
        await database.owner.execute(
            "INSERT INTO tank.command_threads(thread_id,tenant_id,user_id,title,state) "
            "VALUES($1,$2,'offline-user','offline-title','{}'::jsonb)", thread, tenant,
        )
        await database.owner.execute(
            "INSERT INTO tank.command_builds(build_id,thread_id,tenant_id,user_id,brief_markdown,status) "
            "VALUES($1,$2,$3,'offline-user','offline-brief','queued')", build, thread, tenant,
        )
    app = FastAPI()
    app.include_router(workers_status.founder_router)
    bind_tenant_endpoints(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        denied = await client.get("/v1/controls/workers", headers={"x-tank-key": "offline-workspace-key", "x-tervory-admin": "other"})
        assert denied.status_code == 404
        response = await client.get("/v1/controls/workers", headers={"x-tank-key": "offline-workspace-key", "x-tervory-admin": "founder-one"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workers_paused"] is True
    assert body["pause_control"] == {"updated_by": "founder-one", "updated_at": at.isoformat()}
    assert body["last_pause_change"] == {"by_user": "founder-one", "old_value": False, "new_value": True, "at": at.isoformat()}
    assert body["build_counts"] == {"queued": 2, "running": 0, "awaiting_review": 0}
    assert await database.owner.fetchval("SELECT count(*) FROM tank.command_builds WHERE build_id=ANY($1::uuid[]) AND status='queued'", builds) == 2
    assert await database.raw.fetchval("SHOW transaction_read_only") == "off"


@pytest.mark.asyncio
async def test_base_queue_uses_persisted_owner_after_admin_discovery(database, monkeypatch):
    import importlib.util
    sys.path.insert(0, str(ROOT / "agents/base"))
    spec = importlib.util.spec_from_file_location("rls_base_room", ROOT / "agents/base/room.py")
    room = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(room)
    from chassis.tenant_db import TenantPool as RoomPool
    pool = RoomPool(database.raw, database.founder)
    a, b = uuid4(), uuid4()
    for tenant in (a, b):
        await database.owner.execute("INSERT INTO agent_base.tasks(id,tenant_id,agent,task_type,title,input) VALUES($1,$2,'base','base.enrich','offline',$3::jsonb)", uuid4(), tenant, json.dumps({"tenant_id": str(b)}))
    finished = asyncio.Event()
    observed = []
    class Skills:
        async def pin(self, *args):
            return {}, {}
        def bind(self, *args):
            return None
    async def run_batch(pool, task_id, cfg, call):
        setting = await pool.fetchval("SELECT current_setting('app.tenant_id',true)")
        assert setting == cfg["tenant_id"]
        assert await pool.fetchval("SELECT count(*) FROM agent_base.tasks") == 1
        observed.append(setting)
        await pool.execute("UPDATE agent_base.tasks SET status='done' WHERE id=$1", task_id)
        if len(observed) == 2:
            finished.set()
    monkeypatch.delenv("BASE_BRAIN_URL", raising=False)
    monkeypatch.setattr(room, "_run_batch", run_batch)
    monkeypatch.setattr(room, "models_paused", lambda: False)
    worker = asyncio.create_task(room.base_loop(pool, Skills()))
    try:
        await asyncio.wait_for(finished.wait(), timeout=5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert set(observed) == {str(a), str(b)}
    assert await pool.fetchval("SELECT count(*) FROM agent_base.tasks") == 0


@pytest.mark.asyncio
async def test_included_router_explicit_tenant_wins_body_and_body_cannot_select_admin(database):
    from fastapi import APIRouter, FastAPI
    from pydantic import BaseModel
    from tenant_db import bind_tenant_endpoints
    a, b = uuid4(), uuid4()
    for tenant in (a, b):
        await database.owner.execute("INSERT INTO agent_rig.keys(tenant_id,key_hash,kind) VALUES($1,$2,'publishable')", tenant, str(uuid4()))
    class Body(BaseModel):
        tenant_id: UUID
        founder: bool = True
    child, parent, app = APIRouter(), APIRouter(), FastAPI()
    @child.post("/scope")
    async def accepted(tenant_id: UUID, body: Body):
        return {"tenant": await database.pool.fetchval("SELECT current_setting('app.tenant_id',true)"), "keys": await database.pool.fetchval("SELECT count(*) FROM agent_rig.keys")}
    parent.include_router(child, prefix="/child")
    app.include_router(parent, prefix="/parent")
    bind_tenant_endpoints(app)
    bind_tenant_endpoints(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        response = await client.post("/parent/child/scope", params={"tenant_id": str(a)}, json={"tenant_id": str(b), "founder": True})
        assert response.status_code == 200, response.text
        assert response.json() == {"tenant": str(a), "keys": 1}
    assert await database.pool.fetchval("SELECT count(*) FROM agent_rig.keys") == 0


@pytest.mark.asyncio
async def test_durable_statement_checkout_keeps_commits_and_explicit_rollback(database):
    a, b = uuid4(), uuid4()
    for tenant in (a, b):
        await database.owner.execute("INSERT INTO tank.offpeak_jobs(tenant_id,region,request,policy) VALUES($1,'us-east','{}','{}')", tenant)
    with pytest.raises(RuntimeError, match="after durable marker"):
        with tenant_scope(a):
            async with database.pool.acquire(autocommit=True) as conn:
                assert await conn.fetchval("SELECT count(*) FROM tank.offpeak_jobs") == 1
                await conn.execute("UPDATE tank.offpeak_jobs SET status='dispatching'")
                # A separate connection must see this BEFORE checkout/provider work ends.
                assert await database.owner.fetchval("SELECT status FROM tank.offpeak_jobs WHERE tenant_id=$1", a) == "dispatching"
                with pytest.raises(ValueError, match="rollback explicit unit"):
                    async with conn.transaction():
                        await conn.execute("UPDATE tank.offpeak_jobs SET error='must roll back'")
                        raise ValueError("rollback explicit unit")
                assert await conn.fetchval("SELECT error FROM tank.offpeak_jobs") is None
                raise RuntimeError("after durable marker")
    assert await database.owner.fetchval("SELECT status FROM tank.offpeak_jobs WHERE tenant_id=$1", a) == "dispatching"
    assert await database.owner.fetchval("SELECT status FROM tank.offpeak_jobs WHERE tenant_id=$1", b) == "queued"
    assert await database.pool.fetchval("SELECT count(*) FROM tank.offpeak_jobs") == 0


@pytest.mark.asyncio
async def test_offpeak_admin_discovery_then_owner_and_durable_marker(database, monkeypatch):
    from test_agent_chassis import TANK
    import priority_queue
    a, b = uuid4(), uuid4()
    monkeypatch.setattr(TANK, "_pool", database.pool)
    monkeypatch.setattr(TANK, "_admin_pool", database.founder)
    for tenant in (a, b):
        await database.owner.execute("INSERT INTO tank.offpeak_jobs(tenant_id,region,request,policy) VALUES($1,$2,'{}','{}')", tenant, TANK.box_region())
    seen = []
    async def stop_after_marker(tank, conn, job):
        setting = await conn.fetchval("SELECT current_setting('app.tenant_id',true)")
        assert setting == str(job["tenant_id"])
        assert await conn.fetchval("SELECT count(*) FROM tank.offpeak_jobs") == 1
        await conn.execute("UPDATE tank.offpeak_jobs SET status='dispatching' WHERE id=$1", job["id"])
        assert await database.owner.fetchval("SELECT status FROM tank.offpeak_jobs WHERE id=$1", job["id"]) == "dispatching"
        seen.append(setting)
        raise RuntimeError("Simulated interrupted provider boundary; no provider called")
    monkeypatch.setattr(priority_queue, "_process", stop_after_marker)
    await priority_queue.process_once(TANK)
    assert set(seen) == {str(a), str(b)}
    assert await database.owner.fetchval("SELECT count(*) FROM tank.offpeak_jobs WHERE status='dispatching'") == 2
    assert await database.pool.fetchval("SELECT count(*) FROM tank.offpeak_jobs") == 0


@pytest.mark.asyncio
async def test_merged_radix_domain_route_uses_accepted_tenant_without_scan(database, monkeypatch):
    from fastapi import FastAPI
    from chassis.tenant_db import TenantPool as RoomPool, bind_tenant_endpoints
    sys.path.insert(0, str(ROOT / "agents/radix"))
    import passive_routes
    a, b = uuid4(), uuid4()
    monkeypatch.setenv("TANK_KEY", "offline-rls-room")
    app = FastAPI()
    app.state.pool = RoomPool(database.raw, database.founder)
    passive_routes.attach(app)
    bind_tenant_endpoints(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        response = await client.post("/passive/domains", json={"tenant_id": str(a), "domain": "offline.invalid"}, headers={"X-Tank-Key": "offline-rls-room", "X-Tervory-Tenant": str(a)})
        assert response.status_code == 201, response.text
        assert response.json()["tenant_id"] == str(a)
    from chassis.tenant_db import tenant_scope as room_scope
    with room_scope(a):
        assert await app.state.pool.fetchval("SELECT count(*) FROM agent_radix.passive_domains") == 1
    with room_scope(b):
        assert await app.state.pool.fetchval("SELECT count(*) FROM agent_radix.passive_domains") == 0
    assert await app.state.pool.fetchval("SELECT count(*) FROM agent_radix.passive_domains") == 0


@pytest.mark.asyncio
async def test_radix_gateway_scopes_lease_and_admin_reaps_expired_owner(database, monkeypatch):
    from fastapi import FastAPI
    sys.path.insert(0, str(ROOT / "agents/radix"))
    import passive_gateway as gateway
    a, b, expired, pending = uuid4(), uuid4(), uuid4(), uuid4()
    for tenant in (a, b):
        await database.owner.execute("INSERT INTO agent_radix.passive_domains(tenant_id,domain,challenge) VALUES($1,'offline.invalid','public-offline-proof')", tenant)
    await database.owner.execute("""INSERT INTO agent_radix.passive_scans(tenant_id,id,domain,target,artifact,status,lease_until)
        VALUES($1,$2,'offline.invalid','https://offline.invalid/','commit:offline','running',now()-interval '1 minute')""", a, expired)
    await database.owner.execute("""INSERT INTO agent_radix.passive_scans(tenant_id,id,domain,target,artifact)
        VALUES($1,$2,'offline.invalid','https://offline.invalid/','commit:offline')""", b, pending)
    monkeypatch.setenv("DATABASE_URL", database.tenant_url)
    monkeypatch.setenv("RADIX_GATEWAY_ADMIN_DATABASE_URL", database.founder_url)
    monkeypatch.setenv("RADIX_GATEWAY_RLS_ADMIN_ROLE", await database.founder.fetchval("SELECT current_user"))
    monkeypatch.setattr(gateway, "private_bind_address", lambda: "127.0.0.1")
    class NoSocketServer:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            return self
        def close(self):
            pass
    app = FastAPI()
    async with gateway.lifespan(app):
        assert await database.owner.fetchval("SELECT status FROM agent_radix.passive_scans WHERE id=$1", expired) == "error"
        async def accepted_local_proof(domain, challenge):
            assert domain == "offline.invalid" and challenge == "public-offline-proof"
            assert await app.state.pool.fetchval("SELECT current_setting('app.tenant_id',true)") == str(b)
            assert await app.state.pool.fetchval("SELECT count(*) FROM agent_radix.passive_scans") == 1
            return True
        app.state.lease.check = accepted_local_proof
        app.state.lease.server = NoSocketServer
        assert await app.state.lease.start(b, pending) == {"ready": True}
        assert await app.state.pool.fetchval("SELECT count(*) FROM agent_radix.passive_scans") == 0
        await app.state.lease.release(b, pending)
        assert await database.owner.fetchval("SELECT status FROM agent_radix.passive_scans WHERE id=$1", pending) == "error"
