"""GHOST-2 D4: Tank's founder-only corridor for the Shields tile. The room is faked; nothing leaves the box."""
import importlib.util
import re
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ghost_routes_tests", ROOT / "tests/test_ghost_routes.py")
_routes_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_routes_tests)
tank = _routes_tests.tank
gateway = _routes_tests.gateway  # noqa: F811 - the shared Tank fixture

FOUNDER = {"X-Tank-Key": "workspace-test", "X-Tervory-Admin": "founder-test"}
PANEL = ROOT / "workspace/app/admin/ghost"


@pytest.mark.asyncio
async def test_shield_routes_are_founder_only_and_reach_only_ghost(gateway, monkeypatch):
    gateway.fetchrow.return_value = {"cost": Decimal("0.012500"), "receipts": 7}
    seen = []
    shield = uuid.uuid4()

    def upstream(request):
        seen.append(request)
        if request.url.path == "/ghost/summary":
            return httpx.Response(200, json={"mode": "dry_run", "open_total": 2, "sites_broken_by_a_shield": 0})
        return httpx.Response(200, json={"mode": "dry_run", "shields": [], "id": str(shield), "state": "dry_run"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as http:
        monkeypatch.setattr(tank, "_http", http)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
            for method, path in (("GET", "/v1/ghost/shields/list"), ("GET", "/v1/ghost/shields/tile"),
                                 ("POST", f"/v1/ghost/shields/{shield}/raise"), ("POST", f"/v1/ghost/shields/{shield}/undo")):
                for headers in ({"X-Tank-Key": "workspace-test"}, {"X-Tank-Key": "ghost-test"}, {}):
                    assert (await client.request(method, path, headers=headers)).status_code in {403, 404}
            assert not seen
            tile = (await client.get("/v1/ghost/shields/tile", headers=FOUNDER)).json()
            assert tile["cost_this_month_usd"] == 0.0125 and tile["receipts_this_month"] == 7 and tile["open_total"] == 2
            assert (await client.get("/v1/ghost/shields/list", headers=FOUNDER)).status_code == 200
            assert (await client.post(f"/v1/ghost/shields/{shield}/raise", headers=FOUNDER)).status_code == 200
            assert (await client.post(f"/v1/ghost/shields/{shield}/undo", headers=FOUNDER)).status_code == 200
            assert (await client.post(f"/v1/ghost/shields/{shield}/delete", headers=FOUNDER)).status_code in {404, 422}
            assert (await client.post("/v1/ghost/shields/not-a-uuid/raise", headers=FOUNDER)).status_code in {404, 422}
    assert [str(r.url) for r in seen] == ["http://agent-ghost:8000/ghost/summary", "http://agent-ghost:8000/ghost/shields",
                                          f"http://agent-ghost:8000/ghost/shields/{shield}/raise",
                                          f"http://agent-ghost:8000/ghost/shields/{shield}/undo"]
    assert all(r.headers["X-Tank-Key"] == "ghost-test" for r in seen)
    sql, tenant = gateway.fetchrow.await_args.args
    assert "tenant_id=$1" in sql and tenant == tank.PLATFORM_TENANT


def test_room_cannot_reach_the_shield_taps():
    from ghost_routes import ROOM_METHODS
    assert not any("shields" in path for _method, path in ROOM_METHODS)


def test_tile_is_plain_english_on_the_light_logo_with_no_tool_or_model_names():
    text = "".join(p.read_text() for p in PANEL.glob("*.ts*"))
    assert "/brand/tervory-logo.png" in text
    assert "tervory-logo-reversed" not in text and "on-white" not in text
    tile = (PANEL / "tile.tsx").read_text()
    names = ("Cloudflare", "GPT", "Claude", "Grok", "Gemini", "Hermes", "LiteLLM", "OpenAI", "Anthropic", "Coolify")
    for path in PANEL.glob("*.ts*"):
        for word in names:
            assert word not in path.read_text(), f"{word} in {path.name}"
    for word in ("WAF", "API"):
        assert word not in tile, word
    for words in ("Open issues", "Time to know", "Time to shield", "Sites broken by a shield", "Cost this month", "Undo"):
        assert words in tile, words


def test_shield_notes_shown_on_the_tile_name_no_tools():
    from agents.ghost import shields
    shown = re.findall(r'(?:CloudflareError\(|"note"\] = |shield\["note"\] = )f?"([^"]*)"', (ROOT / "agents/ghost/shields.py").read_text())
    shown += list(shields.PLAIN.values())
    assert len(shown) > 10
    for text in shown:
        assert "Cloudflare" not in text and "Grok" not in text, text
