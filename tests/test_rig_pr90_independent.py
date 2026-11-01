"""Independent pre-deploy review of PR #90.

Stand-in catalogues only (agents/rig/catalogues/*). No network, no distributor,
no database. This file does not change Rig. It measures the five Rig checks
from the build plan and the extra review points around that PR.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import statistics
import sys
import threading
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.page_route import mount_page  # noqa: E402
from rigbox.service import Service, hash_key  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

CATALOGUES = ROOT / "agents" / "rig" / "catalogues"
CN = CATALOGUES / "customnation"
ARCHON = CATALOGUES / "archon"
EXAMPLE = CATALOGUES / "example"
SECOND = CATALOGUES / "second"
PAGE = ROOT / "agents" / "rig" / "rigbox" / "page"
REPORT = Path("/tmp/rig-pr90-independent.json")
SHOTS = Path(os.environ.get("RIG_SCREENSHOT_DIR", "/tmp/rig-pr90-screenshots"))

CN_TENANT = "33333333-3333-4333-8333-333333333333"
EX_TENANT = "11111111-1111-4111-8111-111111111111"
SE_TENANT = "22222222-2222-4222-8222-222222222222"
CN_ORIGIN = "https://rig.tervory.com"
LOCAL_ORIGIN = "http://127.0.0.1:5173"
SE_ORIGIN = "https://second.example"
ADMIN_CN = "review-admin-custom-nation"
ADMIN_EX = "review-admin-example"
PHANTOM = "Phantom Suppressor X9"
DISTRIBUTORS = (
    "lipseys",
    "sportssouth",
    "davidsons",
    "zanders",
    "rsrgroup",
    "billhicks",
    "amchar",
    "camfour",
    "mgewholesale",
    "ironvalley",
    "davessport",
    "2ndamendment",
)

# Shopper searches. Each row is (catalogue, query, acceptable product ids).
# A hit is the right product in the first three results. 200 rows, fixed.
_CN: list[tuple[str, set[str]]] = []


def _cn(sku: str, phrases: list[str]) -> None:
    for phrase in phrases:
        _CN.append((phrase, {sku}))


_cn("STI-P-9", ["Staccato P", "staccato p", "staccato P pistol", "sti-p-9", "stacato p", "staccatoo p", "sti p", "pistol staccato p"])
_cn("STI-C2-9", ["staccato c2", "Staccato C2", "sti-c2-9", "stacato c2", "staccatto c2", "c2 staccato", "staccato c 2", "sti c2"])
_cn("STI-XC-9", ["staccato xc", "Staccato XC", "sti-xc-9", "stacato xc", "staccatoo xc", "xc staccato", "sti xc", "staccato xc pistol"])
_cn("TRIJ-RMR-T2", ["trijicon rmr", "Trijicon RMR Type 2", "rmr type 2", "rmr", "triicon rmr", "rmr t2", "trijicon rmr type", "rmrtype2"])
_cn("HOL-507C-X2", ["holosun 507c", "Holosun 507C X2", "507c", "holsun 507", "507c x2", "holosun507c", "holosun x2", "holsun"])
_cn("DAW-FO-FRONT", ["dawson fiber front sight", "dawson sight", "dawson", "dawon sight", "fiber front", "dawson fiber", "dawson front sight", "dawson precision"])
_cn("TEN8-REAR", ["10-8 rear sight", "10-8", "ten8", "10 8 sight", "108 rear", "10-8 performance", "10-8 rear", "108 sight"])
_cn("CHEELY-E2", ["cheely e2", "Cheely E2 grip", "cheely e2 grip", "e2 grip", "cheely grip", "cheelye2", "e2 cheely", "cheely e 2"])
_cn("CHEELY-C2", ["cheely compact grip", "cheely c2", "cheely compact", "cheely c2 grip", "compact cheely", "cheelyc2", "cheely c 2", "cheely compact grip module"])
_cn("ATLAS-FLAT", ["atlas flat trigger", "atlas trigger", "atlas flat", "atlas", "flat trigger", "atlasflat", "atlas triggr", "atlas flat faced"])
_cn("REDD-TRIGGER", ["red dirt trigger", "red dirt", "reddirt trigger", "reddirt", "red dirt trig", "dirt trigger", "red-dirt trigger", "red dirt trigger shoe"])
_cn("SAF-ALS-FULL", ["safariland als", "safariland holster", "safariland", "als holster", "duty holster", "safariland als duty", "als duty holster", "safariland duty"])
_cn("TENICOR-VELO", ["tenicor velo", "tenicor", "velo holster", "tenicorvelo", "velo", "tenicor velo holster", "tenicor holster", "tenicore velo"])
_cn("MAG-17", ["2011 magazine 17", "magazine 17", "17 round mag", "mag 17", "17rd magazine", "17 round magazine", "2011 mag 17", "checkmate 17"])
_cn("MAG-20", ["2011 magazine 20", "magazine 20", "20 round", "mag 20", "20 round magazine", "2011 mag 20", "checkmate 20", "20rd magazine"])
_cn("MAG-16", ["2011 magazine 16", "magazine 16", "16 round", "mag 16", "16 round magazine", "2011 mag 16", "checkmate 16", "16rd mag"])
_cn("SF-X300U", ["surefire x300", "SureFire X300U", "x300", "x300u", "sure fire", "surefire x300u", "surefire light", "x300 ultra"])
_cn("SL-TLR1", ["streamlight tlr", "Streamlight TLR-1 HL", "tlr-1", "tlr1", "stream light", "tlr 1", "tlr-1 hl", "streamlight tlr-1"])

_EX: list[tuple[str, set[str]]] = [
    ("example rifle", {"EXAMPLE-RIFLE-01"}),
    ("example rifle 308", {"EXAMPLE-RIFLE-01"}),
    ("308 20in", {"EXAMPLE-RIFLE-01"}),
    ("exmple rifle", {"EXAMPLE-RIFLE-01"}),
    ("examplebrand rifle", {"EXAMPLE-RIFLE-01"}),
    ("308 win", {"EXAMPLE-RIFLE-01"}),
    ("example scope", {"EXAMPLE-SCOPE-01"}),
    ("scope 4-16", {"EXAMPLE-SCOPE-01"}),
    ("4-16x44", {"EXAMPLE-SCOPE-01"}),
    ("exmaple scope", {"EXAMPLE-SCOPE-01"}),
    ("exampleoptics scope", {"EXAMPLE-SCOPE-01"}),
    ("example scope 4-16x44", {"EXAMPLE-SCOPE-01"}),
    ("30mm rings", {"EXAMPLE-RINGS-30"}),
    ("picatinny rings", {"EXAMPLE-RINGS-30"}),
    ("example rings", {"EXAMPLE-RINGS-30"}),
    ("30mm rings picatinny", {"EXAMPLE-RINGS-30"}),
    ("example 30mm", {"EXAMPLE-RINGS-30"}),
    ("picatinny mount", {"EXAMPLE-RINGS-30"}),
]
_SE: list[tuple[str, set[str]]] = [
    ("desk lamp", {"SECOND-LAMP-01"}),
    ("second desk lamp", {"SECOND-LAMP-01"}),
    ("secondbrand lamp", {"SECOND-LAMP-01"}),
    ("desk lammp", {"SECOND-LAMP-01"}),
    ("lamp shade", {"SECOND-SHADE-01"}),
    ("second lamp shade", {"SECOND-SHADE-01"}),
    ("lampshade", {"SECOND-SHADE-01"}),
    ("second shade", {"SECOND-SHADE-01"}),
]
_PISTOLS = {"STI-P-9", "STI-C2-9", "STI-XC-9"}
_OPTICS = {"HOL-507C-X2", "TRIJ-RMR-T2"}
_INTENT: list[tuple[str, set[str]]] = [
    ("staccato", _PISTOLS),
    ("2011 pistol", _PISTOLS),
    ("staccato pistol", _PISTOLS),
    ("buy a staccato c2", {"STI-C2-9"}),
    ("price of staccato xc", {"STI-XC-9"}),
    ("optic for staccato", _OPTICS),
    ("red dot for staccato", _OPTICS),
    ("grip for staccato c2", {"CHEELY-C2"}),
    ("holster for c2", {"TENICOR-VELO"}),
    ("holster for staccato p", {"SAF-ALS-FULL"}),
    ("magazine for staccato p", {"MAG-17", "MAG-20"}),
    ("light for staccato", {"SF-X300U", "SL-TLR1"}),
    ("trigger for staccato", {"ATLAS-FLAT", "REDD-TRIGGER"}),
    ("sight for staccato", {"DAW-FO-FRONT", "TEN8-REAR"}),
    ("compact 2011", {"STI-C2-9"}),
    ("rmr for 2011", {"TRIJ-RMR-T2"}),
    ("holosun for staccato", {"HOL-507C-X2"}),
    ("cheely for staccato c2", {"CHEELY-C2"}),
    ("surefire for staccato", {"SF-X300U"}),
    ("streamlight for pistol", {"SL-TLR1"}),
    ("c2", {"STI-C2-9", "CHEELY-C2"}),
    ("red dot", _OPTICS),
    ("holster", {"TENICOR-VELO", "SAF-ALS-FULL"}),
    ("optic", _OPTICS),
    ("pistol", _PISTOLS),
    ("2011 magazine", {"MAG-16", "MAG-17", "MAG-20"}),
    ("staccato c2 holster", {"TENICOR-VELO"}),
    ("dawson for staccato", {"DAW-FO-FRONT"}),
    ("atlas for 2011", {"ATLAS-FLAT"}),
    ("x300 for staccato", {"SF-X300U"}),
]

QUERIES: list[tuple[str, str, set[str]]] = (
    [("customnation", text, ok) for text, ok in _CN]
    + [("example", text, ok) for text, ok in _EX]
    + [("second", text, ok) for text, ok in _SE]
    + [("customnation", text, ok) for text, ok in _INTENT]
)

OUTSIDE = [
    "What is the capital of France?",
    "What is the weather in Cape Town tomorrow?",
    "How much is a Glock 19?",
    "Tell me a recipe for pasta",
    "What is the bitcoin price today?",
    "Who won the 2022 world cup?",
    "Recommend a Toyota Hilux",
    "How do I reset my Netflix password?",
    "What is the population of Tokyo?",
    "Translate good morning into isiZulu",
    "Book a flight to London",
    "What is the square root of 144?",
    "Does this holster fit a Glock 19?",
    "Which optic should I buy for a Glock?",
    "What is the duty and VAT breakdown on the Staccato?",
    "Can you ship a suppressor with the Staccato C2?",
    "Is the Staccato legal in California?",
    "What is the warranty period on the Trijicon?",
    "Does the Holosun come with a free mount I can return?",
    "Compare the Staccato to a Glock 17 for concealed carry",
    "What battery does the SureFire take?",
    "How long is the barrel on the Staccato XC?",
    "Can I finance the Staccato P over 24 months?",
    "Which of these lights is waterproof?",
]

# One approved part per category, read off the fit sheet (family or that sku).
# Alphabetical sku wins when a category has more than one approved part.
EXPECTED_BUNDLE = {
    "STI-P-9": ["STI-P-9", "DAW-FO-FRONT", "CHEELY-E2", "SAF-ALS-FULL", "SF-X300U", "MAG-17", "HOL-507C-X2", "ATLAS-FLAT"],
    "STI-C2-9": ["STI-C2-9", "DAW-FO-FRONT", "CHEELY-C2", "TENICOR-VELO", "SF-X300U", "MAG-16", "HOL-507C-X2", "ATLAS-FLAT"],
    "STI-XC-9": ["STI-XC-9", "DAW-FO-FRONT", "CHEELY-E2", "SAF-ALS-FULL", "SF-X300U", "MAG-17", "HOL-507C-X2", "ATLAS-FLAT"],
}
EXPECTED_TOTAL = {"STI-P-9": 85892, "STI-C2-9": 79292, "STI-XC-9": 110892}
C2_FITS = {
    "TRIJ-RMR-T2", "HOL-507C-X2", "DAW-FO-FRONT", "TEN8-REAR", "CHEELY-C2",
    "ATLAS-FLAT", "REDD-TRIGGER", "TENICOR-VELO", "MAG-16", "SF-X300U", "SL-TLR1",
}
C2_DOES_NOT_FIT = {"CHEELY-E2", "SAF-ALS-FULL", "MAG-17", "MAG-20"}


class Hostile:
    """A model that invents a product and cites one real id to try to slip it through."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        return json.dumps(
            {
                "answer": f"The {PHANTOM} costs 12345 ZAR and is in stock.",
                "cites": ["PHANTOM-X9", "STI-C2-9", "EXAMPLE-RIFLE-01"],
            }
        )


