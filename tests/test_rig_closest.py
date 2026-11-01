"""A near-miss model code is a closest match, not an exact hit.

These cases use different wording from the review sets. A code that is not
on a row stays out of the exact results. The real row, when one is close,
comes back with exact_match false and the words "Closest matches".
"""

from __future__ import annotations

from rig_fixture_loader import load_catalogue

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.page_route import mount_page  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

CATALOGUES = ROOT / "tests" / "fixtures" / "rig_catalogues"
CN = "33333333-3333-4333-8333-333333333333"
EXAMPLE = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
PAGE = ROOT / "agents" / "rig" / "rigbox" / "page"
KEY = "rk_pub_customnation"
ORIGIN = "https://rig.tervory.com"


class Quiet:
    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type, messages
        return ""


async def _service() -> Service:
    service = Service(MemoryStore(), Quiet())
    for name in ("customnation", "example", "second"):
        report = await load_catalogue(service, CATALOGUES / name)
        assert report["products"]["rejected"] == []
    return service


def _ids(body: dict) -> list[str]:
    return [str(item["id"]) for item in body.get("results") or []]


def _names(body: dict) -> list[str]:
    return [str(item["name"]) for item in body.get("results") or []]


@pytest.mark.asyncio
async def test_a_different_model_code_is_not_an_exact_hit() -> None:
    service = await _service()
    bare = await service.search(CN, "X300V", 12)
    assert bare["exact_match"] is False
    assert bare["message"] == "No exact match for X300V."
    assert "SF-X300U" in _ids(bare)
    assert all("X300V" not in name for name in _names(bare))

    branded = await service.search(CN, "surefire X300V", 12)
    assert branded["exact_match"] is False
    assert "X300V" in branded["message"]
    assert "No exact match" in branded["message"]
    assert _ids(branded)[0] == "SF-X300U"

    centre = await service.search(CN, "lumaworks C3", 12)
    assert centre["exact_match"] is False
    assert centre["message"] == "No exact match for C3."
    assert set(_ids(centre)) >= {"STI-C2-9", "STI-P-9", "STI-XC-9"}
    assert all("C3" not in name for name in _names(centre))

    optic = await service.search(CN, "holosun 509T", 12)
    assert optic["exact_match"] is False
    assert optic["message"] == "No exact match for 509T."
    assert "HOL-507C-X2" in _ids(optic)
    assert all("509" not in name for name in _names(optic))

    sight = await service.search(CN, "trijicon SRO", 12)
    assert sight["exact_match"] is False
    assert sight["message"] == "No exact match for SRO."
    assert _ids(sight)[0] == "TRIJ-RMR-T2"

    lamp = await service.search(CN, "streamlight TLR-7A", 12)
    assert lamp["exact_match"] is False
    assert lamp["message"] == "No exact match for TLR-7A."
    assert _ids(lamp)[0] == "SL-TLR1"
    assert all("7A" not in name and "7a" not in name for name in _names(lamp))


@pytest.mark.asyncio
async def test_a_real_model_and_a_relation_stay_exact() -> None:
    service = await _service()
    exact = await service.search(CN, "LumaWorks C2", 12)
    assert exact["exact_match"] is True
    assert "message" not in exact
    assert _ids(exact)[0] == "STI-C2-9"

    scope = await service.search(EXAMPLE, "scope", 12)
    assert scope["exact_match"] is True
    assert _ids(scope) == ["EXAMPLE-SCOPE-01"]

    paired = await service.search(CN, "optic pairs with lumaworks", 3)
    assert paired["exact_match"] is True
    assert _ids(paired)[0] in {"HOL-507C-X2", "TRIJ-RMR-T2"}

    shade = await service.search(SECOND, "shade to go with the lamp", 3)
    assert shade["exact_match"] is True
    assert _ids(shade)[0] == "SECOND-SHADE-01"

    assert await service.search(CN, "sig", 12) == {"results": []}
    assert await service.search(CN, "Glock 19", 12) == {"results": []}
    real_light = await service.search(CN, "TLR-1", 12)
    assert real_light["exact_match"] is True
    assert _ids(real_light)[0] == "SL-TLR1"
    real_sight = await service.search(CN, "RMR Type 2", 12)
    assert real_sight["exact_match"] is True
    assert _ids(real_sight)[0] == "TRIJ-RMR-T2"


@pytest.mark.asyncio
async def test_a_single_digit_in_a_model_code_must_be_on_that_row() -> None:
    service = await _service()
    light = await service.search(CN, "TLR-7", 12)
    assert light["exact_match"] is False
    assert light["message"] == "No exact match for TLR-7."
    assert "SL-TLR1" in _ids(light)
    assert all("TLR-7" not in name for name in _names(light))

    named = await service.search(CN, "streamlight TLR-7", 12)
    assert named["exact_match"] is False
    assert "TLR-7" in named["message"]
    assert _ids(named)[0] == "SL-TLR1"

    sight = await service.search(CN, "RMR Type 3", 12)
    assert sight["exact_match"] is False
    assert sight["message"] == "No exact match for Type 3."
    assert _ids(sight)[0] == "TRIJ-RMR-T2"
    assert all("Type 3" not in name for name in _names(sight))

    spaced = await service.search(CN, "TLR 7", 12)
    assert spaced["exact_match"] is False
    assert spaced["message"] == "No exact match for TLR 7."
    assert _ids(spaced)[0] == "SL-TLR1"

    shorter = await service.search(CN, "Holosun 507", 12)
    assert shorter["exact_match"] is False
    assert "507" in shorter["message"]
    assert _ids(shorter)[0] == "HOL-507C-X2"
    assert all(name != "Holosun 507" for name in _names(shorter))


