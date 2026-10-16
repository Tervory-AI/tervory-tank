"""Fresh unseen set for the PR #90 retest.

The builder had already seen tests/test_rig_pr90_independent.py. These 100
searches and 25 questions use different wording. Stand-in catalogues only.
No network, no distributor, no database. This file does not change Rig.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_rig_pr90_independent as old  # noqa: E402

from rigbox.rank import search as rank_search  # noqa: E402
from rigbox.service import Service  # noqa: E402

REPORT = Path("/tmp/rig-pr90-fresh.json")
SKILL_ASK = ROOT / "tank" / "skills" / "rig.ask" / "1.0.0" / "ground.py"
SKILL_SEARCH = ROOT / "tank" / "skills" / "rig.search" / "1.0.0" / "pure.py"
SCHEMA = ROOT / "tank" / "schema.sql"
APP = ROOT / "agents" / "rig" / "app.py"

_OPTICS = {"HOL-507C-X2", "TRIJ-RMR-T2"}
_HOLSTERS = {"TENICOR-VELO", "SAF-ALS-FULL"}
_MAGS = {"MAG-16", "MAG-17", "MAG-20"}
_LIGHTS = {"SF-X300U", "SL-TLR1"}
_TRIGGERS = {"ATLAS-FLAT", "REDD-TRIGGER"}
_SIGHTS = {"DAW-FO-FRONT", "TEN8-REAR"}
_GRIPS = {"CHEELY-E2", "CHEELY-C2"}

# (catalogue, query, acceptable ids). None of these strings are in the first harness.
_ROWS: list[tuple[str, set[str], list[str]]] = [
    ("customnation", {"STI-P-9"}, [
        "full size staccato handgun",
        "staccato model p 2011",
        "handgun called staccato p",
        "the p model staccato pistol",
    ]),
    ("customnation", {"STI-C2-9"}, [
        "compact staccato carry pistol",
        "staccato c2 carry gun",
        "the compact c2 from staccato",
        "carry sized staccato c2",
    ]),
    ("customnation", {"STI-XC-9"}, [
        "staccato xc race pistol",
        "competition staccato xc",
        "the xc handgun by staccato",
        "staccato model xc 2011",
    ]),
    ("customnation", {"TRIJ-RMR-T2"}, [
        "trijicon rmr type 2 optic",
        "type 2 rmr from trijicon",
        "rmr type 2 red dot optic",
        "trijicon adjustable rmr",
    ]),
    ("customnation", {"HOL-507C-X2"}, [
        "holosun 507c x2 optic",
        "507c red dot by holosun",
        "holosun x2 circle dot",
        "the 507c optic from holosun",
    ]),
    ("customnation", {"DAW-FO-FRONT"}, [
        "dawson precision fiber front",
        "fiber front post by dawson",
        "dawson precision front sight post",
        "front fiber sight dawson precision",
    ]),
    ("customnation", {"TEN8-REAR"}, [
        "10-8 performance rear iron",
        "rear sight by 10-8 performance",
        "ten-eight rear sight",
        "10 8 performance rear blade",
    ]),
    ("customnation", {"CHEELY-E2"}, [
        "cheely e2 aluminum grip module",
        "e2 grip module by cheely",
        "cheely e2 2011 grip",
        "aluminum e2 grip from cheely",
    ]),
    ("customnation", {"CHEELY-C2"}, [
        "grip module cheely makes in a compact size",
        "compact grip module by cheely",
        "cheely grip sized compact",
        "the compact cheely grip module",
    ]),
    ("customnation", {"ATLAS-FLAT"}, [
        "atlas gunworks flat trigger",
        "flat faced trigger made by atlas",
        "atlas flat faced trigger shoe",
        "trigger shoe from atlas",
    ]),
    ("customnation", {"REDD-TRIGGER"}, [
        "shoe shaped trigger from the red dirt brand",
        "trigger shoe made by red dirt",
        "red dirt 2011 trigger",
        "shoe from red dirt triggers",
    ]),
    ("customnation", {"SAF-ALS-FULL"}, [
        "safariland als retention holster",
        "als duty holster from safariland",
        "safariland level duty holster",
        "retention holster by safariland",
    ]),
    ("customnation", {"TENICOR-VELO"}, [
        "tenicor velo appendix holster",
        "velo appendix holster by tenicor",
        "tenicor holster called velo",
        "appendix holster from tenicor",
    ]),
    ("customnation", {"MAG-17"}, [
        "check-mate seventeen round magazine",
        "17 round checkmate 2011 mag",
        "magazine seventeen rounds check-mate",
        "checkmate mag holding 17",
    ]),
    ("customnation", {"MAG-20"}, [
        "check-mate twenty round magazine",
        "20 round checkmate 2011 mag",
        "magazine twenty rounds check-mate",
        "checkmate mag holding 20",
    ]),
    ("customnation", {"MAG-16"}, [
        "check-mate sixteen round magazine",
        "16 round checkmate 2011 mag",
        "magazine sixteen rounds check-mate",
        "checkmate mag holding 16",
    ]),
    ("customnation", {"SF-X300U"}, [
        "surefire x300 ultra weapon light",
        "x300u weapon light by surefire",
        "surefire ultra pistol light",
        "weapon light surefire x300u",
    ]),
    ("customnation", {"SL-TLR1"}, [
        "streamlight tlr-1 hl weapon light",
        "tlr1 hl light by streamlight",
        "streamlight hl pistol light",
        "weapon light streamlight tlr-1 hl",
    ]),
    ("example", {"EXAMPLE-RIFLE-01"}, [
        "examplebrand three oh eight rifle",
        "308 rifle by examplebrand",
        "example brand twenty inch rifle",
        "rifle in 308 win from examplebrand",
    ]),
    ("example", {"EXAMPLE-SCOPE-01"}, [
        "exampleoptics four to sixteen scope",
        "variable scope by exampleoptics",
        "example optics 4-16 scope",
        "scope tube 30mm exampleoptics",
    ]),
    ("example", {"EXAMPLE-RINGS-30"}, [
        "exampleoptics thirty mm rings",
        "picatinny ring set by exampleoptics",
        "30mm ring mount example optics",
        "rings that clamp a picatinny base",
    ]),
    ("second", {"SECOND-LAMP-01"}, [
        "secondbrand desk lamp light",
        "desk lamp made by secondbrand",
        "table lamp from second brand",
        "second brand reading lamp",
    ]),
    ("second", {"SECOND-SHADE-01"}, [
        "secondbrand replacement lamp shade",
        "shade made by secondbrand",
        "lamp shade from second brand",
        "second brand fabric shade",
    ]),
    ("customnation", _OPTICS, [
        "which optic pairs with a staccato pistol",
        "red dot optic on a compact pistol",
    ]),
    ("customnation", _HOLSTERS, [
        "need a holster compatible with the c2",
    ]),
    ("customnation", _MAGS, [
        "magazine compatible with the xc handgun",
    ]),
    ("customnation", _LIGHTS, [
        "weapon light to mount on staccato",
    ]),
    ("customnation", _TRIGGERS, [
        "trigger shoe to use on a 2011",
    ]),
    ("customnation", _SIGHTS, [
        "front sight post to replace on a pistol",
    ]),
    ("customnation", _GRIPS, [
        "grip module that suits the compact staccato",
    ]),
]

FRESH: list[tuple[str, str, set[str]]] = [
    (catalogue, phrase, set(ok))
    for catalogue, ok, phrases in _ROWS
    for phrase in phrases
]

# 25 questions the sheets do not answer. Wording is not the first harness.
# The last six are substring traps: "sig" sits inside "sight", "cat" inside
# "staccato", and a red-dot claim can be assembled from two real rows.
OUTSIDE = [
    "How much is a Glock 43X MOS today?",
    "Do you sell a Walther PDP Pro SD?",
    "Is the CZ Shadow 2 Compact stocked?",
    "Can I get a Vortex Razor HD LHT?",
    "What about a Nightforce ATACR 1-8?",
    "Show me Magpul PMAG 30 AR magazines",
    "Do you carry an EOTech EXPS3-0?",
    "Is an Aimpoint Duty RDS available?",
    "Is the Staccato legal to own in California?",
    "What is the shipping fee to Johannesburg?",
    "Can I finance the XC over 36 months?",
    "Does Trijicon include a warranty I can claim?",
    "What VAT rate applies to the Holosun?",
    "Will you ship a suppressor alongside the C2?",
    "Do you stock a Staccato C3 Duo?",
    "Is the Holosun 509T X2 listed?",
    "Do you have the Trijicon SRO 1 MOA?",
    "Is the SureFire X300V-A on the shelf?",
    "Do you sell the Dawson Ice Magwell?",
    "Is the Staccato a Sig?",
    "Is the Staccato C2 a compact red dot?",
    "Does Holosun make the Staccato?",
    "Is the Staccato a cat?",
    "Is the Cheely grip a red dot?",
    "Can the Atlas trigger be a holster?",
]
UNSEEN_SEARCH = "Walther PDP Pro"
REMIX_ANSWER = "The Staccato C2 is a compact red dot Holosun sight"
REMIX_CITES = ["STI-C2-9", "HOL-507C-X2", "DAW-FO-FRONT"]


class Remix:
    """Cite real rows and answer with catalogue words arranged into a false claim."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        return json.dumps({"answer": REMIX_ANSWER, "cites": REMIX_CITES})


