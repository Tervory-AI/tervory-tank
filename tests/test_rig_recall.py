"""A finished search is kept. A later search reuses the parts that match.

The sample catalogue has no model files. These cases do not read one.
A repeated part is not ranked again and does not call a model. A part that
was not stored is ranked in code. Another retailer's search is not reused.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

import rigbox.service as service_mod  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

CATALOGUES = ROOT / "agents" / "rig" / "catalogues"
CN = "33333333-3333-4333-8333-333333333333"
EXAMPLE = "11111111-1111-4111-8111-111111111111"


class Models:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        return ""


async def _service() -> tuple[Service, Models]:
    models = Models()
    service = Service(MemoryStore(), models)
    for name in ("customnation", "example", "second"):
        report = await service.load_folder(CATALOGUES / name)
        assert report["products"]["rejected"] == []
    return service, models


def _ids(body: dict) -> list[str]:
    return [str(item["id"]) for item in body.get("results") or []]


@pytest.mark.asyncio
async def test_the_same_search_is_reused_for_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    service, models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    first = await service.search(CN, "optic for staccato", 12)
    assert _ids(first) 
    assert first["exact_match"] is True
    assert first["parts"][0]["reused"] is False
    assert first["parts"][0]["rung"] == "code"
    assert first["parts"][0]["cost"] == 0
    assert calls == ["optic for staccato"]
    again = await service.search(CN, "optic for staccato", 12)
    assert calls == ["optic for staccato"]
    assert _ids(again) == _ids(first)
    assert again["parts"][0]["reused"] is True
    assert again["parts"][0]["cost"] == 0
    assert again["parts"][0]["rung"] == "code"
    assert models.calls == []
    assert list(again["results"][0]) == ["id", "name", "brand", "category", "image", "price", "attributes"]


@pytest.mark.asyncio
async def test_a_new_part_is_ranked_and_the_known_part_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    service, models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    first = await service.search(CN, "optic for staccato", 12)
    calls.clear()
    second = await service.search(CN, "optic and holster for staccato", 12)
    assert calls == ["holster for staccato"]
    assert _ids(first) == [item for item in _ids(second) if item in set(_ids(first))]
    by_part = {row["part"]: row for row in second["parts"]}
    assert by_part["optic"]["reused"] is True
    assert by_part["optic"]["cost"] == 0
    assert by_part["holster"]["reused"] is False
    assert by_part["holster"]["rung"] == "code"
    calls.clear()
    third = await service.search(CN, "optic and holster for staccato", 12)
    assert calls == []
    assert _ids(third) == _ids(second)
    assert all(row["reused"] is True and row["cost"] == 0 for row in third["parts"])
    assert models.calls == []


@pytest.mark.asyncio
async def test_another_retailer_does_not_reuse_the_search(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append((str(payload["tenant_id"]), str(payload["q"])))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    await service.search(EXAMPLE, "scope", 12)
    calls.clear()
    other = await service.search(CN, "scope", 12)
    assert calls == [(CN, "scope")]
    assert "EXAMPLE-SCOPE-01" not in _ids(other)


@pytest.mark.asyncio
async def test_removing_the_search_ranks_it_again(monkeypatch: pytest.MonkeyPatch) -> None:
    service, models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    await service.search(CN, "optic for staccato", 12)
    await service.search(CN, "optic for staccato", 12)
    assert calls == ["optic for staccato"]
    await service.store.drop_searches(CN)
    await service.search(CN, "optic for staccato", 12)
    assert calls == ["optic for staccato", "optic for staccato"]
    assert models.calls == []


@pytest.mark.asyncio
async def test_a_changed_catalogue_is_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    await service.search(CN, "Staccato P", 12)
    await service.store.update_price(CN, "STI-P-9", {"price": 10})
    again = await service.search(CN, "Staccato P", 12)
    assert calls == ["Staccato P", "Staccato P"]
    assert again["parts"][0]["reused"] is False


@pytest.mark.asyncio
async def test_a_miss_stays_a_miss_without_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    service, models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    assert await service.search(CN, "sig", 12) == {"results": []}
    assert await service.search(CN, "sig", 12) == {"results": []}
    assert calls == ["sig"]
    assert models.calls == []


@pytest.mark.asyncio
async def test_a_closest_match_repeats_the_same_words(monkeypatch: pytest.MonkeyPatch) -> None:
    service, models = await _service()
    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    first = await service.search(CN, "X300V", 12)
    again = await service.search(CN, "X300V", 12)
    assert calls == ["X300V"]
    assert again["exact_match"] is False
    assert again["message"] == first["message"] == "No exact match for X300V."
    assert _ids(again) == _ids(first)
    assert "SF-X300U" in _ids(again)
    assert models.calls == []