def _word_file(name: str) -> list[str]:
    lines = (ROOT / "agents" / "rig" / name).read_text(encoding="utf-8").splitlines()
    return [line.split("#", 1)[0].strip().lower() for line in lines if line.strip() and not line.startswith("#")]


@pytest.mark.asyncio
async def test_the_word_after_a_brand_is_exact_only_from_the_catalogue_or_the_glossary() -> None:
    english = _word_file("english-20k.txt")
    glossary = _word_file("shopping.txt")
    assert len(english) == 20000
    assert len(glossary) >= 300
    assert len(glossary) == len(set(glossary))
    descriptors = (
        "cheap",
        "spare",
        "top",
        "kit",
        "daily",
        "quick",
        "bag",
        "buy",
        "gun",
        "set",
        "rig",
        "extra",
        "basic",
        "black",
        "small",
        "best",
        "new",
        "used",
        "premium",
        "budget",
        "nylon",
        "leather",
        "kydex",
        "iwb",
        "owb",
        "aiwb",
        "fde",
        "odg",
        "tan",
        "holster",
        "case",
        "mount",
        "carry",
        "compact",
        "fiber",
    )
    assert all(word in glossary for word in descriptors)
    # English words and short codes are not descriptors, even when the frequency list knows them.
    for word in ("scout", "turbo", "ice", "cs", "hd", "eps", "oh", "up", "malus", "certum"):
        assert word not in glossary
        assert word in english or word in {"malus", "certum"}
    service = await _service()
    for word in descriptors:
        for text in (f"{word} tenicor", f"tenicor {word}", f"holosun {word}"):
            found = await service.search(CN, text, 12)
            assert found["results"], text
            assert found["exact_match"] is True, text
            assert "message" not in found
    # Before the brand, the frequency list still applies: these are not model codes.
    for text in (
        "scout lumaworks",
        "turbo holosun",
        "ice dawson",
        "cs lumaworks",
        "hd lumaworks",
        "eps holosun",
        "oh lumaworks",
        "up holosun",
        "zqxv tenicor",
        "iwb tenicor",
    ):
        found = await service.search(CN, text, 12)
        assert found["results"], text
        assert found["exact_match"] is True, text
        assert "message" not in found
    between = await service.search(CN, "tenicor cheap zqxv", 12)
    assert between["exact_match"] is True
    assert "message" not in between
    for text, phrase, sku in (
        ("Tenicor iwb", "iwb", "TENICOR-VELO"),
        ("Safariland fde", "fde", "SAF-ALS-FULL"),
        ("Holosun odg", "odg", "HOL-507C-X2"),
    ):
        found = await service.search(CN, text, 12)
        assert found["exact_match"] is True, text
        assert "message" not in found
        assert _ids(found)[0] == sku
    stocked = (
        ("LumaWorks P", "STI-P-9"),
        ("LumaWorks XC", "STI-XC-9"),
        ("Safariland ALS", "SAF-ALS-FULL"),
        ("Streamlight HL", "SL-TLR1"),
        ("Atlas flat", "ATLAS-FLAT"),
        ("Cheely compact", "CHEELY-C2"),
        ("Dawson fiber", "DAW-FO-FRONT"),
        ("RMR Type 2", "TRIJ-RMR-T2"),
    )
    for text, sku in stocked:
        found = await service.search(CN, text, 12)
        assert found["exact_match"] is True, text
        assert "message" not in found
        assert sku in _ids(found)
        assert _ids(found)[0] == sku
    for text, phrase, sku in (
        ("LumaWorks CS", "CS", "STI-C2-9"),
        ("LumaWorks HD", "HD", "STI-C2-9"),
        ("Holosun EPS", "EPS", "HOL-507C-X2"),
        ("SureFire Scout", "Scout", "SF-X300U"),
        ("Streamlight Turbo", "Turbo", "SL-TLR1"),
        ("Dawson ICE", "ICE", "DAW-FO-FRONT"),
        ("Tenicor Malus", "Malus", "TENICOR-VELO"),
        ("Tenicor Certum", "Certum", "TENICOR-VELO"),
        ("Atlas Nemesis", "Nemesis", "ATLAS-FLAT"),
        ("Cheely Mangonel", "Mangonel", "CHEELY-C2"),
        ("Holosun AEMS", "AEMS", "HOL-507C-X2"),
        ("SureFire Vampire", "Vampire", "SF-X300U"),
        ("Tenicor Sagax", "Sagax", "TENICOR-VELO"),
        ("streamlight hll", "hll", "SL-TLR1"),
        ("X300W", "X300W", "SF-X300U"),
        ("LumaWorks C4", "C4", "STI-C2-9"),
    ):
        found = await service.search(CN, text, 12)
        assert found["exact_match"] is False, text
        assert found["message"] == f"No exact match for {phrase}.", text
        assert sku in _ids(found)
        assert all(phrase not in name for name in _names(found))