def _record(name: str, payload: dict[str, Any]) -> None:
    current: dict[str, Any] = {}
    if REPORT.exists():
        current = json.loads(REPORT.read_text(encoding="utf-8"))
    current[name] = payload
    REPORT.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")
    print(f"\nRIG-PR90-FRESH {name}: {json.dumps(payload, default=str)}")


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _percentiles(samples: list[float]) -> tuple[float, float, float]:
    ordered = sorted(samples)
    cuts = statistics.quantiles(ordered, n=100, method="inclusive")
    return cuts[49], cuts[94], ordered[-1]


@pytest.fixture(scope="module")
def fresh_world() -> dict[str, Any]:
    service = asyncio.run(old._loaded(rate_limit=5000))
    client = TestClient(old._app(service))
    client.__enter__()
    payload = {
        "service": service,
        "client": client,
        "keys": {
            "customnation": old._key(old.CN),
            "example": old._key(old.EXAMPLE),
            "second": old._key(old.SECOND),
        },
        "origins": {
            "customnation": old.CN_ORIGIN,
            "example": old.CN_ORIGIN,
            "second": old.SE_ORIGIN,
        },
        "tenants": {
            "customnation": old.CN_TENANT,
            "example": old.EX_TENANT,
            "second": old.SE_TENANT,
        },
    }
    yield payload
    client.__exit__(None, None, None)


