"""R4: dealer admin for suggested fits, and stored answers. No database and no network."""

from __future__ import annotations

from rig_fixture_loader import load_catalogue

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.service import Service, hash_key  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

EXAMPLE = ROOT / "tests" / "fixtures" / "rig_catalogues" / "example"
SECOND = ROOT / "tests" / "fixtures" / "rig_catalogues" / "second"
TENANT = "11111111-1111-4111-8111-111111111111"
SECOND_TENANT = "22222222-2222-4222-8222-222222222222"
PUBLISHABLE = "rk_pub_examplebrand"
ADMIN = "rk_adm_examplebrand"
SECOND_ADMIN = "rk_adm_secondtenant"
ORIGIN = "https://rig.tervory.com"
RIFLE = "EXAMPLE-RIFLE-01"
LAMP = "SECOND-LAMP-01"
CASE = "CASE-1"
SLING = "SLING-1"
NOTED = "NOTED-1"


class Tank:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id
        self.calls.append(task_type)
        self.prompts.append(messages[0]["content"] if messages else "")
        if task_type == "rig.fit_suggest":
            return json.dumps(
                {
                    "fits": [
                        {
                            "part_sku": CASE,
                            "fits_sku": RIFLE,
                            "rule": {},
                            "confidence": 0.66,
                            "source": "import",
                            "approved": True,
                        }
                    ]
                }
            )
        if task_type == "rig.explain":
            return json.dumps({"why": ["Checked against the catalogue."], "parts": [{"id": "extra"}]})
        raise AssertionError(task_type)


def _client(service: Service) -> TestClient:
    app = FastAPI()
    app.state.rig = service
    mount(app)
    return TestClient(app)


def _admin(key: str = ADMIN) -> dict[str, str]:
    return {"X-Rig-Key": key}


def _shopper(key: str = PUBLISHABLE, origin: str = ORIGIN) -> dict[str, str]:
    return {"X-Rig-Key": key, "Origin": origin}


def _ids(body: dict) -> list[str]:
    found: list[str] = []
    for setup in body.get("setups") or []:
        for part in setup.get("parts") or []:
            found.append(part["product"]["id"])
    for branch in body.get("branches") or []:
        for product in branch.get("products") or []:
            found.append(product["id"])
    return found


def _cached(store: MemoryStore, tenant_id: str) -> set[tuple[str, str]]:
    return {(key[1], key[2]) for key in store.answers if key[0] == tenant_id}


async def _product(store: MemoryStore, tenant_id: str, sku: str, name: str, category: str, price: str = "100.00") -> None:
    await store.upsert_product(
        tenant_id,
        {
            "sku": sku,
            "name": name,
            "brand": "ExampleBrand",
            "category": category,
            "price": price,
            "currency": "ZAR" if tenant_id == TENANT else "USD",
            "image_url": "https://example.com/part.jpg",
            "active": True,
            "attributes": {},
            "family": "",
        },
    )


async def _fit(
    store: MemoryStore,
    tenant_id: str,
    part_sku: str,
    *,
    fits_sku: str | None = None,
    fits_family: str | None = None,
    source: str = "import",
    approved: bool = True,
    note: str = "",
    rule: dict | None = None,
    confidence: float = 1,
) -> None:
    await store.upsert_fit(
        tenant_id,
        {
            "part_sku": part_sku,
            "fits_sku": fits_sku,
            "fits_family": fits_family,
            "rule": rule or {},
            "source": source,
            "approved": approved,
            "note": note,
            "confidence": confidence,
        },
    )


def _with_case(roles: list[dict[str, str]] | None = None) -> dict:
    chosen = roles or [
        {"role": "optic", "category": "optic"},
        {"role": "mount", "category": "mount"},
        {"role": "case", "category": "case"},
    ]
    return {"tiers": [{"tier": "ready", "label": "Ready to use", "roles": chosen}]}


