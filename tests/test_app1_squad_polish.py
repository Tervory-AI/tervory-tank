"""Squad pages must not ship placeholder words.

The build fails when any of the nine squad pages contains
"to be named", "__", "TODO", "lorem", or "stub".
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("base", "tiger", "market-lab", "rig", "tisan", "radix", "zenas", "skala", "tank")
BANNED = ("to be named", "__", "todo", "lorem", "stub")


def _page_files() -> list[Path]:
    found: list[Path] = []
    for name in PAGES:
        folder = ROOT / "workspace" / "app" / name
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix not in {".ts", ".tsx", ".css"}:
                continue
            if path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
                continue
            found.append(path)
    return found


def test_pages_reject_placeholder_words() -> None:
    hits: list[str] = []
    for path in _page_files():
        text = path.read_text(encoding="utf-8").lower()
        for word in BANNED:
            if word in text:
                hits.append(f"{path.relative_to(ROOT)} contains {word}")
    assert hits == [], "\n".join(hits)
