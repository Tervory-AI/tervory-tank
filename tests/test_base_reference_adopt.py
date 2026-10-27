"""Reference adoption regressions: real SQL and the actual FFL projection route."""
from datetime import datetime, timezone
import json

import httpx
import pytest
from fastapi import FastAPI

from agents.base.engines.ffl.reference import project, register
from base_product import build_router
from base_product_fixtures import TENANT, OTHER, raw
from base_reference_status import ReferenceFailure, check_reference
from base_repository import BaseStore, encoded
from test_base_database import database as postgres_database
from vendor_meter import PLATFORM

database = postgres_database


def short_headers(row, *, spaced=False):
    return {(key.lower().replace("premise_", "prem_").replace("_", " ") if spaced else
             key.lower().replace("premise_", "prem_")): value for key, value in row.items()}


def seed_rows():
    newer = short_headers(raw(street="2 New Fixture Road"))
    newer["license_name"] = "Newest Fixture Business"
    return [(raw(), 15), (newer, 16), (short_headers(raw(2, "CA", "07"), spaced=True), 15),
            (raw(3, "NY", "03"), 15)]


async def seed(conn):
    ids = []
    await conn.execute("SET LOCAL session_replication_role='replica'")
    for row, day in seed_rows():
        at = datetime(2026, 10, day, tzinfo=timezone.utc)
        ids.append(await conn.fetchval("""INSERT INTO base.records(tenant_id,raw,created_at,updated_at)
            VALUES($1,$2::jsonb,$3,$3) RETURNING id""", PLATFORM, encoded(row), at))
    await conn.execute("INSERT INTO base.records(tenant_id,raw) VALUES($1,$2::jsonb)", OTHER, encoded(raw(99)))
    await conn.execute("SET LOCAL session_replication_role='origin'")
    return ids


@pytest.mark.parametrize("spaced", [False, True])
def test_atf_field_spellings_have_identical_projections(spaced):
    expected = project(raw())
    actual = project(short_headers(raw(), spaced=spaced))
    assert {key: value for key, value in actual.items() if key != "raw"} == {
        key: value for key, value in expected.items() if key != "raw"}


@pytest.mark.asyncio
async def test_duplicate_adoption_keeps_newest_and_exposes_count(database, monkeypatch):
    conn, rt = database
    ids = await seed(conn)
    before = [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")]
    monkeypatch.setenv("TANK_KEY", "local-room-fixture")
    agent = FastAPI()
    register(agent)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent), base_url="http://fixture-room") as http:
        rt._http = http
        store = BaseStore(rt)
        await store.adopt()
        await store.adopt()
        file = await store.latest_file()
        assert file["row_count"] == 3 and file["duplicate_count"] == 1 and file["adopted"]
        assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_files WHERE owner_id=$1", PLATFORM) == 1
        entry = await conn.fetchrow("SELECT * FROM tank.base_reference_entries WHERE licence_key='5-74-00001'")
        assert entry["legacy_record_id"] == ids[1] and entry["raw"] is None
        assert json.loads(entry["address"])["street"] == "2 New Fixture Road"
        assert [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")] == before
        app = FastAPI()
        app.include_router(build_router(rt, background=False))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture",
                                    headers={"X-Tank-Key": "local-fixture"}) as client:
            for tenant in (TENANT, OTHER):
                response = await client.get("/v1/base-product/reference", params={"tenant_id": str(tenant)})
                assert response.status_code == 200
                ref = response.json()
                assert ref["total_all"] == 3 and ref["selected"] == 2 and ref["collectors"] == 1
                assert ref["duplicate_count"] == 1 and ref["refresh"]["status"] == "adopted"
                assert any(row["name"] == "Newest Fixture Business" for row in ref["rows"])


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 422, 500, 503])
async def test_service_failure_is_logged_and_visible_before_a_file_exists(database, caplog, status):
    conn, rt = database
    await seed(conn)
    store = BaseStore(rt)
    # A recent check must not suppress the real failure of the next adoption.
    await store.reference_check("current")
    private = "PRIVATE-RESPONSE-CONTENT"
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(status, text=private))) as http:
        rt._http = http
        await check_reference(store)
    expected = f"The reference could not be loaded: The Base reference service returned HTTP {status}."
    saved = await conn.fetchrow("SELECT * FROM tank.base_reference_checks WHERE owner_id=$1", PLATFORM)
    assert saved["message"] == expected and saved["status"] == "unavailable"
    assert expected in caplog.text and private not in caplog.text
    from base_queries import reference_page
    response = await reference_page(store, [], [], False, 0, 50)
    assert response["file"] is None and response["total_all"] == 0
    assert response["refresh"]["message"] == expected and private not in encoded(response)