async def _loaded() -> tuple[Service, MemoryStore, Tank]:
    store = MemoryStore()
    models = Tank()
    service = Service(store, models)
    example = await load_catalogue(service, EXAMPLE)
    second = await load_catalogue(service, SECOND)
    assert example["products"]["rejected"] == []
    assert second["products"]["rejected"] == []
    await store.put_key(TENANT, hash_key(ADMIN), "admin", [])
    await store.put_key(SECOND_TENANT, hash_key(SECOND_ADMIN), "admin", [])
    return service, store, models


@pytest.mark.asyncio
async def test_admin_routes_require_an_admin_key() -> None:
    service, _store, _models = await _loaded()
    client = _client(service)
    missing = client.get("/v1/rig/admin/fits")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"
    unknown = client.get("/v1/rig/admin/fits", headers=_admin("rk_adm_nope"))
    assert unknown.status_code == 401
    publishable = client.get("/v1/rig/admin/fits", headers=_admin(PUBLISHABLE))
    assert publishable.status_code == 403
    assert publishable.json()["error"]["code"] == "forbidden"
    for path in ("/admin/fits/approve", "/admin/fits/reject", "/admin/fits/suggest"):
        refused = client.post(
            "/v1/rig" + path,
            headers=_admin(PUBLISHABLE),
            json={"part_sku": CASE, "fits_sku": RIFLE},
        )
        assert refused.status_code == 403
    shopper = client.get("/v1/rig/search", params={"q": "scope"}, headers=_shopper(ADMIN))
    assert shopper.status_code == 401
    listed = client.get("/v1/rig/admin/fits", params={"status": "suggested"}, headers=_admin())
    assert listed.status_code == 200
    assert listed.json() == {"fits": []}
    other = client.get("/v1/rig/admin/fits", params={"status": "approved"}, headers=_admin())
    assert other.status_code == 422


@pytest.mark.asyncio
async def test_suggest_runs_only_when_a_dealer_calls_it() -> None:
    service, store, models = await _loaded()
    await _product(store, TENANT, CASE, "Soft Case", "case")
    await service.setups(TENANT, RIFLE)
    await service.graph(TENANT, RIFLE)
    assert "rig.fit_suggest" not in models.calls
    source = (ROOT / "agents" / "rig" / "app.py").read_text(encoding="utf-8")
    assert "fit_suggest" not in source
    assert "suggest" not in source
    client = _client(service)
    once = client.post("/v1/rig/admin/fits/suggest", headers=_admin())
    assert once.status_code == 200
    assert once.json()["fits"][0]["part_sku"] == CASE
    assert once.json()["fits"][0]["approved"] is False
    assert once.json()["fits"][0]["source"] == "suggested"
    assert models.calls.count("rig.fit_suggest") == 1
    client.get("/v1/rig/admin/fits", headers=_admin())
    await service.setups(TENANT, RIFLE)
    assert models.calls.count("rig.fit_suggest") == 1
    again = client.post("/v1/rig/admin/fits/suggest", headers=_admin())
    assert again.status_code == 200
    assert models.calls.count("rig.fit_suggest") == 2