class Quiet:
    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type, messages
        return ""


def _record(name: str, payload: dict[str, Any]) -> None:
    current: dict[str, Any] = {}
    if REPORT.exists():
        current = json.loads(REPORT.read_text(encoding="utf-8"))
    current[name] = payload
    REPORT.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")
    print(f"\nRIG-PR90 {name}: {json.dumps(payload, default=str)}")


def _publish(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "publish.json").read_text(encoding="utf-8"))


def _key(folder: Path) -> str:
    return str(_publish(folder)["keys"][0]["key"])


def _prices(folder: Path) -> dict[str, Decimal]:
    found: dict[str, Decimal] = {}
    with (folder / "products.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            found[row["sku"]] = Decimal(row["price"])
    return found


def _market_rows(folder: Path) -> list[dict[str, str]]:
    with (folder / "market.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _expected_market(sku: str, currency: str, exclude_source: str) -> Decimal | None:
    amounts = [
        Decimal(row["price"])
        for row in _market_rows(CN)
        if row["sku"] == sku
        and row["currency"].upper() == currency.upper()
        and row["source"].casefold() != exclude_source.casefold()
    ]
    if not amounts:
        return None
    return (sum(amounts, Decimal("0")) / Decimal(len(amounts))).quantize(Decimal("0.01"))


def _app(service: Service) -> FastAPI:
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    return app


async def _loaded(models: Any | None = None, *, rate_limit: int = 60) -> Service:
    service = Service(MemoryStore(), models if models is not None else Quiet(), rate_limit=rate_limit)
    for folder in (CN, EXAMPLE, SECOND):
        report = await service.load_folder(folder)
        assert report["products"]["rejected"] == [], report
        assert report["fits"]["rejected"] == [], report
    await service.store.put_key(CN_TENANT, hash_key(ADMIN_CN), "admin", [])
    await service.store.put_key(EX_TENANT, hash_key(ADMIN_EX), "admin", [])
    return service


def _ids(body: dict[str, Any]) -> list[str]:
    return [str(item["id"]) for item in body.get("results") or []]


def _shopper_blob(payload: Any) -> str:
    return json.dumps(payload, default=str)


def _approved_targets(fits: list[dict[str, Any]], centre: str, family: str) -> set[str]:
    found: set[str] = set()
    for row in fits:
        source = str(row.get("source") or "")
        if source == "rejected" or row.get("approved") is False:
            continue
        if source == "suggested" and not row.get("approved"):
            continue
        sku = str(row.get("fits_sku") or "")
        fam = str(row.get("fits_family") or "")
        if sku == centre or (fam and fam == family):
            found.add(str(row.get("part_sku") or ""))
    return found


def _percentiles(samples: list[float]) -> tuple[float, float, float]:
    ordered = sorted(samples)
    cuts = statistics.quantiles(ordered, n=100, method="inclusive")
    return cuts[49], cuts[94], ordered[-1]


SPEED_LIMIT_MS = 300
# One request in the 200 may stall on a shared CI runner (GC or another xdist
# worker holding the CPU). Seen today: 568 ms and 859 ms single samples with
# p95 near 11 ms. Two or more slow samples, or a slow p95, is a real regression.
SPEED_ALLOWED_OVER = 1
# The one allowed outlier still has a hard ceiling, so a real hang fails.
SPEED_CEILING_MS = 2000


def _speed_ok(samples: list[float]) -> bool:
    """Gate 5 verdict: p95 under the limit, at most one sample at or over it, none at the ceiling."""
    _p50, p95, slowest = _percentiles(samples)
    over = sum(1 for sample in samples if sample >= SPEED_LIMIT_MS)
    return p95 < SPEED_LIMIT_MS and over <= SPEED_ALLOWED_OVER and slowest < SPEED_CEILING_MS


def _retime_lone_outlier(samples: list[float], retime: Callable[[int], float]) -> dict[int, float]:
    """Re-time a lone over-limit sample once. A runner pause won't repeat; a slow query will.

    All 200 queries are distinct, so one slow sample can also be one slow query shape.
    Two or more slow samples already fail ``_speed_ok`` and are not re-timed, and
    neither is a lone sample at or over the ceiling, which fails anyway.
    """
    over = [index for index, sample in enumerate(samples) if sample >= SPEED_LIMIT_MS]
    if len(over) != SPEED_ALLOWED_OVER or samples[over[0]] >= SPEED_CEILING_MS:
        return {}
    return {index: retime(index) for index in over}


def _timed_search(world: dict[str, Any], catalogue: str, text: str) -> float:
    """One timed shop-page search over HTTP, in ms."""
    client: TestClient = world["client"]
    started = time.perf_counter()
    response = client.get(
        "/v1/rig/search",
        params={"q": text, "limit": 12},
        headers={"X-Rig-Key": world["keys"][catalogue], "Origin": world["origins"][catalogue]},
    )
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200
    return elapsed


def _cold_search(world: dict[str, Any], catalogue: str, text: str) -> float:
    """Time a search after dropping the tenant's saved searches, so the ranker really runs again.

    The first call saves the search and a repeat would be served from that saved copy.
    """
    asyncio.run(world["service"].store.drop_searches(world["tenants"][catalogue]))
    return _timed_search(world, catalogue, text)


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """Clean catalogues. Tests that add rows build their own service."""
    service = asyncio.run(_loaded(rate_limit=5000))
    client = TestClient(_app(service))
    client.__enter__()
    keys = {
        "customnation": _key(CN),
        "example": _key(EXAMPLE),
        "second": _key(SECOND),
    }
    origins = {
        "customnation": CN_ORIGIN,
        "example": CN_ORIGIN,
        "second": SE_ORIGIN,
    }
    tenants = {"customnation": CN_TENANT, "example": EX_TENANT, "second": SE_TENANT}
    payload = {"service": service, "client": client, "keys": keys, "origins": origins, "tenants": tenants}
    yield payload
    client.__exit__(None, None, None)


def test_gate_1_only_approved_fits_are_shown() -> None:
    """Every accessory a shopper can see has an approved fit. Suggested and rejected stay hidden."""
    service = asyncio.run(_loaded(rate_limit=5000))
    client = TestClient(_app(service))
    checked = 0
    violations: list[str] = []

    async def walk() -> None:
        nonlocal checked
        for tenant, centre_ids in (
            (CN_TENANT, ["STI-P-9", "STI-C2-9", "STI-XC-9"]),
            (EX_TENANT, ["EXAMPLE-RIFLE-01"]),
            (SE_TENANT, ["SECOND-LAMP-01"]),
        ):
            products = {str(row["sku"]): row for row in await service.store.products(tenant)}
            fits = await service.store.fits(tenant)
            for centre_id in centre_ids:
                centre = products[centre_id]
                allowed = _approved_targets(fits, centre_id, str(centre.get("family") or ""))
                graph = await service.graph(tenant, centre_id)
                setups = await service.setups(tenant, centre_id)
                detail = await service.product(tenant, centre_id)
                for branch in graph["branches"]:
                    for item in branch["products"]:
                        checked += 1
                        if item["id"] not in allowed or item["id"] == centre_id:
                            violations.append(f"graph {centre_id} {item['id']}")
                        if "market" in item:
                            violations.append(f"market on graph {item['id']}")
                for setup in setups["setups"]:
                    for part in setup["parts"][1:]:
                        checked += 1
                        part_id = part["product"]["id"]
                        if part_id not in allowed:
                            violations.append(f"setup {centre_id} {part_id}")
                for row in detail["categories_that_fit"]:
                    checked += 1
                    if row["count"] < 1:
                        violations.append(f"empty category {centre_id} {row['category']}")
        c2 = await service.graph(CN_TENANT, "STI-C2-9")
        shown = {item["id"] for branch in c2["branches"] for item in branch["products"]}
        if shown != C2_FITS:
            violations.append(f"C2 accessories {sorted(shown ^ C2_FITS)}")
        if shown & C2_DOES_NOT_FIT:
            violations.append(f"C2 showed a fit for another pistol {sorted(shown & C2_DOES_NOT_FIT)}")

        await service.store.upsert_product(
            CN_TENANT,
            {
                "sku": "HIDDEN-SUGGESTED",
                "name": "Hidden Suggested Optic",
                "brand": "Hidden",
                "category": "Optics",
                "price": "10.00",
                "currency": "ZAR",
                "image_url": "https://assets.local/hidden.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            CN_TENANT,
            {
                "part_sku": "HIDDEN-SUGGESTED",
                "fits_sku": "STI-C2-9",
                "fits_family": None,
                "rule": {},
                "source": "suggested",
                "approved": False,
                "note": "not approved",
                "confidence": 0.4,
            },
        )
        await service.store.upsert_product(
            CN_TENANT,
            {
                "sku": "HIDDEN-REJECTED",
                "name": "Hidden Rejected Light",
                "brand": "Hidden",
                "category": "Lights",
                "price": "11.00",
                "currency": "ZAR",
                "image_url": "https://assets.local/hidden-no.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            CN_TENANT,
            {
                "part_sku": "HIDDEN-REJECTED",
                "fits_sku": "STI-C2-9",
                "fits_family": None,
                "rule": {},
                "source": "rejected",
                "approved": False,
                "note": "rejected",
                "confidence": 0.1,
            },
        )
        blob = _shopper_blob(await service.graph(CN_TENANT, "STI-C2-9"))
        blob += _shopper_blob(await service.setups(CN_TENANT, "STI-C2-9"))
        blob += _shopper_blob(await service.product(CN_TENANT, "STI-C2-9"))
        setup = (await service.setups(CN_TENANT, "STI-C2-9"))["setups"][0]
        blob += _shopper_blob(await service.swap(CN_TENANT, setup, "Optics"))
        for name in ("Hidden Suggested Optic", "Hidden Rejected Light", "HIDDEN-SUGGESTED", "HIDDEN-REJECTED"):
            checked += 1
            if name in blob:
                violations.append(f"shopper saw {name}")
        waiting = await service.suggested_fits(CN_TENANT)
        waiting_ids = {row["part_sku"] for row in waiting["fits"]}
        if "HIDDEN-SUGGESTED" not in waiting_ids:
            violations.append("admin list missed the suggested fit")
        if "HIDDEN-REJECTED" in waiting_ids:
            violations.append("admin list showed a rejected fit")
        page = client.get(
            "/v1/rig/graph/STI-C2-9",
            headers={"X-Rig-Key": _key(CN), "Origin": CN_ORIGIN},
        )
        assert page.status_code == 200
        if "Hidden Suggested" in page.text or "Hidden Rejected" in page.text:
            violations.append("HTTP graph showed an unapproved fit")
        await service.approve(CN_TENANT, "HIDDEN-SUGGESTED", "STI-C2-9", None)
        await service.reject(CN_TENANT, "CHEELY-C2", "STI-C2-9", None)
        after = await service.graph(CN_TENANT, "STI-C2-9")
        after_ids = {item["id"] for branch in after["branches"] for item in branch["products"]}
        checked += 2
        if "HIDDEN-SUGGESTED" not in after_ids:
            violations.append("approved fit stayed hidden")
        if "CHEELY-C2" in after_ids or "HIDDEN-REJECTED" in after_ids:
            violations.append("rejected fit was shown")

    asyncio.run(walk())
    rate = 100.0 if checked and not violations else (100.0 * (checked - len(violations)) / checked if checked else 0.0)
    payload = {"checked": checked, "violations": len(violations), "rate_pct": round(rate, 2), "examples": violations[:8]}
    _record("1_approved_fits", payload)
    assert not violations, payload
    assert rate == 100.0


def test_gate_2_search_top3(world: dict[str, Any]) -> None:
    """200 shopper queries. Pass when the right product is in the top 3 for at least 90%."""
    assert len(QUERIES) == 200, len(QUERIES)
    pairs = [(catalogue, text) for catalogue, text, _ok in QUERIES]
    assert len(pairs) == len(set(pairs)), "duplicate shopper query"
    client: TestClient = world["client"]
    hits = 0
    misses: list[dict[str, Any]] = []
    for catalogue, text, acceptable in QUERIES:
        response = client.get(
            "/v1/rig/search",
            params={"q": text, "limit": 12},
            headers={"X-Rig-Key": world["keys"][catalogue], "Origin": world["origins"][catalogue]},
        )
        assert response.status_code == 200, (text, response.status_code, response.text)
        found = _ids(response.json())[:3]
        if any(sku in found for sku in acceptable):
            hits += 1
        else:
            misses.append({"q": text, "catalogue": catalogue, "want": sorted(acceptable), "got": found})
    rate = 100.0 * hits / len(QUERIES)
    payload = {"queries": len(QUERIES), "hits": hits, "misses": len(misses), "rate_pct": round(rate, 2), "miss_list": misses}
    _record("2_search", payload)
    assert rate >= 90.0, payload


def test_gate_3_i_dont_know_outside_the_catalogue() -> None:
    """Questions the sheets cannot answer stay 'I don't know', with nothing invented."""
    hostile = Hostile()
    service = asyncio.run(_loaded(hostile, rate_limit=5000))
    refused = 0
    fabricated: list[dict[str, Any]] = []
    model_calls_before = 0

    async def ask_all() -> None:
        nonlocal refused, model_calls_before
        for question in OUTSIDE:
            model_calls_before = len(hostile.calls)
            answer = await service.ask(CN_TENANT, "STI-C2-9", question)
            called = len(hostile.calls) > model_calls_before
            text = str(answer.get("answer") or "")
            cites = list(answer.get("cites") or [])
            clean = text == "I don't know" and cites == [] and PHANTOM not in text and "12345" not in text
            if clean:
                refused += 1
            else:
                fabricated.append({"q": question, "answer": text, "cites": cites, "model_called": called})
        empty = await service.search(CN_TENANT, "Glock 19", 12)
        if empty["results"]:
            fabricated.append({"q": "search Glock 19", "answer": empty["results"], "cites": [], "model_called": False})
        else:
            refused += 1

    asyncio.run(ask_all())
    total = len(OUTSIDE) + 1
    rate = 100.0 * refused / total
    payload = {
        "questions": total,
        "refused": refused,
        "fabricated": len(fabricated),
        "rate_pct": round(rate, 2),
        "model_calls": len(hostile.calls),
        "examples": fabricated,
        "bug": "agents/rig/rigbox/ground.py:22-32 and :121-126; agents/rig/rigbox/service.py:249-258",
    }
    _record("3_i_dont_know", payload)
    assert rate == 100.0, payload


def test_gate_4_one_retailer_never_sees_another() -> None:
    """Two retailers' keys, including admin routes and market prices. Crossings must be 0."""
    service = asyncio.run(_loaded(rate_limit=5000))
    client = TestClient(_app(service))
    cn_key = _key(CN)
    ex_key = _key(EXAMPLE)
    se_key = _key(SECOND)
    crossings: list[str] = []

    def shop(key: str, origin: str) -> dict[str, str]:
        return {"X-Rig-Key": key, "Origin": origin}

    def leak(label: str, text: str, needles: list[str]) -> None:
        for needle in needles:
            if needle and needle in text:
                crossings.append(f"{label} contains {needle}")

    cn_only = ["Staccato C2", "Tervory", "Cheely compact grip"]
    ex_only = ["Example Rifle 308 20in", "ExampleOptics", "EXAMPLE-RIFLE-01"]
    se_only = ["Second Desk Lamp", "SecondBrand"]

    own = client.get("/v1/rig/search", params={"q": "staccato c2"}, headers=shop(cn_key, CN_ORIGIN))
    assert own.status_code == 200
    leak("cn search staccato", own.text, ex_only + se_only)
    ex_search = client.get("/v1/rig/search", params={"q": "staccato"}, headers=shop(ex_key, CN_ORIGIN))
    leak("example search staccato", ex_search.text, cn_only)
    if ex_search.json()["results"]:
        crossings.append("example search returned Staccato rows")
    se_search = client.get("/v1/rig/search", params={"q": "Staccato C2"}, headers=shop(se_key, SE_ORIGIN))
    leak("second search staccato", se_search.text, cn_only + ex_only)
    cn_foreign = client.get("/v1/rig/search", params={"q": "Example Rifle"}, headers=shop(cn_key, CN_ORIGIN))
    leak("cn search example rifle", cn_foreign.text, ex_only)

    for path in ("/v1/rig/products/EXAMPLE-RIFLE-01", "/v1/rig/graph/EXAMPLE-RIFLE-01"):
        response = client.get(path, headers=shop(cn_key, CN_ORIGIN))
        if response.status_code != 404:
            crossings.append(f"{path} status {response.status_code}")
        leak(path, response.text, ex_only)
    setups = client.post("/v1/rig/setups", headers=shop(cn_key, CN_ORIGIN), json={"product_id": "SECOND-LAMP-01"})
    if setups.status_code != 404:
        crossings.append(f"setups foreign status {setups.status_code}")
    leak("setups foreign", setups.text, se_only)
    compared = client.post(
        "/v1/rig/compare",
        headers=shop(cn_key, CN_ORIGIN),
        json={"product_ids": ["EXAMPLE-RIFLE-01", "SECOND-LAMP-01"]},
    )
    if compared.status_code != 404:
        crossings.append(f"compare foreign status {compared.status_code}")
    leak("compare foreign", compared.text, ex_only + se_only)
    mixed = client.post(
        "/v1/rig/compare",
        headers=shop(cn_key, CN_ORIGIN),
        json={"product_ids": ["STI-C2-9", "EXAMPLE-RIFLE-01"]},
    )
    assert mixed.status_code == 200
    leak("compare mixed", mixed.text, ex_only)
    if [line["id"] for line in mixed.json()["lines"]] != ["STI-C2-9"]:
        crossings.append(f"compare mixed lines {[line['id'] for line in mixed.json()['lines']]}")

    wrong_origin = client.get("/v1/rig/search", params={"q": "staccato"}, headers=shop(cn_key, SE_ORIGIN))
    if wrong_origin.status_code != 403:
        crossings.append(f"wrong origin status {wrong_origin.status_code}")
    leak("wrong origin", wrong_origin.text, cn_only)

    pub_admin = client.get("/v1/rig/admin/fits", headers={"X-Rig-Key": cn_key})
    if pub_admin.status_code != 403:
        crossings.append(f"publishable key on admin status {pub_admin.status_code}")
    leak("publishable admin", pub_admin.text, ex_only + se_only + ["HIDDEN-SUGGESTED"])

    async def plant() -> None:
        for tenant, name, price, source in (
            (CN_TENANT, "Shared Widget CN", "10.00", "Cn Side Shop"),
            (EX_TENANT, "Shared Widget EX", "99.00", "Ex Side Shop"),
        ):
            await service.store.upsert_product(
                tenant,
                {
                    "sku": "SHARED-1",
                    "name": name,
                    "brand": "Shared",
                    "category": "Widgets",
                    "price": price,
                    "currency": "ZAR",
                    "image_url": "https://assets.local/shared.jpg",
                    "active": True,
                    "attributes": {},
                    "family": "",
                },
            )
            existing = await service.store.market_for(tenant, [row["sku"] for row in await service.store.products(tenant)])
            existing.append({"sku": "SHARED-1", "source": source, "price": price, "currency": "ZAR", "seen_at": "2026-03-01"})
            await service.store.replace_market(tenant, existing)
        await service.store.upsert_product(
            EX_TENANT,
            {
                "sku": "EX-SECRET-FIT",
                "name": "Example Secret Mount",
                "brand": "ExampleOptics",
                "category": "mount",
                "price": "4.00",
                "currency": "ZAR",
                "image_url": "https://example.com/secret.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            EX_TENANT,
            {
                "part_sku": "EX-SECRET-FIT",
                "fits_sku": "EXAMPLE-RIFLE-01",
                "fits_family": None,
                "rule": {},
                "source": "suggested",
                "approved": False,
                "note": "example only",
                "confidence": 0.2,
            },
        )

    asyncio.run(plant())
    cn_admin = client.get("/v1/rig/admin/fits", headers={"X-Rig-Key": ADMIN_CN})
    assert cn_admin.status_code == 200
    leak("cn admin list", cn_admin.text, ["Example Secret Mount", "EX-SECRET-FIT", "Shared Widget EX", "Ex Side Shop"])
    ex_admin = client.get("/v1/rig/admin/fits", headers={"X-Rig-Key": ADMIN_EX})
    leak("ex admin list", ex_admin.text, ["Hidden Suggested Optic", "Staccato", "Cn Side Shop"])
    stolen = client.post(
        "/v1/rig/admin/fits/approve",
        headers={"X-Rig-Key": ADMIN_CN},
        json={"part_sku": "EX-SECRET-FIT", "fits_sku": "EXAMPLE-RIFLE-01"},
    )
    if stolen.status_code != 404:
        crossings.append(f"cn admin approved an example fit ({stolen.status_code})")
    leak("stolen approve", stolen.text, ["Example Secret Mount"])

    async def still_hidden() -> None:
        rows = await service.suggested_fits(EX_TENANT)
        ids = {row["part_sku"] for row in rows["fits"]}
        if "EX-SECRET-FIT" not in ids:
            crossings.append("example suggested fit disappeared after the other admin called")
        graph = await service.graph(EX_TENANT, "EXAMPLE-RIFLE-01")
        shown = {item["id"] for branch in graph["branches"] for item in branch["products"]}
        if "EX-SECRET-FIT" in shown:
            crossings.append("example shopper saw a fit the other admin touched")

    asyncio.run(still_hidden())
    cn_shared = client.post("/v1/rig/compare", headers=shop(cn_key, CN_ORIGIN), json={"product_ids": ["SHARED-1"]})
    ex_shared = client.post("/v1/rig/compare", headers=shop(ex_key, CN_ORIGIN), json={"product_ids": ["SHARED-1"]})
    leak("cn shared compare", cn_shared.text, ["Ex Side Shop", "Shared Widget EX", "99"])
    leak("ex shared compare", ex_shared.text, ["Cn Side Shop", "Shared Widget CN"])
    if cn_shared.status_code == 200 and cn_shared.json()["lines"][0]["market"]["amount"] != 10:
        crossings.append(f"cn market mixed {cn_shared.json()['lines'][0]['market']}")
    if ex_shared.status_code == 200 and ex_shared.json()["lines"][0]["market"]["amount"] != 99:
        crossings.append(f"ex market mixed {ex_shared.json()['lines'][0]['market']}")
    cn_name = client.get("/v1/rig/search", params={"q": "Shared Widget"}, headers=shop(cn_key, CN_ORIGIN))
    leak("cn shared search", cn_name.text, ["Shared Widget EX"])
    if "Shared Widget CN" not in cn_name.text:
        crossings.append("cn could not see its own shared product")

    monkey = os.environ.get("RIG_ADMIN_KEY")
    os.environ["RIG_ADMIN_KEY"] = "env-admin-should-not-cross"
    try:
        env_attempt = client.get("/v1/rig/admin/fits", headers={"X-Rig-Key": "env-admin-should-not-cross"})
    finally:
        if monkey is None:
            os.environ.pop("RIG_ADMIN_KEY", None)
        else:
            os.environ["RIG_ADMIN_KEY"] = monkey
    if env_attempt.status_code != 401:
        crossings.append(f"env admin key spanned tenants ({env_attempt.status_code})")
    leak("env admin", env_attempt.text, cn_only + ex_only)

    payload = {"checks_with_crossings": len(crossings), "crossings": crossings}
    _record("4_isolation", payload)
    assert crossings == [], payload


def test_gate_5_search_speed(world: dict[str, Any]) -> None:
    """Shop-page search stays under 300 ms. Report p50 and p95."""
    samples = [_timed_search(world, catalogue, text) for catalogue, text, _ok in QUERIES]
    p50, p95, slowest = _percentiles(samples)
    over = sum(1 for sample in samples if sample >= SPEED_LIMIT_MS)
    retimed = {
        QUERIES[index][1]: round(ms, 3)
        for index, ms in _retime_lone_outlier(
            samples, lambda index: _cold_search(world, QUERIES[index][0], QUERIES[index][1])
        ).items()
    }
    payload = {
        "n": len(samples),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(slowest, 3),
        "over_300": over,
        "retimed_ms": retimed,
        "path": "HTTP GET /v1/rig/search on the in-memory ranker (no Postgres in this run)",
    }
    _record("5_speed", payload)
    assert _speed_ok(samples), payload
    assert all(ms < SPEED_LIMIT_MS for ms in retimed.values()), payload


def _verdict(samples: list[float], retime: Callable[[int], float]) -> bool:
    """The two gate 5 asserts as one bool, for the self-check."""
    retimed = _retime_lone_outlier(samples, retime)
    return _speed_ok(samples) and all(ms < SPEED_LIMIT_MS for ms in retimed.values())


def test_gate_5_verdict_tolerates_one_pause_but_not_a_regression() -> None:
    """One stalled sample that is fast on re-time passes. A slow query, a hang, two slow samples or a slow p95 fail."""
    fast = [10.0] * 200
    retimed: list[int] = []

    def pause_gone(index: int) -> float:
        """A runner pause does not repeat: the re-time is fast."""
        retimed.append(index)
        return 10.0

    one_pause_at_100 = fast[:100] + [859.59] + fast[101:]
    assert _verdict(one_pause_at_100, pause_gone) and retimed == [100]
    retimed.clear()
    assert not _verdict(fast[:198] + [568.4, 859.59], pause_gone) and retimed == []
    for constant_ms in (1500.0, 500.0):
        slow_query = fast[:100] + [constant_ms] + fast[101:]
        assert _speed_ok(slow_query)
        assert not _verdict(slow_query, lambda _index, ms=constant_ms: ms)
    assert _verdict(fast, pause_gone) and retimed == []
    assert not _verdict(fast[:199] + [2500.0], pause_gone) and retimed == []
    assert _speed_ok(fast)
    one_pause = fast[:199] + [859.59]
    assert _speed_ok(one_pause)
    two_pauses = fast[:198] + [568.4, 859.59]
    assert not _speed_ok(two_pauses)
    slow_tail = fast[:185] + [400.0] * 15
    assert not _speed_ok(slow_tail)
    all_slow = [400.0] * 200
    assert not _speed_ok(all_slow)
    just_under = [299.0] * 200
    assert _speed_ok(just_under)
    under_ceiling = fast[:199] + [1999.0]
    assert _speed_ok(under_ceiling)
    at_ceiling = fast[:199] + [2000.0]
    assert not _speed_ok(at_ceiling)
    hang = fast[:199] + [10_000.0]
    assert not _speed_ok(hang)


def test_gate_5_retime_reruns_the_ranker(world: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """A query that is slow inside the ranker is still slow on the re-time, not served from a saved search."""
    service = world["service"]
    catalogue, slow = next((catalogue, text) for catalogue, text, _ok in QUERIES if text == "staccato P pistol")
    ranked: list[str] = []
    original = service._rank

    def slow_rank(tenant_id: str, products: list[dict[str, Any]], text: str, cap: int) -> dict[str, Any]:
        if text == slow:
            ranked.append(text)
            time.sleep(SPEED_LIMIT_MS / 1000 + 0.05)
        return original(tenant_id, products, text, cap)

    monkeypatch.setattr(service, "_rank", slow_rank)
    first = _cold_search(world, catalogue, slow)
    retimed = _cold_search(world, catalogue, slow)
    assert first >= SPEED_LIMIT_MS and retimed >= SPEED_LIMIT_MS, (first, retimed)
    assert ranked == [slow, slow]


def test_bundle_and_compare_math() -> None:
    """Bundle total is the sum of the selected sheet prices. Market average is the mean of the other shops."""
    service = asyncio.run(_loaded(rate_limit=5000))
    prices = _prices(CN)
    problems: list[str] = []

    async def check() -> None:
        looked: list[str] = []
        original = service.store.market_for

        async def watch(tenant_id: str, skus: list[str]) -> list[dict[str, Any]]:
            looked.append(tenant_id)
            return await original(tenant_id, skus)

        service.store.market_for = watch
        found = await service.search(CN_TENANT, "staccato c2", 12)
        if looked:
            problems.append("search read market prices")
        if any("market" in item for item in found["results"]):
            problems.append("search result carried a market field")
        for sku, parts in EXPECTED_BUNDLE.items():
            setup = (await service.setups(CN_TENANT, sku))["setups"][0]
            got = [part["product"]["id"] for part in setup["parts"]]
            if got != parts:
                problems.append(f"{sku} parts {got} != {parts}")
            sheet_sum = sum((prices[part] for part in got), Decimal("0"))
            if Decimal(str(setup["total"]["amount"])) != sheet_sum:
                problems.append(f"{sku} total {setup['total']['amount']} != sheet {sheet_sum}")
            if setup["total"]["amount"] != EXPECTED_TOTAL[sku]:
                problems.append(f"{sku} total {setup['total']['amount']} != {EXPECTED_TOTAL[sku]}")
            if setup["total"]["currency"] != "ZAR" or setup["total"]["indicative"] is not True:
                problems.append(f"{sku} total shape {setup['total']}")
        rifle = (await service.setups(EX_TENANT, "EXAMPLE-RIFLE-01"))["setups"][0]
        rifle_sum = sum((_prices(EXAMPLE)[part["product"]["id"]] for part in rifle["parts"]), Decimal("0"))
        if Decimal(str(rifle["total"]["amount"])) != rifle_sum or rifle["total"]["amount"] != 35297:
            problems.append(f"example rifle total {rifle['total']['amount']} sheet {rifle_sum}")
        compared = await service.compare(CN_TENANT, EXPECTED_BUNDLE["STI-C2-9"] + ["SL-TLR1", "TEN8-REAR"])
        if compared["retailer"] != "Tervory":
            problems.append(f"retailer label {compared['retailer']}")
        by_id = {line["id"]: line for line in compared["lines"]}
        for sku in EXPECTED_BUNDLE["STI-C2-9"] + ["SL-TLR1", "TEN8-REAR"]:
            line = by_id[sku]
            if Decimal(str(line["price"]["amount"])) != prices[sku]:
                problems.append(f"{sku} own price {line['price']['amount']} != {prices[sku]}")
            expect = _expected_market(sku, "ZAR", "Tervory")
            got = None if line["market"] is None else Decimal(str(line["market"]["amount"]))
            if expect is None:
                if line["market"] is not None:
                    problems.append(f"{sku} invented a market figure {line['market']}")
            elif got != expect:
                problems.append(f"{sku} market {got} != {expect}")
        rows = await original(CN_TENANT, ["TRIJ-RMR-T2"])
        rows.append({"sku": "TRIJ-RMR-T2", "source": "TERVORY", "price": "1.00", "currency": "ZAR", "seen_at": ""})
        rows.append({"sku": "TRIJ-RMR-T2", "source": "Demo Shop C", "price": "1.00", "currency": "USD", "seen_at": ""})
        await service.store.replace_market(CN_TENANT, rows)
        again = await service.compare(CN_TENANT, ["TRIJ-RMR-T2"])
        if Decimal(str(again["lines"][0]["market"]["amount"])) != Decimal("10000.00"):
            problems.append(f"filtered average moved to {again['lines'][0]['market']}")
        graph = await service.graph(CN_TENANT, "STI-C2-9")
        if "67000" in json.dumps(graph):
            problems.append("graph included a demo-shop price")

    asyncio.run(check())
    payload = {"problems": problems, "c2_total": EXPECTED_TOTAL["STI-C2-9"], "p_total": EXPECTED_TOTAL["STI-P-9"], "xc_total": EXPECTED_TOTAL["STI-XC-9"]}
    _record("bundle_compare_math", payload)
    assert problems == [], payload


def test_diff_secrets_feeds_and_admin_key() -> None:
    """Rig pages and catalogues contain no secret, no live feed, and no admin key."""
    secret_hits: list[str] = []
    distributor_hits: list[str] = []
    patterns = [
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk_live_[A-Za-z0-9]{8,}"),
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        re.compile(r"RIG_ADMIN_KEY\s*[:=]\s*['\"][^'\"$\{][^'\"]*['\"]"),
    ]
    allowed = {"rig.tervory.com", "127.0.0.1:5173", "assets.local", "example.com", "second.example"}

    def scan(path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT).as_posix()
        for pattern in patterns:
            if pattern.search(text):
                secret_hits.append(f"{rel} matched {pattern.pattern}")
        lowered = text.lower()
        for host in DISTRIBUTORS:
            if host in lowered:
                distributor_hits.append(f"{rel} mentions {host}")
        return text

    page_names = ("index.html", "admin.html", "search.js", "admin.js", "search.css")
    page_text = "\n".join(scan(PAGE / name) for name in page_names)
    feed_urls: list[str] = []
    for folder in (CN, EXAMPLE, SECOND):
        publish = _publish(folder)
        if publish.get("feed"):
            feed_urls.append(f"{folder.name} publish.json has a feed")
        for path in folder.iterdir():
            if not path.is_file():
                continue
            for url in re.findall(r"https?://[^\s,\"']+", scan(path)):
                host = url.split("://", 1)[1].split("/", 1)[0]
                if host not in allowed:
                    feed_urls.append(url)
    admin_leaks: list[str] = []
    if "RIG_ADMIN_KEY" in page_text or ADMIN_CN in page_text or ADMIN_EX in page_text:
        admin_leaks.append("page source contains an admin key")
    if "rk_" in (PAGE / "admin.html").read_text(encoding="utf-8") or "rk_" in (PAGE / "admin.js").read_text(encoding="utf-8"):
        admin_leaks.append("admin page contains an rk_ key")
    service = asyncio.run(_loaded())
    client = TestClient(_app(service))
    shop = client.get("/")
    classic = client.get("/cn-classic")
    admin = client.get("/admin")
    rendered = shop.text + "\n" + classic.text + "\n" + admin.text + "\n" + client.get("/page/admin.js").text + "\n" + client.get("/page/search.js").text
    if "RIG_ADMIN_KEY" in rendered or ADMIN_CN in rendered or "review-admin" in rendered:
        admin_leaks.append("rendered page contains an admin key")
    demo_key = _key(CN)
    example_key = _key(EXAMPLE)
    archon_key = _key(ARCHON) if ARCHON.exists() else "rk_pub_archon"
    if example_key in shop.text or example_key in classic.text:
        admin_leaks.append("shopper page embeds the example catalogue key")
    if archon_key in shop.text:
        admin_leaks.append("root product page embeds an offline fixture key")
    if demo_key in classic.text:
        admin_leaks.append("classic shopper page embeds an offline fixture key")
    if "Custom Nation" in classic.text:
        admin_leaks.append("classic shopper page shows Custom Nation")
    feeds = asyncio.run(_feeds(service))
    if any(feeds.values()):
        feed_urls.append(f"loaded feeds {feeds}")
    payload = {
        "secret_hits": secret_hits,
        "distributor_hits": distributor_hits,
        "feed_urls": feed_urls,
        "admin_leaks": admin_leaks,
        "shopper_page_embeds_demo_catalogue_key": demo_key in classic.text,
        "root_embeds_archon_key": archon_key in shop.text,
        "shopper_page_embeds_example_publishable_key": example_key in shop.text or example_key in classic.text,
    }
    _record("static", payload)
    assert secret_hits == [], payload
    assert distributor_hits == [], payload
    assert feed_urls == [], payload
    assert admin_leaks == [], payload


async def _feeds(service: Service) -> dict[str, list[dict[str, Any]]]:
    return {
        "customnation": await service.store.feeds_for(CN_TENANT),
        "example": await service.store.feeds_for(EX_TENANT),
        "second": await service.store.feeds_for(SE_TENANT),
    }


def _seed_review_fits(service: Service) -> None:
    async def plant() -> None:
        for sku, name, category in (
            ("REVIEW-DOT", "Review Dot", "Optics"),
            ("REVIEW-GRIP", "Review Grip", "Grips"),
        ):
            await service.store.upsert_product(
                CN_TENANT,
                {
                    "sku": sku,
                    "name": name,
                    "brand": "Review",
                    "category": category,
                    "price": "1111.00",
                    "currency": "ZAR",
                    "image_url": "https://assets.local/review.jpg",
                    "active": True,
                    "attributes": {},
                    "family": "",
                },
            )
            await service.store.upsert_fit(
                CN_TENANT,
                {
                    "part_sku": sku,
                    "fits_sku": "STI-C2-9",
                    "fits_family": None,
                    "rule": {},
                    "source": "suggested",
                    "approved": False,
                    "note": "Waiting for a person",
                    "confidence": 0.55,
                },
            )

    asyncio.run(plant())


def _shot(page: Any, name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / name
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def test_browser_search_accessories_compare_admin(monkeypatch) -> None:
    """Click the shopper path, then approve and reject on the dealer page."""
    playwright_sync = pytest.importorskip("playwright.sync_api")
    monkeypatch.setenv("RIG_WIDGET_PUBLISHABLE_KEY", _key(CN))
    service = asyncio.run(_loaded(rate_limit=5000))
    _seed_review_fits(service)
    app = _app(service)
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=5173, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    shots: list[str] = []
    notes: list[str] = []
    try:
        assert server.started, "Rig page did not start on 127.0.0.1:5173"
        with playwright_sync.sync_playwright() as playwright:
            executable = os.environ.get("READ1_CHROMIUM_EXECUTABLE")
            browser = playwright.chromium.launch(
                channel=None if executable else "chrome",
                executable_path=executable,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(LOCAL_ORIGIN + "/cn-classic", wait_until="domcontentloaded")
            shots.append(_shot(page, "pr90-01-search.png"))
            page.fill("#q", "staccato c2")
            page.click("form.search button")
            page.wait_for_selector("text=Staccato C2")
            shots.append(_shot(page, "pr90-02-results.png"))
            results = page.locator("#results").inner_text()
            if "Staccato C2" not in results:
                notes.append("results missed Staccato C2")
            page.locator("#results button", has_text="Staccato C2").first.click()
            page.wait_for_selector("#show-accessories")
            if not page.locator("#groups").is_hidden():
                notes.append("accessories were visible before the prompt")
            if "Market average" in page.locator("#product").inner_text():
                notes.append("market prices showed before Compare prices")
            shots.append(_shot(page, "pr90-03-product.png"))
            page.click("#show-accessories")
            page.wait_for_selector("#groups >> text=Optics")
            groups = page.locator("#groups").inner_text()
            for label in ("Optics", "Grips", "Holsters", "Triggers", "Magazines", "Lights", "Aftermarket sights"):
                if label not in groups:
                    notes.append(f"missing group {label}")
            if "Review Dot" in groups or "Review Grip" in groups:
                notes.append("suggested fits were shown to the shopper")
            if "Cheely E2" in groups:
                notes.append("C2 showed the full-size grip")
            if "Why it fits" not in groups:
                notes.append("why line missing")
            bundle = page.locator("#bundle-total").inner_text().replace("\xa0", " ").replace("\u202f", " ")
            if "79 292" not in bundle or "ZAR" not in bundle:
                notes.append(f"bundle total {bundle!r}")
            shots.append(_shot(page, "pr90-04-accessories.png"))
            page.click("#compare")
            page.wait_for_selector("text=Market average")
            compare = page.locator("#compare-lines").inner_text().replace("\xa0", " ").replace("\u202f", " ")
            if "Custom Nation" in compare:
                notes.append("compare shows Custom Nation")
            if "Tervory price" not in compare:
                notes.append("retailer label missing")
            if "Market average: 59 000 ZAR" not in compare:
                notes.append(f"C2 market line missing in {compare[:400]!r}")
            if "Tervory price: 58 999 ZAR" not in compare:
                notes.append("C2 own price missing")
            shots.append(_shot(page, "pr90-05-compare.png"))
            lights = page.locator("#bundle-parts li", has_text="SureFire")
            lights.get_by_role("button", name="Swap part").click()
            page.locator(".options").get_by_role("button", name="Streamlight TLR-1 HL").click()
            page.wait_for_function(
                """() => {
                  const total = document.querySelector('#bundle-total');
                  const text = total ? total.textContent.replace(/\\s/g, ' ') : '';
                  return text.includes('77 092') || text.includes('77092');
                }"""
            )
            swapped = page.locator("#bundle-total").inner_text().replace("\xa0", " ").replace("\u202f", " ")
            if "77 092" not in swapped and "77092" not in swapped.replace(" ", ""):
                notes.append(f"swapped bundle total {swapped!r}")
            page.click("#compare")
            page.wait_for_function(
                """() => {
                  const box = document.querySelector('#compare-lines');
                  const text = box ? box.textContent : '';
                  return text.includes('not available') && !text.includes('Loading');
                }"""
            )
            compare_swapped = page.locator("#compare-lines").inner_text().replace("\xa0", " ").replace("\u202f", " ")
            if "Market average: not available" not in compare_swapped:
                notes.append(f"Streamlight has no market rows, got {compare_swapped[:500]!r}")
            if "Tervory price: 2 799 ZAR" not in compare_swapped:
                notes.append("Streamlight own price missing")
            shots.append(_shot(page, "pr90-05b-no-market.png"))
            page.goto(LOCAL_ORIGIN + "/admin", wait_until="domcontentloaded")
            if "review-admin" in page.content() or "RIG_ADMIN_KEY" in page.content():
                notes.append("admin key was in the admin page")
            page.fill("#admin-key", ADMIN_CN)
            page.click("#key-form button")
            page.wait_for_selector("text=Review Dot")
            page.wait_for_selector("text=Review Grip")
            shots.append(_shot(page, "pr90-06-admin.png"))
            page.locator("tr", has_text="Review Dot").get_by_role("button", name="Approve").click()
            page.wait_for_selector("text=Approved")
            page.locator("tr", has_text="Review Grip").get_by_role("button", name="Reject").click()
            page.wait_for_selector("text=Rejected")
            shots.append(_shot(page, "pr90-07-admin-decided.png"))
            page.goto(LOCAL_ORIGIN + "/cn-classic", wait_until="domcontentloaded")
            page.fill("#q", "staccato c2")
            page.click("form.search button")
            page.wait_for_selector("text=Staccato C2")
            page.locator("#results button", has_text="Staccato C2").first.click()
            page.wait_for_selector("#show-accessories")
            page.click("#show-accessories")
            page.wait_for_selector("#groups >> text=Review Dot")
            after = page.locator("#groups").inner_text()
            if "Review Grip" in after:
                notes.append("rejected grip was shown after review")
            if "Review Dot" not in after:
                notes.append("approved optic was still hidden")
            shots.append(_shot(page, "pr90-08-after-review.png"))
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    payload = {"notes": notes, "screenshots": shots}
    _record("browser", payload)
    assert notes == [], payload
