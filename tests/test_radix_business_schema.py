"""Real Postgres: fresh, reapplied with data, and pinned existing-main + roles.

Uses the same disposable database service CI already provides. Can also run
with stdlib unittest inside an offline container with asyncpg installed.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "radix"))
from chassis.db import ensure_schema  # noqa: E402
from chassis.roles import statements_for  # noqa: E402
from scanlib.store import ensure_findings  # noqa: E402

URL = os.environ.get("RX5_SCHEMA_DATABASE_URL") or os.environ.get("POOL_SCHEMA_DATABASE_URL", "")
SQL = (ROOT / "agents" / "radix" / "schema.sql").read_text()
MAIN = (ROOT / "tests" / "fixtures" / "rx5" / "main_schema.sql").read_text()
TENANT = UUID("10000000-0000-0000-0000-000000000001")
OTHER = UUID("10000000-0000-0000-0000-000000000002")


class BusinessSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not URL:
            self.skipTest("RX5_SCHEMA_DATABASE_URL or POOL_SCHEMA_DATABASE_URL is not set")
        self.admin = await asyncpg.connect(URL)
        self.databases = []

    async def asyncTearDown(self):
        if not hasattr(self, "admin"):
            return
        for name in self.databases:
            await self.admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await self.admin.close()

    async def database(self):
        name = "rx5_" + uuid4().hex
        await self.admin.execute(f'CREATE DATABASE "{name}"')
        self.databases.append(name)
        return await asyncpg.connect(URL, database=name)

    async def assert_repeat_preserves_rows_and_enforces_tenants(self, conn):
        run = uuid4()
        result = {"tenant_id": str(TENANT), "region": "us-east", "ok": True, "score": 0, "factors": []}
        source = {"id": "fixture", "tenant_id": str(TENANT), "url": f"client://{TENANT}/fixture"}
        await conn.execute("INSERT INTO agent_radix.business_runs (tenant_id,id,region,skill,result) VALUES ($1,$2,'us-east','business_risk',$3::jsonb)", TENANT, run, json.dumps(result))
        await conn.execute("INSERT INTO agent_radix.business_sources VALUES ($1,$2,'fixture',$3::jsonb)", TENANT, run, json.dumps(source))
        await conn.execute(SQL)
        await conn.execute(SQL)
        self.assertEqual(await conn.fetchval("SELECT count(*) FROM agent_radix.business_runs WHERE tenant_id=$1 AND id=$2", TENANT, run), 1)
        self.assertEqual(await conn.fetchval("SELECT count(*) FROM agent_radix.business_sources WHERE tenant_id=$1 AND run_id=$2", TENANT, run), 1)
        self.assertIsNone(await conn.fetchrow("SELECT result FROM agent_radix.business_runs WHERE tenant_id=$1 AND id=$2", OTHER, run))
        with self.assertRaises(asyncpg.CheckViolationError):
            await conn.execute("INSERT INTO agent_radix.business_runs (tenant_id,id,region,skill,result) VALUES ($1,$2,'us-east','business_risk',$3::jsonb)", OTHER, run, json.dumps(result))
        with self.assertRaises(asyncpg.CheckViolationError):
            await conn.execute("INSERT INTO agent_radix.business_runs (tenant_id,id,region,skill,result) VALUES ($1,$2,'za','business_risk',$3::jsonb)", TENANT, uuid4(), json.dumps(result))
        with self.assertRaises(asyncpg.CheckViolationError):
            await conn.execute("INSERT INTO agent_radix.business_runs (tenant_id,id,region,skill,result) VALUES ($1,$2,'us-east','business_risk','{}')", TENANT, uuid4())
        with self.assertRaises(asyncpg.ForeignKeyViolationError):
            source["tenant_id"] = str(OTHER)
            await conn.execute("INSERT INTO agent_radix.business_sources VALUES ($1,$2,'fixture',$3::jsonb)", OTHER, run, json.dumps(source))

    async def test_empty_schema_then_reapply_with_existing_rows(self):
        conn = await self.database()
        try:
            await conn.execute("CREATE SCHEMA agent_radix")
            await conn.execute(SQL)
            await self.assert_repeat_preserves_rows_and_enforces_tenants(conn)
        finally:
            await conn.close()

    async def test_existing_main_roles_jobs_and_findings_survive_agent_owned_migration(self):
        conn = await self.database()
        try:
            # Snapshot from main 28e63ff1ba117938a978b3a0c8af68c6d72594d7,
            # never the changed branch schema. Its serial Base sequence is kept.
            self.assertEqual(hashlib.sha256(MAIN.encode()).hexdigest(), "57723380f91ca527173363d401a38dfce5e8f47f80862f6c8dcd76c7e07f6944")
            await conn.execute(MAIN)
            await ensure_schema(conn, "radix")
            await ensure_findings(conn, "agent_radix")
            job = await conn.fetchval("INSERT INTO agent_radix.jobs (tenant_id,kind) VALUES ($1,'ping') RETURNING id", TENANT)
            await conn.execute("INSERT INTO agent_radix.findings (tenant_id,scan_id,tool,severity,file,line,rule,fix) VALUES ($1,$2,'fixture','low','example.py',1,'fixture','example')", TENANT, job)
            for statement in statements_for("radix", "rx5_placeholder_password"):
                await conn.execute(statement)
            # The startup path runs as the existing restricted agent role.
            await conn.execute("SET ROLE agent_radix")
            await conn.execute(SQL)
            await self.assert_repeat_preserves_rows_and_enforces_tenants(conn)
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM agent_radix.jobs WHERE tenant_id=$1 AND id=$2", TENANT, job), 1)
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM agent_radix.findings WHERE tenant_id=$1 AND scan_id=$2", TENANT, job), 1)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await conn.fetchval("SELECT count(*) FROM tank.ledger")
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await conn.fetchval("SELECT count(*) FROM agent_base.records")
            await conn.execute("RESET ROLE")
            self.assertTrue(await conn.fetchval("SELECT to_regclass('agent_base.migration_log_id_seq') IS NOT NULL"))
            await conn.execute(MAIN)  # main's normal restart still works.
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM agent_radix.business_runs WHERE tenant_id=$1", TENANT), 1)
        finally:
            await conn.close()