@pytest.mark.asyncio
async def test_list_approve_and_reject_keep_unapproved_fits_away_from_shoppers() -> None:
    service, store, models = await _loaded()
    await _product(store, TENANT, CASE, "Soft Case", "case", "100.00")
    await _product(store, TENANT, NOTED, "Noted Case", "spare", "50.00")
    await store.set_template(TENANT, "rifle", _with_case())
    await _fit(
        store,
        TENANT,
        NOTED,
        fits_sku=RIFLE,
        source="suggested",
        approved=False,
        note="Kept aside until a person approves it",
        confidence=0.25,
    )
    client = _client(service)
    suggested = client.post("/v1/rig/admin/fits/suggest", headers=_admin())
    assert suggested.status_code == 200
    listed = client.get("/v1/rig/admin/fits", params={"status": "suggested"}, headers=_admin())
    assert listed.status_code == 200
    by_sku = {row["part_sku"]: row for row in listed.json()["fits"]}
    assert set(by_sku) == {CASE, NOTED}
    assert by_sku[CASE]["confidence"] == 0.66
    assert by_sku[CASE]["note"] == ""
    assert by_sku[CASE]["fits_sku"] == RIFLE
    assert by_sku[NOTED]["note"] == "Kept aside until a person approves it"
    assert by_sku[NOTED]["confidence"] == 0.25
    hidden_setups = await service.setups(TENANT, RIFLE)
    hidden_graph = await service.graph(TENANT, RIFLE)
    assert CASE not in _ids(hidden_setups)
    assert CASE not in _ids(hidden_graph)
    assert NOTED not in _ids(hidden_graph)
    assert "rig.explain" not in models.calls

    approved = client.post(
        "/v1/rig/admin/fits/approve",
        headers=_admin(),
        json={"part_sku": CASE, "fits_sku": RIFLE},
    )
    assert approved.status_code == 200
    assert approved.json() == {"approved": True}
    shown = await service.setups(TENANT, RIFLE)
    shown_graph = await service.graph(TENANT, RIFLE)
    assert CASE in _ids(shown)
    assert CASE in _ids(shown_graph)
    assert NOTED not in _ids(shown_graph)
    setup = shown["setups"][0]
    amounts = [part["product"]["price"]["amount"] for part in setup["parts"]]
    assert setup["total"]["amount"] == sum(amounts) == 35297 + 100
    assert "discount" not in json.dumps(shown)
    assert "extra" not in _ids(shown)
    assert [part["product"]["id"] for part in setup["parts"]].count(CASE) == 1
    still = client.get("/v1/rig/admin/fits", headers=_admin())
    assert [row["part_sku"] for row in still.json()["fits"]] == [NOTED]

    both = client.post(
        "/v1/rig/admin/fits/approve",
        headers=_admin(),
        json={"part_sku": CASE, "fits_sku": RIFLE, "fits_family": "EXAMPLE-PLATFORM"},
    )
    assert both.status_code == 422
    missing = client.post(
        "/v1/rig/admin/fits/approve",
        headers=_admin(),
        json={"part_sku": "MISSING", "fits_sku": RIFLE},
    )
    assert missing.status_code == 404

    rejected = client.post(
        "/v1/rig/admin/fits/reject",
        headers=_admin(),
        json={"part_sku": CASE, "fits_sku": RIFLE},
    )
    assert rejected.status_code == 200
    assert rejected.json() == {"rejected": True}
    after = await service.setups(TENANT, RIFLE)
    after_graph = await service.graph(TENANT, RIFLE)
    assert CASE not in json.dumps(after)
    assert CASE not in json.dumps(after_graph)
    assert after["setups"][0]["total"]["amount"] == 35297
    listed_again = client.get("/v1/rig/admin/fits", headers=_admin())
    assert [row["part_sku"] for row in listed_again.json()["fits"]] == [NOTED]
    family = client.post(
        "/v1/rig/admin/fits/reject",
        headers=_admin(),
        json={"part_sku": "EXAMPLE-RINGS-30", "fits_family": "EXAMPLE-PLATFORM"},
    )
    assert family.status_code == 200
    without_mount = await service.graph(TENANT, RIFLE)
    assert "mount" not in {branch["category"] for branch in without_mount["branches"]}


@pytest.mark.asyncio
async def test_one_admin_key_cannot_see_or_approve_another_tenant() -> None:
    service, store, _models = await _loaded()
    await _product(store, TENANT, CASE, "Soft Case", "case")
    await _product(store, SECOND_TENANT, "ONLY-B", "Only Second", "shade", "8.00")
    await _fit(
        store,
        SECOND_TENANT,
        "ONLY-B",
        fits_sku=LAMP,
        source="suggested",
        approved=False,
        note="Second dealer only",
        confidence=0.2,
    )
    client = _client(service)
    client.post("/v1/rig/admin/fits/suggest", headers=_admin())
    own = client.get("/v1/rig/admin/fits", headers=_admin())
    assert [row["part_sku"] for row in own.json()["fits"]] == [CASE]
    foreign = client.get("/v1/rig/admin/fits", headers=_admin(SECOND_ADMIN))
    assert [row["part_sku"] for row in foreign.json()["fits"]] == ["ONLY-B"]
    assert CASE not in foreign.text
    assert "Second dealer only" not in own.text
    stolen = client.post(
        "/v1/rig/admin/fits/approve",
        headers=_admin(SECOND_ADMIN),
        json={"part_sku": CASE, "fits_sku": RIFLE},
    )
    assert stolen.status_code == 404
    still = client.get("/v1/rig/admin/fits", headers=_admin())
    assert still.json()["fits"][0]["part_sku"] == CASE
    blocked = client.post(
        "/v1/rig/admin/fits/reject",
        headers=_admin(),
        json={"part_sku": "ONLY-B", "fits_sku": LAMP},
    )
    assert blocked.status_code == 404
    untouched = client.get("/v1/rig/admin/fits", headers=_admin(SECOND_ADMIN))
    assert untouched.json()["fits"][0]["note"] == "Second dealer only"


