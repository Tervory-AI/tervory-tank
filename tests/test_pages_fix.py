"""PAGES-FIX: the six routes stay free of the old placeholders and dead controls."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "workspace" / "app"

ROUTES = {
    "rig": APP / "rig" / "page.tsx",
    "review": APP / "review" / "page.tsx",
    "feeds": APP / "zenas" / "feeds" / "page.tsx",
    "market-lab": APP / "market-lab" / "page.tsx",
    "radix": APP / "radix" / "page.tsx",
    "tasks": APP / "tasks" / "page.tsx",
    "data": APP / "data" / "page.tsx",
}

BANNED = ("is off", "not on this page yet", "needs a key", "to be named", "todo", "lorem", "stub")
VAULT_SENTENCE = "this vault is off. turn it on in tank."


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(folder: Path) -> str:
    parts: list[str] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".css"}:
            continue
        if path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
            continue
        parts.append(_text(path))
    return "\n".join(parts)


def test_each_route_file_is_present_for_a_founder():
    for name, path in ROUTES.items():
        assert path.is_file(), name
    feeds = _text(ROUTES["feeds"])
    assert "isFounder(userId)" in feeds
    assert "notFound()" in feeds
    review = _text(APP / "review" / "access.ts")
    assert 'role !== "reviewer"' in review
    assert "isListedFounder" in review
    assert "reviewGate" in review
    founder = _text(APP / "review" / "founder.ts")
    assert "signOffRefusal" in founder
    sign = _text(APP / "api" / "zenas" / "documents" / "[id]" / "reviews" / "route.ts")
    assert "signOffRefusal" in sign
    assert "Only an admitted reviewer can sign off." in founder
    assert "View only" not in founder
    assert "{ status: 403 }" in sign
    desk = _text(APP / "review" / "desk.tsx")
    assert "View only" not in desk
    assert "Approve" in desk
    assert "viewOnly" not in desk
    assert "Request refused." in _text(APP / "rig" / "api" / "rig" / "route.ts")
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "pages_fix_access.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_rig_does_not_read_room_files():
    server = _text(APP / "rig" / "rig-server.ts")
    page = _text(APP / "rig" / "page.tsx")
    tank = _text(ROOT / "workspace" / "lib" / "tank.ts")
    assert "readFileSync" not in server
    assert "demoKey" not in server
    assert "publish.json" not in server
    assert "products.csv" not in server
    assert "rigCatalogueCounts" in page
    assert "rigCatalogueCounts" in tank
    assert "/v1/rig/catalogues" in tank
    assert "Rig did not answer" in _text(APP / "rig" / "lab.tsx")
    joined = _tree(APP / "rig")
    assert "readFileSync" not in joined
    assert "/v1/rig/search" in joined
    assert "/v1/rig/ask" in joined


def test_pages_drop_the_dead_copy():
    folders = [
        APP / "rig",
        APP / "review",
        APP / "zenas" / "feeds",
        APP / "market-lab",
        APP / "radix",
        APP / "tasks",
        APP / "data",
    ]
    hits: list[str] = []
    for folder in folders:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix not in {".ts", ".tsx", ".css"}:
                continue
            if ".test." in path.name:
                continue
            text = _text(path).lower().replace(VAULT_SENTENCE, "")
            for word in BANNED:
                if word in text:
                    hits.append(f"{path.relative_to(ROOT)} contains {word}")
    assert hits == [], "\n".join(hits)
    view = _text(APP / "market-lab" / "view.tsx")
    assert "Off (needs a key)" not in view
    radix = _text(APP / "radix" / "view.tsx")
    assert "Outbound scans are off" not in radix
    assert "Scan results are not on this page yet" not in radix


def test_primary_buttons_are_not_greyed_out_before_input():
    tasks = _text(APP / "tasks" / "page.tsx")
    data = _text(APP / "data" / "page.tsx")
    assert "Add task" in tasks
    assert "Run Base" in data
    assert "disabled={busy || !title.trim()" not in tasks
    assert "disabled={busy || !batch.trim()" not in data
    assert 'disabled={busy}' in tasks
    assert 'disabled={busy}' in data
    market = _text(APP / "market-lab" / "view.tsx")
    assert "disabled={sending || !draft.trim()}" not in market
    radix = _text(APP / "radix" / "conversation.tsx")
    assert "disabled={busy || !draft.trim()}" not in radix


def test_wide_tables_scroll_inside_their_box():
    feeds = _text(APP / "zenas" / "feeds" / "feeds.css")
    board = _text(APP / "zenas" / "feeds" / "board.tsx")
    assert ".zf-scroll" in feeds
    assert "overflow-x: auto" in feeds
    assert "overflow-x: hidden" in feeds
    assert 'className="zf-scroll"' in board
    data_css = _text(APP / "data" / "data.css")
    data = _text(APP / "data" / "page.tsx")
    assert ".data-scroll" in data_css
    assert "overflow-x: auto" in data_css
    assert 'className="data-scroll"' in data
    assert "overflow-x: hidden" in data_css
