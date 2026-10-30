"""Initial ATF download: full saved file, real engine, SQL and failure persistence."""
from contextlib import asynccontextmanager
from datetime import date
import gzip
import hashlib
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from agents.base.engines.ffl import reference
from base_product_fixtures import OTHER, atf_bytes, raw
from base_reference_status import ReferenceFailure, check_reference
from base_repository import BaseStore, PLATFORM, REFERENCE_URL, encoded
from base_queries import reference_page
from test_base_database import database as postgres_database
from test_base_reference_adopt import seed

database = postgres_database
SAVED_FILE = Path(__file__).parent / "fixtures/base-atf/0925-ffl-list-complete.txt.gz"
SAVED_SHA = "ebe50ffac9e53c6e513ba43832ddb913a7190f209b2ae6133d515b3d5eee465c"
FILE_URL = "https://www.atf.gov/resource-center/docs/report/0925-ffl-list-completetxt/download"
LISTING = f'''<html><a href="/0125-ffl-list-complete.txt">January</a>
<a href="{FILE_URL}">September complete list</a>
<a href="/1299-ffl-list-complete.txt">Future</a>
<a href="https://untrusted.example/1025-ffl-list-complete.txt">Not ATF</a>
<a href="/1025-ffl-list-texas.txt">State list</a></html>'''


def saved_file():
    content = gzip.decompress(SAVED_FILE.read_bytes())
    assert hashlib.sha256(content).hexdigest() == SAVED_SHA
    return content


@asynccontextmanager
async def engine(rt, monkeypatch, handler):
    monkeypatch.setenv("TANK_KEY", "local-room-fixture")
    monkeypatch.setattr(reference, "_blocked", False)
    monkeypatch.setattr(reference, "_last_read", 0)
    app = FastAPI()
    reference.register(app)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as public:
        app.state.http = public
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture-room") as room:
            rt._http = room
            yield BaseStore(rt)


@pytest.mark.asyncio
async def test_empty_reference_installs_latest_saved_official_file_once(database, monkeypatch):
    conn, rt = database
    await conn.execute("SET LOCAL session_replication_role='replica'")
    await conn.execute("INSERT INTO base.records(tenant_id,raw) VALUES($1,$2::jsonb)", OTHER, encoded(raw(99)))
    await conn.execute("SET LOCAL session_replication_role='origin'")
    requests = []
    content = saved_file()
    def public(request):
        requests.append(str(request.url))
        assert request.headers["user-agent"] == "Tervory/1.0 (+https://tervory.com)"
        assert "x-tank-key" not in request.headers
        if str(request.url) == REFERENCE_URL:
            return httpx.Response(200, text=LISTING)
        assert str(request.url) == FILE_URL, "Download only the latest eligible complete file"
        return httpx.Response(200, content=content)
    async with engine(rt, monkeypatch, public) as store:
        # The live box has a recent old failure; it must not delay the first download.
        await store.reference_check("unavailable", "The saved reference is missing.")
        await check_reference(store)
        await check_reference(store)
        file = await store.latest_file()
        assert file["published_on"] == date(2025, 9, 1) and file["row_count"] == 77611
        assert file["sha256"] == SAVED_SHA and file["source_url"] == FILE_URL and not file["adopted"]
        assert file["duplicate_count"] == 0
        assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_entries WHERE legacy_record_id IS NULL AND raw IS NOT NULL") == 77611
        assert await conn.fetchval("SELECT count(*) FROM base.records WHERE tenant_id=$1", PLATFORM) == 0
        assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_files") == 1
        page = await reference_page(store, [], [], False, 0, 1)
        assert page["total_all"] == 77611 and page["file"]["source_url"] == FILE_URL
        assert page["refresh"]["status"] == "updated" and page["refresh"]["message"] is None
    assert requests == [REFERENCE_URL, FILE_URL]