@pytest.mark.asyncio
async def test_single_env_admin_key_binds_only_one_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RIG_ADMIN_KEY", "single-dealer-key")
    store = MemoryStore()
    service = Service(store, Tank())
    await load_catalogue(service, EXAMPLE)
    client = _client(service)
    allowed = client.get("/v1/rig/admin/fits", headers=_admin("single-dealer-key"))
    assert allowed.status_code == 200
    await store.put_retailer(SECOND_TENANT, "second", None, None)
    refused = client.get("/v1/rig/admin/fits", headers=_admin("single-dealer-key"))
    assert refused.status_code == 401


@pytest.mark.asyncio
async def test_repeat_call_makes_no_model_calls_and_matches_a_fresh_answer() -> None:
    service, store, models = await _loaded()
    await _product(store, TENANT, CASE, "Soft Case", "case")
    await _fit(store, TENANT, CASE, fits_sku=RIFLE, note="", rule={})
    await store.set_template(TENANT, "rifle", _with_case())
    first = await service.setups(TENANT, RIFLE)
    first_graph = await service.graph(TENANT, RIFLE)
    assert models.calls.count("rig.explain") == 1
    assert CASE in models.prompts[-1]
    assert "EXAMPLE-SCOPE-01" not in models.prompts[-1]
    assert "extra" not in _ids(first)
    assert "Checked against the catalogue." in first["setups"][0]["why"]
    before = len(models.calls)
    second = await service.setups(TENANT, RIFLE)
    second_graph = await service.graph(TENANT, RIFLE)
    assert models.calls[before:] == []
    assert second == first
    assert second_graph == first_graph
    first["setups"][0]["label"] = "changed by the caller"
    cached = await service.setups(TENANT, RIFLE)
    assert cached["setups"][0]["label"] == "Ready to use"
    store.answers.clear()
    fresh = await service.setups(TENANT, RIFLE)
    fresh_graph = await service.graph(TENANT, RIFLE)
    assert fresh == cached
    assert fresh_graph == second_graph
    assert models.calls[before:] == []


@pytest.mark.asyncio
async def test_a_new_part_is_the_only_one_sent_to_the_model() -> None:
    service, store, models = await _loaded()
    await _product(store, TENANT, CASE, "Soft Case", "case")
    await _fit(store, TENANT, CASE, fits_sku=RIFLE, note="", rule={})
    await store.set_template(TENANT, "rifle", _with_case())
    await service.setups(TENANT, RIFLE)
    assert models.calls.count("rig.explain") == 1
    await _product(store, TENANT, SLING, "Soft Sling", "sling", "40.00")
    await _fit(store, TENANT, SLING, fits_sku=RIFLE, note="", rule={})
    await store.set_template(
        TENANT,
        "rifle",
        _with_case(
            [
                {"role": "optic", "category": "optic"},
                {"role": "mount", "category": "mount"},
                {"role": "case", "category": "case"},
                {"role": "sling", "category": "sling"},
            ]
        ),
    )
    before = len(models.calls)
    built = await service.setups(TENANT, RIFLE)
    assert models.calls[before:] == ["rig.explain"]
    prompt = models.prompts[-1]
    assert SLING in prompt
    assert CASE not in prompt
    assert "EXAMPLE-SCOPE-01" not in prompt
    assert "EXAMPLE-RINGS-30" not in prompt
    assert SLING in _ids(built)
    assert "Checked against the catalogue." in built["setups"][0]["why"]
    amounts = [part["product"]["price"]["amount"] for part in built["setups"][0]["parts"]]
    assert built["setups"][0]["total"]["amount"] == sum(amounts)
    again = len(models.calls)
    assert await service.setups(TENANT, RIFLE) == built
    assert models.calls[again:] == []


