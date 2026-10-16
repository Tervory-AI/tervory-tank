"""A near-miss model code is a closest match, not an exact hit.

These cases use different wording from the review sets. A code that is not
on a row stays out of the exact results. The real row, when one is close,
comes back with exact_match false and the words "Closest matches".
"""

from __future__ import annotations

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
