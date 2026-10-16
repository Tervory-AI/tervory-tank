"""Shopper answers are written from catalogue fields. The model only names rows.

These cases are original: a short token inside a longer word, a claim that
mixes two real rows, and a category that belongs to a different row. Search
uses the same relation phrases a shopper actually types.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

CATALOGUES = ROOT / "agents" / "rig" / "catalogues"
CN = "33333333-3333-4333-8333-333333333333"
EXAMPLE = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
LIE = "Invented claim: the compact centre is a red dot made by another brand."
OPTICS = {"HOL-507C-X2", "TRIJ-RMR-T2"}
HOLSTERS = {"TENICOR-VELO", "SAF-ALS-FULL"}
TRIGGERS = {"ATLAS-FLAT", "REDD-TRIGGER"}


class Liar:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        return json.dumps(
            {
                "answer": LIE,
                "cites": ["STI-C2-9", "HOL-507C-X2", "DAW-FO-FRONT", "EXAMPLE-SCOPE-01", "made-up"],
            }
        )


async def _service() -> tuple[Service, Liar]:
    models = Liar()
    service = Service(MemoryStore(), models)
    for name in ("customnation", "example", "second"):
        report = await service.load_folder(CATALOGUES / name)
        assert report["products"]["rejected"] == []
        assert report["fits"]["rejected"] == []
    return service, models


def _ids(body: dict[str, Any]) -> list[str]:
    return [str(item["id"]) for item in body.get("results") or []]


@pytest.mark.asyncio
async def test_short_tokens_do_not_match_inside_longer_words() -> None:
    service, models = await _service()
    for question in ("Is sig listed?", "Is cat listed?"):
        before = len(models.calls)
        answer = await service.ask(CN, "STI-C2-9", question)
        assert answer == {"answer": "I don't know", "cites": []}
        assert len(models.calls) == before
    sig = _ids(await service.search(CN, "sig", 12))
    cat = _ids(await service.search(CN, "cat", 12))
    assert "DAW-FO-FRONT" not in sig
    assert "TEN8-REAR" not in sig
    assert not {"STI-P-9", "STI-C2-9", "STI-XC-9"} & set(cat)


@pytest.mark.asyncio
async def test_false_relations_are_not_stitched_across_rows() -> None:
    service, models = await _service()
    questions = (
        "Is the compact Staccato also a red dot?",
        "Is Holosun a Staccato?",
        "Is Cheely a red dot?",
        "Is Atlas a holster?",
        "Is the grip an optic?",
    )
    for question in questions:
        answer = await service.ask(CN, "STI-C2-9", question)
        assert answer == {"answer": "I don't know", "cites": []}, question
        assert LIE not in answer["answer"]
    assert models.calls


@pytest.mark.asyncio
async def test_a_real_row_is_quoted_from_its_own_fields() -> None:
    service, _models = await _service()
    scope = await service.ask(EXAMPLE, "EXAMPLE-RIFLE-01", "Which scope is listed?")
    assert scope["cites"] == ["EXAMPLE-SCOPE-01"]
    assert "Example Scope" in scope["answer"]
    assert "8999" in scope["answer"]
    assert scope["answer"] != LIE
    assert "made-up" not in scope["cites"]
    compact = await service.ask(CN, "STI-C2-9", "Is the C2 compact?")
    assert compact["cites"] == ["STI-C2-9"]
    assert "Staccato C2" in compact["answer"]
    assert "compact" in compact["answer"]
    assert "Holosun" not in compact["answer"]
    assert "red dot" not in compact["answer"].lower()


@pytest.mark.asyncio
async def test_an_approved_fit_is_a_sentence_the_code_writes() -> None:
    service, _models = await _service()
    answer = await service.ask(CN, "STI-C2-9", "Which optic fits the Staccato C2?")
    text = answer["answer"]
    assert "Holosun 507C X2 fits Staccato C2." in text
    assert "Trijicon RMR Type 2 fits Staccato C2." in text
    assert LIE not in text
    assert "compact red dot" not in text.lower()
    assert set(answer["cites"]) >= {"HOL-507C-X2", "TRIJ-RMR-T2", "STI-C2-9"}


@pytest.mark.asyncio
async def test_relation_phrases_rank_the_part_being_asked_for() -> None:
    service, _models = await _service()
    optic = _ids(await service.search(CN, "optic pairs with staccato", 3))
    holster = _ids(await service.search(CN, "holster compatible with c2", 3))
    trigger = _ids(await service.search(CN, "trigger fits staccato", 3))
    light = _ids(await service.search(CN, "x300 for staccato", 3))
    scope = _ids(await service.search(EXAMPLE, "scope goes on the rifle", 3))
    shade = _ids(await service.search(SECOND, "shade to go with the lamp", 3))
    assert optic[0] in OPTICS
    assert set(holster) & HOLSTERS
    assert trigger[0] in TRIGGERS
    assert "SF-X300U" in light
    assert scope[0] == "EXAMPLE-SCOPE-01"
    assert shade[0] == "SECOND-SHADE-01"
    assert "STI-P-9" not in optic