def test_fresh_set_is_unseen() -> None:
    """The builder's harness must not contain these strings."""
    assert len(FRESH) == 100, len(FRESH)
    assert len(OUTSIDE) == 25, len(OUTSIDE)
    fresh_q = [text.casefold() for _, text, _ok in FRESH]
    assert len(fresh_q) == len(set(fresh_q))
    old_q = {text.casefold() for _cat, text, _ok in old.QUERIES}
    overlap = sorted(set(fresh_q) & old_q)
    assert overlap == [], overlap
    fresh_out = [text.casefold() for text in OUTSIDE]
    assert len(fresh_out) == len(set(fresh_out))
    old_out = {text.casefold() for text in old.OUTSIDE}
    shared = sorted(set(fresh_out) & old_out)
    assert shared == [], shared
    assert UNSEEN_SEARCH.casefold() not in old_q


def test_fresh_gate_1_unseen_fits_stay_hidden() -> None:
    """Suggested and rejected rows with names the first harness never used stay off the shopper page."""
    service = asyncio.run(old._loaded(rate_limit=5000))
    client = TestClient(old._app(service))
    checked = 0
    violations: list[str] = []

    async def walk() -> None:
        nonlocal checked
        await service.store.upsert_product(
            old.CN_TENANT,
            {
                "sku": "FRESH-SUG-OPT",
                "name": "Unseen Suggested Optic",
                "brand": "Unseen",
                "category": "Optics",
                "price": "21.00",
                "currency": "ZAR",
                "image_url": "https://assets.local/fresh-sug.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            old.CN_TENANT,
            {
                "part_sku": "FRESH-SUG-OPT",
                "fits_sku": "STI-P-9",
                "fits_family": None,
                "rule": {},
                "source": "suggested",
                "approved": False,
                "note": "fresh suggested",
                "confidence": 0.33,
            },
        )
        await service.store.upsert_product(
            old.CN_TENANT,
            {
                "sku": "FRESH-REJ-BEZ",
                "name": "Unseen Rejected Bezel",
                "brand": "Unseen",
                "category": "Optics",
                "price": "22.00",
                "currency": "ZAR",
                "image_url": "https://assets.local/fresh-rej.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            old.CN_TENANT,
            {
                "part_sku": "FRESH-REJ-BEZ",
                "fits_sku": "STI-P-9",
                "fits_family": None,
                "rule": {},
                "source": "rejected",
                "approved": False,
                "note": "fresh rejected",
                "confidence": 0.1,
            },
        )
        await service.store.upsert_product(
            old.EX_TENANT,
            {
                "sku": "FRESH-EX-BRACE",
                "name": "Unseen Example Brace",
                "brand": "ExampleOptics",
                "category": "mount",
                "price": "23.00",
                "currency": "ZAR",
                "image_url": "https://example.com/fresh-brace.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            old.EX_TENANT,
            {
                "part_sku": "FRESH-EX-BRACE",
                "fits_sku": "EXAMPLE-RIFLE-01",
                "fits_family": None,
                "rule": {},
                "source": "suggested",
                "approved": False,
                "note": "fresh example",
                "confidence": 0.2,
            },
        )
        hidden = (
            "Unseen Suggested Optic",
            "Unseen Rejected Bezel",
            "Unseen Example Brace",
            "FRESH-SUG-OPT",
            "FRESH-REJ-BEZ",
            "FRESH-EX-BRACE",
        )
        for tenant, centre in ((old.CN_TENANT, "STI-P-9"), (old.EX_TENANT, "EXAMPLE-RIFLE-01")):
            graph = await service.graph(tenant, centre)
            setups = await service.setups(tenant, centre)
            detail = await service.product(tenant, centre)
            setup = setups["setups"][0]
            role = setup["parts"][1]["product"]["category"]
            swapped = await service.swap(tenant, setup, role)
            blob = old._shopper_blob(graph) + old._shopper_blob(setups) + old._shopper_blob(detail)
            blob += old._shopper_blob(swapped)
            for name in hidden:
                checked += 1
                if name in blob:
                    violations.append(f"{centre} shopper saw {name}")
        page = client.get(
            "/v1/rig/graph/STI-P-9",
            headers={"X-Rig-Key": old._key(old.CN), "Origin": old.CN_ORIGIN},
        )
        assert page.status_code == 200
        checked += 1
        if "Unseen Suggested" in page.text or "Unseen Rejected" in page.text:
            violations.append("HTTP graph showed an unapproved fresh fit")
        waiting = await service.suggested_fits(old.CN_TENANT)
        waiting_ids = {row["part_sku"] for row in waiting["fits"]}
        checked += 2
        if "FRESH-SUG-OPT" not in waiting_ids:
            violations.append("admin list missed the fresh suggested fit")
        if "FRESH-REJ-BEZ" in waiting_ids:
            violations.append("admin list showed the fresh rejected fit")
        await service.approve(old.CN_TENANT, "FRESH-SUG-OPT", "STI-P-9", None)
        await service.reject(old.CN_TENANT, "MAG-20", "STI-P-9", None)
        after = await service.graph(old.CN_TENANT, "STI-P-9")
        after_ids = {item["id"] for branch in after["branches"] for item in branch["products"]}
        checked += 3
        if "FRESH-SUG-OPT" not in after_ids:
            violations.append("approved fresh fit stayed hidden")
        if "MAG-20" in after_ids:
            violations.append("rejected magazine stayed on the P")
        if "FRESH-REJ-BEZ" in after_ids:
            violations.append("rejected fresh fit was shown")

    asyncio.run(walk())
    rate = 100.0 if checked and not violations else 0.0
    payload = {"checked": checked, "violations": len(violations), "rate_pct": rate, "examples": violations[:8]}
    _record("1_approved_fits", payload)
    assert not violations, payload
    assert rate == 100.0


def test_fresh_gate_2_search_top3(fresh_world: dict[str, Any]) -> None:
    """100 unseen shopper queries. Pass when the right product is in the top 3 for at least 90%."""
    client: TestClient = fresh_world["client"]
    hits = 0
    misses: list[dict[str, Any]] = []
    for catalogue, text, acceptable in FRESH:
        response = client.get(
            "/v1/rig/search",
            params={"q": text, "limit": 12},
            headers={
                "X-Rig-Key": fresh_world["keys"][catalogue],
                "Origin": fresh_world["origins"][catalogue],
            },
        )
        assert response.status_code == 200, (text, response.status_code, response.text)
        found = old._ids(response.json())[:3]
        if any(sku in found for sku in acceptable):
            hits += 1
        else:
            misses.append({"q": text, "catalogue": catalogue, "want": sorted(acceptable), "got": found})
    rate = 100.0 * hits / len(FRESH)
    payload = {
        "queries": len(FRESH),
        "hits": hits,
        "misses": len(misses),
        "rate_pct": round(rate, 2),
        "miss_list": misses,
    }
    _record("2_search", payload)
    assert rate >= 90.0, payload


def test_fresh_gate_3_outside_catalogue() -> None:
    """Unseen out-of-catalogue questions, including a remix the first harness never sent."""
    remix = Remix()
    service = asyncio.run(old._loaded(remix, rate_limit=5000))
    refused = 0
    fabricated: list[dict[str, Any]] = []

    async def ask_all() -> None:
        nonlocal refused
        for question in OUTSIDE:
            before = len(remix.calls)
            answer = await service.ask(old.CN_TENANT, "STI-C2-9", question)
            text = str(answer.get("answer") or "")
            cites = list(answer.get("cites") or [])
            clean = text == "I don't know" and cites == [] and "red dot" not in text.lower()
            if clean:
                refused += 1
            else:
                fabricated.append(
                    {
                        "q": question,
                        "answer": text,
                        "cites": cites,
                        "model_called": len(remix.calls) > before,
                    }
                )
        found = await service.search(old.CN_TENANT, UNSEEN_SEARCH, 12)
        if found["results"]:
            fabricated.append({"q": UNSEEN_SEARCH, "answer": found["results"], "cites": [], "model_called": False})

    asyncio.run(ask_all())
    rate = 100.0 * refused / len(OUTSIDE)
    bug = ""
    if fabricated:
        bug = (
            "agents/rig/rigbox/claims.py:156-161 answerable() treats any subject token as in-catalogue "
            "when it is a substring of some row; claims.py:192-202 _supported() keeps an answer when "
            "every word is a substring of the cited rows combined, so one false sentence can cite "
            "the pistol, the optic, and the sight and pass."
        )
    payload = {
        "questions": len(OUTSIDE),
        "refused": refused,
        "fabricated": len(fabricated),
        "rate_pct": round(rate, 2),
        "model_calls": len(remix.calls),
        "unseen_search": UNSEEN_SEARCH,
        "unseen_search_results": 0 if not any(item["q"] == UNSEEN_SEARCH for item in fabricated) else 1,
        "examples": fabricated,
        "bug": bug,
    }
    _record("3_i_dont_know", payload)
    assert rate == 100.0, payload
    assert not fabricated, payload


def test_fresh_gate_4_isolation() -> None:
    """A second shared sku and an unseen suggested fit. Crossings must be 0."""
    service = asyncio.run(old._loaded(rate_limit=5000))
    client = TestClient(old._app(service))
    cn_key = old._key(old.CN)
    ex_key = old._key(old.EXAMPLE)
    crossings: list[str] = []

    def shop(key: str, origin: str) -> dict[str, str]:
        return {"X-Rig-Key": key, "Origin": origin}

    def leak(label: str, text: str, needles: list[str]) -> None:
        for needle in needles:
            if needle and needle in text:
                crossings.append(f"{label} contains {needle}")

    async def plant() -> None:
        for tenant, name, price, source in (
            (old.CN_TENANT, "North Stand-in Widget", "4107.00", "North Stand Shop"),
            (old.EX_TENANT, "South Stand-in Widget", "8203.00", "South Stand Shop"),
        ):
            await service.store.upsert_product(
                tenant,
                {
                    "sku": "FRESH-SHARED-9",
                    "name": name,
                    "brand": "Standin",
                    "category": "Widgets",
                    "price": price,
                    "currency": "ZAR",
                    "image_url": "https://assets.local/fresh-shared.jpg",
                    "active": True,
                    "attributes": {},
                    "family": "",
                },
            )
            existing = await service.store.market_for(
                tenant, [row["sku"] for row in await service.store.products(tenant)]
            )
            existing.append(
                {
                    "sku": "FRESH-SHARED-9",
                    "source": source,
                    "price": price,
                    "currency": "ZAR",
                    "seen_at": "2026-04-02",
                }
            )
            await service.store.replace_market(tenant, existing)
        await service.store.upsert_product(
            old.EX_TENANT,
            {
                "sku": "FRESH-EX-SECRET",
                "name": "Unseen Example Brace",
                "brand": "ExampleOptics",
                "category": "mount",
                "price": "5.00",
                "currency": "ZAR",
                "image_url": "https://example.com/fresh-secret.jpg",
                "active": True,
                "attributes": {},
                "family": "",
            },
        )
        await service.store.upsert_fit(
            old.EX_TENANT,
            {
                "part_sku": "FRESH-EX-SECRET",
                "fits_sku": "EXAMPLE-RIFLE-01",
                "fits_family": None,
                "rule": {},
                "source": "suggested",
                "approved": False,
                "note": "fresh secret",
                "confidence": 0.2,
            },
        )

    asyncio.run(plant())
    cn_search = client.get(
        "/v1/rig/search",
        params={"q": "North Stand-in Widget"},
        headers=shop(cn_key, old.CN_ORIGIN),
    )
    leak("cn shared search", cn_search.text, ["South Stand-in Widget", "South Stand Shop", "8203"])
    if "North Stand-in Widget" not in cn_search.text:
        crossings.append("cn missed its own fresh shared product")
    ex_search = client.get(
        "/v1/rig/search",
        params={"q": "Stand-in Widget"},
        headers=shop(ex_key, old.CN_ORIGIN),
    )
    leak("ex shared search", ex_search.text, ["North Stand-in Widget", "North Stand Shop", "4107"])
    foreign = client.get(
        "/v1/rig/products/FRESH-EX-SECRET",
        headers=shop(cn_key, old.CN_ORIGIN),
    )
    if foreign.status_code != 404:
        crossings.append(f"cn opened the example secret ({foreign.status_code})")
    leak("cn secret product", foreign.text, ["Unseen Example Brace"])
    cn_admin = client.get("/v1/rig/admin/fits", headers={"X-Rig-Key": old.ADMIN_CN})
    leak("cn admin", cn_admin.text, ["Unseen Example Brace", "FRESH-EX-SECRET", "South Stand Shop"])
    stolen = client.post(
        "/v1/rig/admin/fits/approve",
        headers={"X-Rig-Key": old.ADMIN_CN},
        json={"part_sku": "FRESH-EX-SECRET", "fits_sku": "EXAMPLE-RIFLE-01"},
    )
    if stolen.status_code != 404:
        crossings.append(f"cn admin approved an example fit ({stolen.status_code})")
    cn_cmp = client.post(
        "/v1/rig/compare",
        headers=shop(cn_key, old.CN_ORIGIN),
        json={"product_ids": ["FRESH-SHARED-9"]},
    )
    ex_cmp = client.post(
        "/v1/rig/compare",
        headers=shop(ex_key, old.CN_ORIGIN),
        json={"product_ids": ["FRESH-SHARED-9"]},
    )
    leak("cn compare", cn_cmp.text, ["South Stand Shop", "South Stand-in Widget", "8203"])
    leak("ex compare", ex_cmp.text, ["North Stand Shop", "North Stand-in Widget", "4107"])
    if cn_cmp.status_code == 200 and int(cn_cmp.json()["lines"][0]["market"]["amount"]) != 4107:
        crossings.append(f"cn market mixed {cn_cmp.json()['lines'][0]['market']}")
    if ex_cmp.status_code == 200 and int(ex_cmp.json()["lines"][0]["market"]["amount"]) != 8203:
        crossings.append(f"ex market mixed {ex_cmp.json()['lines'][0]['market']}")
    monkey = os.environ.get("RIG_ADMIN_KEY")
    os.environ["RIG_ADMIN_KEY"] = "fresh-env-admin-must-fail"
    try:
        env_attempt = client.get(
            "/v1/rig/admin/fits",
            headers={"X-Rig-Key": "fresh-env-admin-must-fail"},
        )
    finally:
        if monkey is None:
            os.environ.pop("RIG_ADMIN_KEY", None)
        else:
            os.environ["RIG_ADMIN_KEY"] = monkey
    if env_attempt.status_code != 401:
        crossings.append(f"env admin key spanned tenants ({env_attempt.status_code})")
    payload = {"checks_with_crossings": len(crossings), "crossings": crossings}
    _record("4_isolation", payload)
    assert crossings == [], payload


def test_fresh_gate_5_search_speed(fresh_world: dict[str, Any]) -> None:
    """The 100 unseen searches, timed on the shopper HTTP path."""
    client: TestClient = fresh_world["client"]
    samples: list[float] = []
    for catalogue, text, _ok in FRESH:
        started = time.perf_counter()
        response = client.get(
            "/v1/rig/search",
            params={"q": text, "limit": 12},
            headers={
                "X-Rig-Key": fresh_world["keys"][catalogue],
                "Origin": fresh_world["origins"][catalogue],
            },
        )
        samples.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200
    p50, p95, slowest = _percentiles(samples)
    over = sum(1 for sample in samples if sample >= 300)
    payload = {
        "n": len(samples),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(slowest, 3),
        "over_300": over,
        "path": "HTTP GET /v1/rig/search on the in-memory ranker",
    }
    _record("5_speed", payload)
    assert over == 0, payload
    assert p95 < 300, payload


def test_live_shopper_path_skips_tank_skills() -> None:
    """Deployed shopper search and ask do not call tank/skills rig.search or rig.ask.

    Those packages still keep an invented answer when one cite is a real id.
    The shopper calls Tank /v1/route (policy model luna) and then claims.py.
    """
    skill_ask = _load_module(SKILL_ASK, "rig_ask_skill_ground_fresh")
    skill_search = _load_module(SKILL_SEARCH, "rig_search_skill_pure_fresh")
    service = asyncio.run(old._loaded(old.Hostile(), rate_limit=5000))

    async def compare() -> dict[str, Any]:
        products = await service.store.products(old.CN_TENANT)
        fits = await service.store.fits(old.CN_TENANT)
        public = [
            {
                "id": str(row.get("sku") or ""),
                "sku": str(row.get("sku") or ""),
                "name": str(row.get("name") or ""),
                "brand": str(row.get("brand") or ""),
                "category": str(row.get("category") or ""),
                "attributes": row.get("attributes") or {},
                "tenant_id": old.CN_TENANT,
                "active": True,
                "family": row.get("family") or "",
                "price": row.get("price"),
                "currency": row.get("currency") or "",
            }
            for row in products
        ]
        question = "What battery does the SureFire take?"
        payload = {"question": question, "products": public, "fits": fits}
        phantom = json.dumps(
            {
                "answer": "The Phantom Suppressor X9 costs 12345 ZAR and is in stock.",
                "cites": ["PHANTOM-X9", "STI-C2-9"],
            }
        )
        skill_out = skill_ask.ask(payload, phantom)
        shop_out = await service.ask(old.CN_TENANT, "STI-C2-9", question)
        probes = ["optic for staccato", "compact 2011", "red dot for staccato", "magazine for staccato p"]
        rows = []
        for query in probes:
            body = {"tenant_id": old.CN_TENANT, "q": query, "limit": 3, "products": public}
            live = await service.search(old.CN_TENANT, query, 3)
            rows.append(
                {
                    "q": query,
                    "live": [item["id"] for item in live["results"]],
                    "rank": rank_search(body)["ids"][:3],
                    "skill": skill_search.search(body)["ids"][:3],
                }
            )
        return {"skill_ask": skill_out, "shop_ask": shop_out, "search": rows}

    compared = asyncio.run(compare())
    search_src = inspect.getsource(Service.search)
    ask_src = inspect.getsource(Service.ask)
    app_src = APP.read_text(encoding="utf-8")
    schema = SCHEMA.read_text(encoding="utf-8")
    ask_line = next(line.strip() for line in schema.splitlines() if "'rig.ask'" in line)
    complete_src = app_src[app_src.index("class _TankModels") : app_src.index("def _public_report")]
    skill_fabricates = "Phantom" in str(compared["skill_ask"].get("answer"))
    shop_refuses = compared["shop_ask"].get("answer") == "I don't know" and compared["shop_ask"].get("cites") == []
    live_matches_rank = all(row["live"] == row["rank"] for row in compared["search"])
    diverges = [row for row in compared["search"] if row["live"] != row["skill"]]
    payload = {
        "shopper_search_calls_rank": "rank_room" in search_src and "search_rows" not in search_src,
        "shopper_ask_calls_claims": "grounded_answer" in ask_src and "answerable" in ask_src,
        "shopper_ask_imports_skill": "tank/skills" in ask_src or "rig.ask" in ask_src and "skill" in ask_src,
        "tank_complete_calls_route": ".route(" in complete_src and "run_skill" not in complete_src,
        "policy_rig_ask": ask_line,
        "policy_model_is_luna": "'luna'" in ask_line and "skill:rig.ask" not in ask_line,
        "skill_ask_keeps_phantom": skill_fabricates,
        "shopper_ask_drops_phantom": shop_refuses,
        "live_search_equals_rank": live_matches_rank,
        "probes_where_skill_differs": diverges,
        "deployed_path": (
            "HTTP /v1/rig/search -> Service.search -> rigbox.rank.search. "
            "HTTP /v1/rig/ask -> Service.ask -> claims.answerable/grounded_answer around "
            "models.complete -> TankClient.route -> POST /v1/route. "
            "Policy model for rig.ask is luna, so run_route returns raw model text and does not run "
            "tank/skills/rig.ask. The skill still fabricates if something calls /v1/skala/rig.ask/run "
            "or the policy is later pointed at skill:rig.ask@1.0.0."
        ),
    }
    _record("live_path", payload)
    assert payload["shopper_search_calls_rank"]
    assert payload["shopper_ask_calls_claims"]
    assert payload["tank_complete_calls_route"]
    assert payload["policy_model_is_luna"]
    assert skill_fabricates
    assert shop_refuses
    assert live_matches_rank
    assert diverges, payload
