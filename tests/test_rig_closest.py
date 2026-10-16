"""A near-miss model code is a closest match, not an exact hit.

These cases use different wording from the review sets. A code that is not
on a row stays out of the exact results. The real row, when one is close,
comes back with exact_match false and the words "Closest matches".
"""

from __future__ import annotations

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

CATALOGUES = ROOT / "agents" / "rig" / "catalogues"
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
        report = await service.load_folder(CATALOGUES / name)
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

    centre = await service.search(CN, "staccato C3", 12)
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
    exact = await service.search(CN, "Staccato C2", 12)
    assert exact["exact_match"] is True
    assert "message" not in exact
    assert _ids(exact)[0] == "STI-C2-9"

    scope = await service.search(EXAMPLE, "scope", 12)
    assert scope["exact_match"] is True
    assert _ids(scope) == ["EXAMPLE-SCOPE-01"]

    paired = await service.search(CN, "optic pairs with staccato", 3)
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


@pytest.mark.asyncio
async def test_ordinary_shopping_words_never_flag_and_an_unknown_name_after_a_brand_does() -> None:
    listed = [
        line.split("#", 1)[0].strip().lower()
        for line in (ROOT / "agents" / "rig" / "english-20k.txt").read_text(encoding="utf-8").splitlines()
    ]
    listed = [word for word in listed if word]
    assert len(listed) == 20000
    shopping = (
        "cheap",
        "spare",
        "top",
        "kit",
        "daily",
        "quick",
        "bag",
        "buy",
        "gun",
        "oh",
        "set",
        "up",
        "rig",
        "extra",
        "basic",
        "black",
        "small",
        "best",
        "new",
        "used",
        "local",
        "premium",
        "budget",
        "simple",
        "clean",
        "soft",
        "original",
        "replacement",
        "compact",
        "carry",
        "home",
        "travel",
        "nylon",
        "leather",
        "light",
        "heavy",
        "open",
        "free",
        "good",
        "great",
        "little",
        "strong",
        "classic",
        "modern",
        "mini",
        "easy",
        "fast",
        "quiet",
        "short",
        "long",
        "round",
        "flat",
        "holder",
        "cover",
        "case",
        "pack",
        "box",
        "pair",
    )
    assert all(word in listed for word in shopping)
    assert "malus" not in listed
    assert "certum" not in listed
    service = await _service()
    for word in shopping:
        for text in (f"{word} tenicor", f"tenicor {word}", f"{word} staccato", f"holosun {word}"):
            found = await service.search(CN, text, 12)
            assert found["results"], text
            assert found["exact_match"] is True, text
            assert "message" not in found
    # A word that is not English still does not flag when it sits before the brand.
    for text in ("zqxv tenicor", "blorpt holosun", "iwb tenicor", "qqqq staccato"):
        found = await service.search(CN, text, 12)
        assert found["results"], text
        assert found["exact_match"] is True, text
        assert "message" not in found
    # The same unknown token directly after the brand is the missing model.
    # An ordinary word between them is not, and it does not pull the later token in.
    between = await service.search(CN, "tenicor cheap zqxv", 12)
    assert between["exact_match"] is True
    assert "message" not in between
    typo = await service.search(CN, "streamlight hll", 12)
    assert typo["exact_match"] is True
    assert "message" not in typo
    assert _ids(typo)[0] == "SL-TLR1"
    for text, phrase, sku in (
        ("Tenicor Malus", "Malus", "TENICOR-VELO"),
        ("Tenicor Certum", "Certum", "TENICOR-VELO"),
        ("X300W", "X300W", "SF-X300U"),
        ("Staccato C4", "C4", "STI-C2-9"),
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
    report = await service.load_folder(CATALOGUES / "customnation")
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
    exact = client.get("/v1/rig/search", params={"q": "Staccato C2"}, headers=headers)
    assert exact.json()["exact_match"] is True
    assert "Closest matches" not in exact.text
