"""R3 Rig: catalogue import, public API, and tenant isolation. No database and no network."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.catalogue import map_google_merchant, map_shopify, map_woocommerce  # noqa: E402
from rigbox.logic import has_breakdown, rule_matches  # noqa: E402
from rigbox.service import RecordingHandoff, Service  # noqa: E402
from rigbox.store import MemoryStore, PgStore, _SEARCH, schema_statements  # noqa: E402
from rigbox.api import mount  # noqa: E402

EXAMPLE = ROOT / "agents" / "rig" / "catalogues" / "example"
TENANT = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
KEY = "rk_pub_examplebrand"
OTHER_KEY = "rk_pub_othertenant"
ORIGIN = "https://rig.tervory.com"
BANNED = re.compile(
    r"\b(firearms?|ammunition|ammo|handguns?|rifles?|pistols?|shotguns?|holsters?|picatinny|staccato|calibres?|calibers?)\b",
    re.IGNORECASE,
)


class Models:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        if task_type == "rig.ask":
            return json.dumps({"answer": "The scope is in the catalogue.", "cites": ["EXAMPLE-SCOPE-01", "made-up"]})
        if task_type == "rig.explain":
            return json.dumps({"why": ["Checked against the catalogue."], "parts": [{"id": "extra"}]})
        if task_type == "rig.fit_suggest":
            return json.dumps(
                {
                    "fits": [
                        {
                            "part_sku": "CASE-1",
                            "fits_sku": "EXAMPLE-RIFLE-01",
                            "rule": {},
                            "confidence": 0.5,
                            "source": "import",
                            "approved": True,
                        }
                    ]
                }
            )
        raise AssertionError(task_type)


async def _loaded() -> tuple[Service, MemoryStore, RecordingHandoff, Models]:
    store = MemoryStore()
    handoff = RecordingHandoff()
    models = Models()
    service = Service(store, models, handoff)
    report = await service.load_folder(EXAMPLE)
    assert report["products"] == {"added": 3, "updated": 0, "rejected": []}
    assert report["fits"]["rejected"] == []
    assert report["fits"]["added"] == 3
    assert report["keys"] == 1
    return service, store, handoff, models


def _client(service: Service) -> TestClient:
    app = FastAPI()
    app.state.rig = service
    mount(app)
    return TestClient(app)


def _headers(key: str = KEY, origin: str | None = ORIGIN) -> dict[str, str]:
    headers = {"X-Rig-Key": key}
    if origin is not None:
        headers["Origin"] = origin
    return headers


@pytest.mark.asyncio
async def test_import_search_setups_and_a_single_total() -> None:
    service, store, handoff, models = await _loaded()
    again = await service.load_folder(EXAMPLE)
    assert again["products"]["added"] == 0
    assert again["products"]["updated"] == 3
    found = await service.search(TENANT, "scope", 12)
    assert [item["id"] for item in found["results"]] == ["EXAMPLE-SCOPE-01"]
    assert list(found["results"][0]) == ["id", "name", "brand", "category", "image", "price", "attributes"]
    assert found["results"][0]["price"]["indicative"] is True
    assert await service.search(TENANT, "", 12) == {"results": []}
    detail = await service.product(TENANT, "EXAMPLE-RIFLE-01")
    assert {item["category"] for item in detail["categories_that_fit"]} == {"optic", "mount"}
    built = await service.setups(TENANT, "EXAMPLE-RIFLE-01")
    setup = built["setups"][0]
    assert setup["total"] == {"amount": 35297, "currency": "ZAR", "indicative": True}
    assert [part["product"]["id"] for part in setup["parts"]] == [
        "EXAMPLE-RIFLE-01",
        "EXAMPLE-SCOPE-01",
        "EXAMPLE-RINGS-30",
    ]
    assert "extra" not in json.dumps(setup["parts"])
    assert setup["why"] == [
        "Fits Example Rifle 308 20in",
        "Scope listed for this rifle",
        "rail is picatinny",
        "Picatinny rings fit every rifle on this platform",
    ]
    assert "rig.explain" not in models.calls
    assert has_breakdown(built) is False
    graph = await service.graph(TENANT, "EXAMPLE-RIFLE-01")
    assert "categories_that_fit" not in graph["centre"]
    assert [branch["category"] for branch in graph["branches"]] == ["mount", "optic"]
    assert KEY not in json.dumps(store.keys)
    assert handoff.sent == []


@pytest.mark.asyncio
async def test_suggested_fits_stay_hidden_until_approved() -> None:
    service, store, _handoff, models = await _loaded()
    await store.upsert_product(
        TENANT,
        {
            "sku": "EXAMPLE-SCOPE-02",
            "name": "Second Scope",
            "brand": "ExampleOptics",
            "category": "optic",
            "price": "1000.00",
            "currency": "ZAR",
            "image_url": "https://example.com/s2.jpg",
            "active": True,
            "attributes": {},
            "family": "",
        },
    )
    await store.upsert_fit(
        TENANT,
        {
            "part_sku": "EXAMPLE-SCOPE-02",
            "fits_sku": "EXAMPLE-RIFLE-01",
            "fits_family": None,
            "rule": {},
            "source": "suggested",
            "approved": False,
            "note": "",
            "confidence": 0.4,
        },
    )
    hidden = await service.swap(
        TENANT,
        (await service.setups(TENANT, "EXAMPLE-RIFLE-01"))["setups"][0],
        "optic",
    )
    assert [item["id"] for item in hidden["options"]] == []
    await service.approve(TENANT, "EXAMPLE-SCOPE-02", "EXAMPLE-RIFLE-01", None)
    shown = await service.swap(TENANT, hidden["setup"], "optic")
    assert [item["id"] for item in shown["options"]] == ["EXAMPLE-SCOPE-02"]
    priced = await service.swap(
        TENANT,
        {
            **shown["setup"],
            "parts": [
                shown["setup"]["parts"][0],
                {"role": "optic", "product": {**shown["options"][0], "price": {"amount": 1, "currency": "ZAR", "indicative": True}}},
                shown["setup"]["parts"][2],
            ],
        },
        "optic",
    )
    assert priced["setup"]["total"]["amount"] == 24999 + 1000 + 1299
    await store.upsert_product(
        TENANT,
        {
            "sku": "CASE-1",
            "name": "Soft Case",
            "brand": "ExampleBrand",
            "category": "case",
            "price": "100.00",
            "currency": "ZAR",
            "image_url": "https://example.com/c.jpg",
            "active": True,
            "attributes": {"colour": "navy"},
            "family": "",
        },
    )
    suggested = await service.suggest(TENANT)
    assert suggested["fits"][0]["source"] == "suggested"
    assert suggested["fits"][0]["approved"] is False
    assert "case" not in {branch["category"] for branch in (await service.graph(TENANT, "EXAMPLE-RIFLE-01"))["branches"]}
    await service.approve(TENANT, "CASE-1", "EXAMPLE-RIFLE-01", None)
    assert "case" in {branch["category"] for branch in (await service.graph(TENANT, "EXAMPLE-RIFLE-01"))["branches"]}
    assert "rig.fit_suggest" in models.calls


@pytest.mark.asyncio
async def test_ask_refuses_outside_the_catalogue_and_quotes_are_stored() -> None:
    service, store, handoff, models = await _loaded()
    refused = await service.ask(TENANT, "EXAMPLE-RIFLE-01", "What is the capital of France?")
    assert refused == {"answer": "I don't know", "cites": []}
    assert "rig.ask" not in models.calls
    answered = await service.ask(TENANT, "EXAMPLE-RIFLE-01", "Which scope is listed?")
    assert answered["cites"] == ["EXAMPLE-SCOPE-01"]
    assert "made-up" not in answered["cites"]
    quoted = await service.quote(
        TENANT,
        {
            "product_id": "EXAMPLE-SCOPE-01",
            "contact": {"name": "Ada", "email": "ada@example.com"},
        },
    )
    assert quoted["request_id"].startswith("req_")
    assert len(handoff.sent) == 1
    assert handoff.sent[0]["tenant_id"] == TENANT
    assert handoff.sent[0]["email"] == "buyer@example.com"
    saved = await store.quotes_for(TENANT)
    assert saved[0]["id"] == quoted["request_id"]
    assert has_breakdown(saved[0]["payload"]) is False
    linked = await service.link_quote(TENANT, "https://example.com/item", "Please check this")
    assert linked["request_id"].startswith("req_")
    with pytest.raises(Exception) as bad_link:
        await service.link_quote(TENANT, "not a url", "")
    assert bad_link.value.status == 422  # type: ignore[attr-defined]
    with pytest.raises(Exception) as bad_contact:
        await service.quote(TENANT, {"product_id": "EXAMPLE-SCOPE-01", "contact": {"name": "", "email": ""}})
    assert bad_contact.value.status == 422  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_key_cannot_see_another_tenant() -> None:
    service, store, _handoff, _models = await _loaded()
    await store.upsert_product(
        OTHER,
        {
            "sku": "SECRET-1",
            "name": "Secret Lamp",
            "brand": "North",
            "category": "light",
            "price": "5.00",
            "currency": "USD",
            "image_url": "https://example.com/secret.jpg",
            "active": True,
            "attributes": {},
            "family": "",
        },
    )
    from rigbox.service import hash_key

    await store.put_key(OTHER, hash_key(OTHER_KEY), "publishable", ["https://other.example"])
    assert await service.search(TENANT, "secret", 12) == {"results": []}
    assert [item["id"] for item in (await service.search(OTHER, "secret", 12))["results"]] == ["SECRET-1"]
    assert await service.search(OTHER, "scope", 12) == {"results": []}
    with pytest.raises(Exception) as missing:
        await service.product(TENANT, "SECRET-1")
    assert missing.value.status == 404  # type: ignore[attr-defined]
    client = _client(service)
    own = client.get("/v1/rig/search", params={"q": "secret"}, headers=_headers())
    assert own.status_code == 200
    assert own.json()["results"] == []
    assert own.headers["access-control-allow-origin"] == ORIGIN
    other = client.get(
        "/v1/rig/search",
        params={"q": "secret"},
        headers=_headers(OTHER_KEY, "https://other.example"),
    )
    assert [item["id"] for item in other.json()["results"]] == ["SECRET-1"]
    refused = client.get("/v1/rig/search", params={"q": "scope"}, headers=_headers(origin="https://evil.example"))
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "origin"
    assert "access-control-allow-origin" not in refused.headers
    missing_key = client.get("/v1/rig/search", params={"q": "scope"})
    assert missing_key.status_code == 401
    assert missing_key.json()["error"]["code"] == "unauthorized"
    preflight = client.options("/v1/rig/search", headers={"Origin": ORIGIN, "Access-Control-Request-Headers": "X-Rig-Key"})
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.asyncio
async def test_rate_limit_and_bad_sheet_and_feeds_and_price_watch(tmp_path: Path) -> None:
    store = MemoryStore()
    service = Service(store, rate_limit=2)
    await service.load_folder(EXAMPLE)
    client = _client(service)
    assert client.get("/v1/rig/search", params={"q": "scope"}, headers=_headers()).status_code == 200
    assert client.get("/v1/rig/search", params={"q": "scope"}, headers=_headers()).status_code == 200
    limited = client.get("/v1/rig/search", params={"q": "scope"}, headers=_headers())
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limit"

    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "products.csv").write_text(
        "sku,gtin,name,brand,category,price,currency,image_url,product_url,family,active,attributes\n"
        "OK-1,,Ok Lamp,North,light,10,USD,https://example.com/a.jpg,,,yes,\n"
        "BAD-1,,Bad Lamp,North,light,nope,USD,https://example.com/b.jpg,,,yes,\n",
        encoding="utf-8",
    )
    rejected = await service.load_folder(folder)
    assert rejected["products"]["added"] == 0
    assert rejected["products"]["rejected"]
    assert await store.product_exists(rejected["tenant_id"], "OK-1") is False

    await store.put_feed(TENANT, "shopify", "https://example.com/products.json", "USD")
    body = {
        "products": [
            {
                "title": "Desk Lamp",
                "vendor": "North",
                "product_type": "light",
                "handle": "desk-lamp",
                "status": "active",
                "images": [{"src": "https://example.com/l.jpg"}],
                "variants": [{"sku": "LAMP-1", "price": "42.00", "barcode": "000"}],
            }
        ]
    }

    async def fetch(_url: str) -> dict:
        return body

    pulled = await service.pull_feeds(TENANT, fetch)
    assert pulled[0]["added"] == 1
    assert [item["id"] for item in (await service.search(TENANT, "desk", 5))["results"]] == ["LAMP-1"]
    woo = map_woocommerce(
        [{"sku": "W-1", "name": "Clip", "price": "3.00", "permalink": "https://example.com/w", "images": [{"src": "https://example.com/w.jpg"}], "categories": [{"name": "clip"}], "brands": [{"name": "North"}], "status": "publish"}],
        "USD",
    )
    assert woo["rows"][0]["sku"] == "W-1"
    merchant = map_google_merchant(
        """<?xml version="1.0"?><rss xmlns:g="http://base.google.com/ns/1.0"><channel><item>
        <g:id>G-1</g:id><g:title>Stand</g:title><g:brand>North</g:brand>
        <g:price>8.00 USD</g:price><g:image_link>https://example.com/g.jpg</g:image_link>
        <g:link>https://example.com/g</g:link><g:availability>in stock</g:availability>
        <g:product_type>stand</g:product_type>
        </item></channel></rss>"""
    )
    assert merchant["rows"][0]["currency"] == "USD"
    shop = map_shopify(body, "USD")
    assert shop["rejected"] == []
    before = (await service.product(TENANT, "EXAMPLE-SCOPE-01"))["attributes"]
    assert await service.apply_watch(
        TENANT,
        "EXAMPLE-SCOPE-01",
        {"price": "10.00", "attributes": {"tube_mm": 99}, "fits": [{"part_sku": "NOPE"}]},
    )
    after = await service.product(TENANT, "EXAMPLE-SCOPE-01")
    assert after["price"]["amount"] == 10
    assert after["attributes"] == before
    assert rule_matches({"length_mm": [400, 520]}, {"length_mm": 450}) is True
    assert rule_matches({"length_mm": [400, 520]}, {"length_mm": 10}) is False


def _load_rig_app():
    """Load agents/rig/app.py by path. A bare `import app` can resolve to tiger/app.py."""
    path = ROOT / "agents" / "rig" / "app.py"
    spec = importlib.util.spec_from_file_location("rig_public_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rig_public_app"] = module
    spec.loader.exec_module(module)
    return module


def test_public_app_drops_jobs_and_docs() -> None:
    import asyncio

    rig_app = _load_rig_app()
    assert Path(rig_app.__file__).resolve() == (ROOT / "agents" / "rig" / "app.py").resolve()

    paths = {getattr(route, "path", None) for route in rig_app.app.routes}
    assert "/health" in paths
    assert "/v1/rig/search" in paths
    assert rig_app.app.openapi_url is None
    assert rig_app.app.docs_url is None
    for closed in ("/jobs", "/jobs/{job_id}", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"):
        assert closed not in paths

    async def status(method: str, path: str) -> int:
        sent: list[dict] = []

        async def receive() -> dict:
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message: dict) -> None:
            sent.append(message)

        await rig_app.app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 9),
                "server": ("test", 80),
            },
            receive,
            send,
        )
        return int(sent[0]["status"])

    assert asyncio.run(status("POST", "/jobs")) == 404
    assert asyncio.run(status("GET", "/jobs/11111111-1111-4111-8111-111111111111")) == 404
    assert asyncio.run(status("GET", "/docs")) == 404
    assert asyncio.run(status("GET", "/openapi.json")) == 404
    assert asyncio.run(status("GET", "/redoc")) == 404
    assert asyncio.run(status("GET", "/health")) == 503


def test_room_compose_policy_and_skills_match() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    corridor = compose["networks"]["tervory-gw-rig"]
    assert corridor["name"] == "tervory-gw-rig"
    assert "external" not in corridor
    for name in ("tank", "postgres", "hermes"):
        assert "tervory-gw-rig" in services[name]["networks"]
    for name in ("redis", "qdrant", "litellm", "searxng", "tiger", "workspace", "agent-roles"):
        assert "tervory-gw-rig" not in (services[name].get("networks") or [])
    assert services["tank"]["environment"]["TANK_KEY_RIG"] == "${TANK_KEY_RIG:-}"
    assert services["hermes"]["environment"]["TANK_KEY_RIG"] == "${TANK_KEY_RIG:-}"
    assert "AGENT_DB_PASSWORD_RIG" in services["agent-roles"]["environment"]
    box = yaml.safe_load((ROOT / "agents" / "rig" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert box["networks"]["gw"]["external"] is True
    assert box["networks"]["gw"]["name"] == "tervory-gw-rig"
    service = box["services"]["agent-rig"]
    assert service["mem_limit"] == "512m"
    assert "postgresql://agent_rig:" in service["environment"]["DATABASE_URL"]
    assert service["environment"]["TANK_KEY"] == "${TANK_KEY_RIG:-}"
    assert "POSTGRES_PASSWORD" not in service["environment"]
    assert "POSTGRES_USER" not in service["environment"]
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "TANK_KEY_RIG=" in example
    assert "AGENT_DB_PASSWORD_RIG=" in example
    assert "| Rig | `tervory-gw-rig`" in (ROOT / "agents" / "README.md").read_text(encoding="utf-8")
    policy = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
    for task in ("rig.explain", "rig.ask", "rig.fit_suggest"):
        assert f"'{task}', 1, 'luna'" in policy
    assert "ON CONFLICT DO NOTHING" in policy
    assert "tenant_id = $1" in _SEARCH
    assert "to_tsvector" in _SEARCH
    assert "similarity" in _SEARCH
    for statement in schema_statements():
        if statement.upper().startswith("CREATE"):
            assert "IF NOT EXISTS" in statement.upper()
    logic = (ROOT / "agents" / "rig" / "rigbox" / "logic.py").read_bytes()
    ground = (ROOT / "agents" / "rig" / "rigbox" / "ground.py").read_bytes()
    assert logic == (ROOT / "tank" / "skills" / "rig.search" / "1.0.0" / "pure.py").read_bytes()
    assert logic == (ROOT / "tank" / "skills" / "rig.setups" / "1.0.0" / "pure.py").read_bytes()
    for name in ("rig.explain", "rig.ask", "rig.fit_suggest"):
        assert ground == (ROOT / "tank" / "skills" / name / "1.0.0" / "ground.py").read_bytes()
    hits: list[str] = []
    roots = [ROOT / "agents" / "rig" / "rigbox", ROOT / "agents" / "rig" / "app.py"]
    roots.extend(ROOT / "tank" / "skills" / name for name in ("rig.search", "rig.setups", "rig.explain", "rig.ask", "rig.fit_suggest"))
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix not in {".py", ".sql", ".yml", ".yaml", ".md", ".jsonl"}:
                continue
            if BANNED.search(path.read_text(encoding="utf-8")):
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_model_skill_cases_do_not_call_the_model() -> None:
    class Boom:
        async def model(self, *_args: object, **_kwargs: object) -> str:
            raise AssertionError("model")

    import asyncio
    import skala

    async def run_cases(skill_id: str) -> None:
        path = ROOT / "tank" / "skills" / skill_id / "1.0.0" / "run.py"
        spec = importlib.util.spec_from_file_location(skill_id.replace(".", "_"), path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        raw = (path.parent / "evals" / "cases.jsonl").read_text(encoding="utf-8")
        for line in raw.splitlines():
            case = json.loads(line)
            output = await module.run(case["input"], Boom())
            ok, why = skala.score_case(case["expected"], output, case["tolerance"])
            assert ok, why

    asyncio.run(run_cases("rig.ask"))
    asyncio.run(run_cases("rig.explain"))
    asyncio.run(run_cases("rig.fit_suggest"))


class InsufficientPrivilegeError(Exception):
    """Stand-in for asyncpg.exceptions.InsufficientPrivilegeError. No database."""


class _SchemaConn:
    def __init__(self, *, present: bool, error: BaseException | None) -> None:
        self.present = present
        self.error = error
        self.executed: list[str] = []
        self.lookups: list[str] = []

    async def execute(self, statement: str) -> None:
        self.executed.append(statement)
        if self.error is not None:
            raise self.error

    async def fetchval(self, query: str) -> int | None:
        self.lookups.append(query)
        return 1 if self.present else None


class _SchemaPool:
    def __init__(self, conn: _SchemaConn) -> None:
        self.conn = conn

    def acquire(self) -> "_SchemaAcquire":
        return _SchemaAcquire(self.conn)


class _SchemaAcquire:
    def __init__(self, conn: _SchemaConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _SchemaConn:
        return self.conn

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _denied() -> InsufficientPrivilegeError:
    return InsufficientPrivilegeError("permission denied for database tervory")


def _apply(
    statements: list[str],
    *,
    present: bool,
    error: BaseException | None,
    monkeypatch: pytest.MonkeyPatch,
) -> _SchemaConn:
    import rigbox.store as store

    monkeypatch.setattr(store, "schema_statements", lambda: list(statements))
    conn = _SchemaConn(present=present, error=error)
    asyncio.run(PgStore(_SchemaPool(conn)).apply_schema())
    return conn


def test_commented_create_schema_is_not_fatal_when_agent_rig_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """A leading ``--`` comment must not hide CREATE SCHEMA from the applicator."""
    statement = "-- Rig's room.\n\nCREATE SCHEMA IF NOT EXISTS agent_rig"
    real = schema_statements()[0]
    assert real.lstrip().startswith("--")
    assert "CREATE SCHEMA IF NOT EXISTS agent_rig" in real

    for text in (statement, real):
        kept = _apply([text], present=True, error=_denied(), monkeypatch=monkeypatch)
        assert kept.executed == [text]
        assert kept.lookups == ["SELECT 1 FROM pg_namespace WHERE nspname = 'agent_rig'"]
        with pytest.raises(InsufficientPrivilegeError):
            _apply([text], present=False, error=_denied(), monkeypatch=monkeypatch)

    with pytest.raises(RuntimeError):
        _apply([statement], present=True, error=RuntimeError("syntax error"), monkeypatch=monkeypatch)
    other = "-- not this room\nCREATE SCHEMA IF NOT EXISTS other_box"
    with pytest.raises(InsufficientPrivilegeError):
        _apply([other], present=True, error=_denied(), monkeypatch=monkeypatch)


def test_commented_extension_and_trigram_failures_stay_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = RuntimeError("pg_trgm is not available")
    optional = [
        "-- trigram type\n\nCREATE EXTENSION IF NOT EXISTS pg_trgm",
        "-- name search\nCREATE INDEX IF NOT EXISTS products_name_trgm ON agent_rig.products USING gin (name gin_trgm_ops)",
    ]
    applied = _apply(optional, present=True, error=failure, monkeypatch=monkeypatch)
    assert applied.executed == optional
    assert applied.lookups == []

    commented_table = "-- mentions gin_trgm_ops but is not that index\nCREATE TABLE agent_rig.products (sku text)"
    with pytest.raises(RuntimeError):
        _apply([commented_table], present=True, error=failure, monkeypatch=monkeypatch)
