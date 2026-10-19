"""Private intake authentication, rejection before Tank, and tenant-scoped reads."""
from __future__ import annotations

import os
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
from fastapi import FastAPI

from test_radix_business import ENGINE, OTHER, ROOT, fixture, load_module

ROUTES = load_module("rx5_verify_routes", ROOT / "agents" / "radix" / "verify" / "routes.py")


class Store:
    def __init__(self):
        self.rows = {}
        self.calls = []

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self):
        yield

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        if sql.startswith("INSERT INTO agent_radix.business_runs"):
            self.rows[(args[0], args[1], args[2])] = args[4]

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        row = self.rows.get(tuple(args))
        return {"result": row} if row else None


class BusinessRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"TANK_KEY": "rx5_example_room_key", "TANK_REGION": "us-east"})
        self.env.start()
        self.app = FastAPI()
        self.store = Store()
        self.app.state.pool = self.store

        async def run_skill(tenant, skill, body):
            return ENGINE.analyse(skill.removeprefix("radix."), body, tenant)

        self.app.state.tank = SimpleNamespace(run_skill=AsyncMock(side_effect=run_skill))
        ROUTES.attach(self.app)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://radix-room")
        self.headers = {"X-Tank-Key": "rx5_example_room_key"}

    async def asyncTearDown(self):
        await self.client.aclose()
        self.env.stop()

    async def test_authenticated_roundtrip_and_other_tenant_cannot_read(self):
        payload = fixture()
        response = await self.client.post("/verify/business_risk", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        out = response.json()
        run_id = out["id"]
        read = await self.client.get(f"/verify/runs/{run_id}", params={"tenant_id": payload["tenant_id"]}, headers=self.headers)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.json(), out)
        read = await self.client.get(f"/verify/runs/{run_id}", params={"tenant_id": OTHER}, headers=self.headers)
        self.assertEqual(read.status_code, 404)
        self.app.state.tank.run_skill.assert_awaited_once_with(payload["tenant_id"], "radix.business_risk", payload)
        inserts = [args for sql, args in self.store.calls if sql.startswith("INSERT")]
        self.assertEqual(len(inserts), 1 + len(payload["sources"]))
        self.assertTrue(all(row[0] == UUID(payload["tenant_id"]) for row in inserts))

    async def test_missing_wrong_or_unconfigured_key_never_calls_tank_or_database(self):
        for key in (None, "wrong"):
            response = await self.client.post("/verify/business_risk", json=fixture(), headers={"X-Tank-Key": key} if key else {})
            self.assertEqual(response.status_code, 401)
        with patch.dict(os.environ, {"TANK_KEY": ""}):
            response = await self.client.post("/verify/business_risk", json=fixture(), headers=self.headers)
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.store.calls, [])
        self.app.state.tank.run_skill.assert_not_awaited()

    async def test_every_route_rejects_person_keys_before_tank_or_database(self):
        for skill in ROUTES.SKILLS:
            for value in ("Jane Example", "jane@example.test", "+27 82 555 0100", "0825550100"):
                for kind in ("company_name", "domain", "registration_number", "licence_number", "business_id", "email", "phone", "name"):
                    with self.subTest(skill=skill, kind=kind, value=value):
                        payload = fixture()
                        payload["lookup"] = {"kind": kind, "value": value}
                        response = await self.client.post(f"/verify/{skill}", json=payload, headers=self.headers)
                        self.assertEqual(response.status_code, 400)
                        self.assertNotIn(value, response.text)
        self.assertEqual(self.store.calls, [])
        self.app.state.tank.run_skill.assert_not_awaited()

    async def test_bad_shape_wrong_region_and_oversize_body_never_call_tank(self):
        payload = fixture()
        payload["region"] = "za"
        for body in (payload, [], {"tenant_id": "invalid"}, {**fixture(), "lookup": "Jane Example"}):
            response = await self.client.post("/verify/business_risk", json=body, headers=self.headers)
            self.assertEqual(response.status_code, 400)
        response = await self.client.post("/verify/business_risk", content=b"{" * (ROUTES.MAX_BYTES + 1), headers=self.headers)
        self.assertEqual(response.status_code, 413)
        response = await self.client.post("/verify/business_risk", content=b"{invalid", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.calls, [])
        self.app.state.tank.run_skill.assert_not_awaited()

    async def test_unknown_skill_and_unapproved_or_failed_tank_do_not_store(self):
        response = await self.client.post("/verify/person_search", json=fixture(), headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.app.state.tank.run_skill.side_effect = RuntimeError("unapproved skill")
        response = await self.client.post("/verify/business_risk", json=fixture(), headers=self.headers)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("unapproved skill", response.text)
        self.assertEqual(self.store.calls, [])

    async def test_invalid_cross_tenant_or_cross_region_evidence_never_stored(self):
        for kind in ("sources", "businesses", "accounts"):
            payload = fixture()
            payload[kind][0]["tenant_id"] = OTHER
            response = await self.client.post("/verify/business_risk", json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 400)
        self.app.state.tank.run_skill.side_effect = None
        for result in ({"ok": True, "tenant_id": OTHER, "region": "us-east"}, {"ok": True, "tenant_id": fixture()["tenant_id"], "region": "za"}):
            self.app.state.tank.run_skill.return_value = result
            response = await self.client.post("/verify/business_risk", json=fixture(), headers=self.headers)
            self.assertEqual(response.status_code, 502)
        self.assertEqual(self.store.calls, [])

    async def test_region_read_constraint_and_unknown_result_roundtrip(self):
        payload = fixture()
        payload["lookup"]["value"] = OTHER
        response = await self.client.post("/verify/business_risk", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "unknown")
        with patch.dict(os.environ, {"TANK_REGION": "za"}):
            response = await self.client.get(f'/verify/runs/{response.json()["id"]}', params={"tenant_id": payload["tenant_id"]}, headers=self.headers)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.store.calls[-1][1][-1], "za")

    async def test_lifespan_applies_schema_with_room_connection(self):
        app = FastAPI()
        app.state.pool = SimpleNamespace(acquire=self.store.acquire)
        ROUTES.attach(app)
        async with app.router.lifespan_context(app):
            pass
        self.assertIn("CREATE TABLE IF NOT EXISTS agent_radix.business_runs", self.store.calls[0][0])
        self.assertEqual(len(self.store.calls), 1)