@pytest.mark.asyncio
async def test_saved_rows_are_adopted_without_initial_download(database, monkeypatch):
    conn, rt = database
    await seed(conn)
    before = [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")]
    def no_download(request):
        pytest.fail("Existing saved rows must be projected, never downloaded again")
    async with engine(rt, monkeypatch, no_download) as store:
        await store.adopt()
        await store.adopt()
        file = await store.latest_file()
        assert file["adopted"] and file["row_count"] == 3 and file["duplicate_count"] == 1
        assert [dict(row) for row in await conn.fetch("SELECT * FROM base.records ORDER BY id")] == before


@pytest.mark.asyncio
@pytest.mark.parametrize("where,status,body", [
    ("listing", 403, b""), ("file", 403, b""),
    ("listing", 200, b"<html>Please complete the captcha</html>"),
    ("listing", 200, b"<html>Access denied</html>"),
    ("listing", 429, b""),
])
async def test_atf_block_is_visible_and_durable_without_further_reads(database, monkeypatch, where, status, body):
    conn, rt = database
    calls = []
    def public(request):
        calls.append(str(request.url))
        if where == "file" and str(request.url) == REFERENCE_URL:
            return httpx.Response(200, text=LISTING)
        return httpx.Response(status, content=body)
    async with engine(rt, monkeypatch, public) as store:
        await check_reference(store)
        # Simulate a restarted agent by clearing its in-memory stop. Tank's
        # persisted block must prevent another request, even on an empty box.
        monkeypatch.setattr(reference, "_blocked", False)
        await check_reference(store)
        await BaseStore(rt).adopt()
        page = await reference_page(store, [], [], False, 0, 1)
        assert page["file"] is None and page["total_all"] == 0
        assert page["refresh"]["status"] == "blocked"
        assert page["refresh"]["message"].startswith("The reference could not be loaded:")
        assert "ATF did not allow the read" in page["refresh"]["message"]
        assert "Automatic checks have stopped." in page["refresh"]["message"]
        if status != 200:
            assert f"HTTP {status}" in page["refresh"]["message"]
        assert not await store.due_refresh()
    assert calls == [REFERENCE_URL, FILE_URL] if where == "file" else calls == [REFERENCE_URL]


@pytest.mark.asyncio
@pytest.mark.parametrize("appeared", ["saved_rows", "reference_file"])
async def test_initial_install_rechecks_existing_set_after_download(database, appeared):
    conn, rt = database
    store = BaseStore(rt)
    file = {"published_on": "2025-09-01", "source_url": FILE_URL, "checked_at": "2026-10-27T12:00:00+00:00",
            "sha256": "fixture-race", "rows": [reference.project(raw(88))]}
    if appeared == "saved_rows":
        await seed(conn)
        with pytest.raises(ReferenceFailure, match="Saved ATF licence rows became available"):
            await store.install(file, initial=True)
        assert await store.latest_file() is None
        assert await conn.fetchval("SELECT count(*) FROM base.records WHERE tenant_id=$1", PLATFORM) == 4
    else:
        existing = await store.install({**file, "published_on": "2025-01-01", "sha256": "previous-fixture"})
        kept = await store.install(file, initial=True)
        assert kept["id"] == existing["id"] and kept["sha256"] == "previous-fixture"
        assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_files") == 1


@pytest.mark.asyncio
async def test_no_eligible_file_is_a_visible_failure_not_an_empty_success(database, monkeypatch):
    conn, rt = database
    async with engine(rt, monkeypatch, lambda request: httpx.Response(200, text="<html>No download links</html>")) as store:
        await check_reference(store)
        assert await store.latest_file() is None
        message = await conn.fetchval("SELECT message FROM tank.base_reference_checks WHERE owner_id=$1", PLATFORM)
        assert "No dated complete ATF list was found on the official page." in message


def test_separator_rows_are_ignored_but_incomplete_licences_are_rejected():
    content = atf_bytes([raw()])
    separator = b"\t" * (len(raw()) - 1) + b"\n"
    assert len(reference.parse_file(content + separator)) == 1
    with pytest.raises(ValueError, match="incomplete"):
        reference.parse_file(content + b"5\t74\n")


@pytest.mark.asyncio
async def test_block_status_is_checked_before_reading_response_body(monkeypatch):
    monkeypatch.setattr(reference, "_blocked", False)
    monkeypatch.setattr(reference, "_last_read", 0)
    class MustNotRead(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail("A 403 body must not be consumed or mistaken for a file-size failure")
            yield b""
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(403, stream=MustNotRead()))) as client:
        with pytest.raises(ValueError, match="blocked: HTTP 403"):
            await reference.read_public(client, REFERENCE_URL)