class _Liar:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        return json.dumps(
            {
                "answer": "The missing code is the same product.",
                "cites": ["SL-TLR1", "TRIJ-RMR-T2", "made-up"],
            }
        )


@pytest.mark.asyncio
async def test_ask_refuses_a_model_digit_the_row_does_not_have() -> None:
    models = _Liar()
    service = Service(MemoryStore(), models)
    report = await load_catalogue(service, CATALOGUES / "customnation")
    assert report["products"]["rejected"] == []
    for question in ("Is TLR-7 listed?", "Is the RMR Type 3 listed?"):
        before = len(models.calls)
        answer = await service.ask(CN, "STI-C2-9", question)
        assert answer == {"answer": "I don't know", "cites": []}, question
        assert len(models.calls) == before
    light = await service.ask(CN, "STI-C2-9", "Is TLR-1 listed?")
    assert "SL-TLR1" in light["cites"]
    assert "Streamlight" in light["answer"]
    assert "TLR-1" in light["answer"]
    assert "missing code" not in light["answer"]
    sight = await service.ask(CN, "STI-C2-9", "Is the RMR Type 2 listed?")
    assert sight["cites"] == ["TRIJ-RMR-T2"]
    assert "Trijicon" in sight["answer"]
    assert "Type 2" in sight["answer"]
    assert "Type 3" not in sight["answer"]


@pytest.mark.asyncio
async def test_the_page_labels_closest_matches() -> None:
    script = (PAGE / "search.js").read_text(encoding="utf-8")
    assert "exact_match" in script
    assert "Closest matches" in script
    service = await _service()
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    client = TestClient(app)
    headers = {"X-Rig-Key": KEY, "Origin": ORIGIN}
    near = client.get("/v1/rig/search", params={"q": "X300V"}, headers=headers)
    assert near.status_code == 200
    body = near.json()
    assert body["exact_match"] is False
    assert body["message"] == "No exact match for X300V."
    assert body["results"][0]["id"] == "SF-X300U"
    exact = client.get("/v1/rig/search", params={"q": "LumaWorks C2"}, headers=headers)
    assert exact.json()["exact_match"] is True
    assert "Closest matches" not in exact.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "sku"),
    [
        ("Holosun rds", "HOL-507C-X2"),
        ("Safariland qd", "SAF-ALS-FULL"),
        ("Tenicor mlok", "TENICOR-VELO"),
        ("Holosun lh", "HOL-507C-X2"),
        ("Holosun rh", "HOL-507C-X2"),
        ("Holosun moa", "HOL-507C-X2"),
        ("Holosun ir", "HOL-507C-X2"),
        ("Streamlight led", "SL-TLR1"),
        ("Holosun picatinny", "HOL-507C-X2"),
        ("Safariland metal", "SAF-ALS-FULL"),
        ("Tenicor primary", "TENICOR-VELO"),
        ("Streamlight cr123", "SL-TLR1"),
        ("SureFire cr123a", "SF-X300U"),
        ("Holosun cr2032", "HOL-507C-X2"),
    ],
)
async def test_shopping_descriptors_and_cell_codes_stay_exact(query: str, sku: str) -> None:
    service = await _service()
    found = await service.search(CN, query, 12)
    assert found["exact_match"] is True, query
    assert "message" not in found
    assert _ids(found)[0] == sku


@pytest.mark.asyncio
async def test_spaced_codes_join_to_catalogue_codes() -> None:
    service = await _service()
    both = await service.search(CN, "c 2", 12)
    assert both["exact_match"] is True
    assert "STI-C2-9" in _ids(both)
    branded = await service.search(CN, "LumaWorks c 2", 12)
    assert branded["exact_match"] is True
    assert _ids(branded)[0] == "STI-C2-9"
    grip = await service.search(CN, "e 2", 12)
    assert grip["exact_match"] is True
    assert "CHEELY-E2" in _ids(grip)
    cheely = await service.search(CN, "Cheely e 2", 12)
    assert cheely["exact_match"] is True
    assert _ids(cheely)[0] == "CHEELY-E2"
    optic = await service.search(CN, "x 2", 12)
    assert optic["exact_match"] is True
    assert _ids(optic)[0] == "HOL-507C-X2"
    light = await service.search(CN, "Streamlight TLR 1", 12)
    assert light["exact_match"] is True
    assert _ids(light)[0] == "SL-TLR1"
    missing = await service.search(CN, "LumaWorks c 4", 12)
    assert missing["exact_match"] is False
    assert missing["message"] == "No exact match for c 4."
    assert "STI-C2-9" in _ids(missing)