@pytest.mark.asyncio
async def test_import_feed_price_approve_and_reject_clear_only_that_tenant() -> None:
    service, store, _models = await _loaded()
    await service.setups(TENANT, RIFLE)
    await service.graph(TENANT, RIFLE)
    await service.setups(SECOND_TENANT, LAMP)
    await service.graph(SECOND_TENANT, LAMP)
    assert _cached(store, TENANT) == {("setups", RIFLE), ("graph", RIFLE)}
    assert ("setups", LAMP) in _cached(store, SECOND_TENANT)

    await load_catalogue(service, EXAMPLE)
    assert _cached(store, TENANT) == set()
    assert ("setups", LAMP) in _cached(store, SECOND_TENANT)

    await service.setups(TENANT, RIFLE)
    await service.apply_watch(TENANT, "EXAMPLE-SCOPE-01", {"price": "10.00"})
    assert _cached(store, TENANT) == set()
    assert ("graph", LAMP) in _cached(store, SECOND_TENANT)

    await service.setups(TENANT, RIFLE)
    await store.put_feed(TENANT, "shopify", "https://example.com/products.json", "ZAR")

    async def fetch(_url: str) -> dict:
        return {
            "products": [
                {
                    "title": "Desk Lamp",
                    "vendor": "North",
                    "product_type": "light",
                    "handle": "desk-lamp",
                    "status": "active",
                    "images": [{"src": "https://example.com/l.jpg"}],
                    "variants": [{"sku": "LAMP-9", "price": "42.00", "barcode": "000"}],
                }
            ]
        }

    await service.pull_feeds(TENANT, fetch)
    assert _cached(store, TENANT) == set()
    assert ("setups", LAMP) in _cached(store, SECOND_TENANT)

    await service.setups(TENANT, RIFLE)
    await _product(store, TENANT, CASE, "Soft Case", "case")
    await _fit(store, TENANT, CASE, fits_sku=RIFLE, source="suggested", approved=False, note="Later", confidence=0.4)
    await service.setups(TENANT, RIFLE)
    assert _cached(store, TENANT) == {("setups", RIFLE)}
    assert await service.approve(TENANT, CASE, RIFLE, None) is True
    assert _cached(store, TENANT) == set()
    assert ("setups", LAMP) in _cached(store, SECOND_TENANT)

    await service.setups(TENANT, RIFLE)
    assert await service.reject(TENANT, CASE, RIFLE, None) is True
    assert _cached(store, TENANT) == set()
    assert ("graph", LAMP) in _cached(store, SECOND_TENANT)
    hidden = await service.graph(TENANT, RIFLE)
    assert CASE not in json.dumps(hidden)


@pytest.mark.asyncio
async def test_cached_fixture_answers_stay_under_300ms() -> None:
    service, _store, models = await _loaded()
    await service.setups(TENANT, RIFLE)
    await service.graph(TENANT, RIFLE)
    before = len(models.calls)
    started = time.perf_counter()
    for _ in range(15):
        setups = await service.setups(TENANT, RIFLE)
        graph = await service.graph(TENANT, RIFLE)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.3
    assert models.calls[before:] == []
    assert setups["setups"][0]["total"]["amount"] == 35297
    assert "discount" not in json.dumps(setups)
    assert [branch["category"] for branch in graph["branches"]] == ["mount", "optic"]
    schema = (ROOT / "agents" / "rig" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS agent_rig.answers" in schema
    assert "CREATE TABLE IF NOT EXISTS agent_rig.fit_why" in schema
    compose = (ROOT / "agents" / "rig" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "RIG_ADMIN_KEY: ${RIG_ADMIN_KEY:-}" in compose