@pytest.mark.asyncio
@pytest.mark.parametrize("saved_rows", [False, True])
async def test_connection_failure_has_safe_durable_reason_with_or_without_seed(database, caplog, saved_rows):
    conn, rt = database
    store = BaseStore(rt)
    if saved_rows:
        await seed(conn)
    def unavailable(request):
        raise httpx.ConnectError("PRIVATE-CONNECTION-CONTENT", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as http:
        rt._http = http
        await check_reference(store)
    saved = await conn.fetchval("SELECT message FROM tank.base_reference_checks WHERE owner_id=$1", PLATFORM)
    assert saved == "The reference could not be loaded: The Base reference service could not be reached."
    assert saved in caplog.text and "PRIVATE-CONNECTION-CONTENT" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("background", [True, False])
async def test_block_status_survives_later_failures(database, background):
    conn, rt = database
    await seed(conn)
    store = BaseStore(rt)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(422, json={
        "detail": "blocked: https://www.atf.gov/private?tracking=PRIVATE-BLOCK-CONTENT"}))) as http:
        rt._http = http
        if background:
            await check_reference(store)
        else:
            with pytest.raises(ReferenceFailure):
                await store.engine({"since": "2026-09-01"})
    await store.reference_check("unavailable", "An unrelated failure.")
    check = await conn.fetchrow("SELECT status,message FROM tank.base_reference_checks WHERE owner_id=$1", PLATFORM)
    assert check["status"] == "blocked" and "HTTP 422" in check["message"]
    assert "PRIVATE-BLOCK-CONTENT" not in check["message"] and not await store.due_refresh()


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [
    (b"PRIVATE-RESPONSE-CONTENT", "The Base reference service returned unreadable data (HTTP 200)."),
    (b"[]", "The Base reference service returned an unexpected response (HTTP 200)."),
    (b'{"rows":[]}', "The reference service did not return every submitted licence."),
])
async def test_bad_success_response_is_safe_and_does_not_install_partial_file(database, caplog, body, expected):
    conn, rt = database
    await seed(conn)
    store = BaseStore(rt)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=body))) as http:
        rt._http = http
        await check_reference(store)
    assert await store.latest_file() is None
    message = await conn.fetchval("SELECT message FROM tank.base_reference_checks WHERE owner_id=$1", PLATFORM)
    assert message == "The reference could not be loaded: " + expected
    assert message in caplog.text and "PRIVATE-RESPONSE-CONTENT" not in caplog.text


@pytest.mark.asyncio
async def test_duplicates_across_projection_chunks_keep_newest(database):
    conn, rt = database
    await conn.execute("SET LOCAL session_replication_role='replica'")
    # 2,001 source rows put the oldest duplicate in the second projection chunk.
    await conn.executemany("INSERT INTO base.records(tenant_id,raw,created_at,updated_at) VALUES($1,$2::jsonb,$3,$3)",
                          [(PLATFORM, encoded(raw(i)), datetime(2026, 10, 16, tzinfo=timezone.utc)) for i in range(1, 2001)] +
                          [(PLATFORM, encoded(raw(street="Old duplicate")), datetime(2026, 10, 15, tzinfo=timezone.utc))])
    await conn.execute("SET LOCAL session_replication_role='origin'")
    chunks = []
    store = BaseStore(rt)
    async def project_chunk(payload):
        chunks.append(len(payload["rows"]))
        return {"rows": [project(row) for row in payload["rows"]]}
    store.engine = project_chunk
    await store.adopt()
    file = await store.latest_file()
    assert chunks == [2000, 1] and file["row_count"] == 2000 and file["duplicate_count"] == 1
    assert json.loads(await conn.fetchval("SELECT address FROM tank.base_reference_entries WHERE licence_key='5-74-00001'"))["street"] == "1 Fixture Road"
