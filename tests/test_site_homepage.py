"""Public site copy: the retired phrase stays out of site/, and the homepage uses the brief."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SKIP = {"node_modules", ".next", "out"}
TEXT = {".ts", ".tsx", ".css", ".mjs", ".js", ".json", ".svg", ".html", ".txt", ".md"}


def test_retired_phrase_is_absent_under_site() -> None:
    banned = "one window"
    hits: list[str] = []
    for path in SITE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT:
            continue
        if any(part in SKIP for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if banned in text.lower():
            hits.append(str(path.relative_to(SITE)))
    assert hits == []


def test_title_and_description_have_one_source() -> None:
    source = (SITE / "lib" / "site.ts").read_text(encoding="utf-8")
    layout = (SITE / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert source.count('export const homeTitle = "Tervory AI: specialist AI for the work that runs a business";') == 1
    assert (
        "A squad of specialist AI agents for data, pricing, markets, legal, security and the web. "
        "Every answer shows its sources, the model that ran it, and what it cost."
    ) in source
    assert "homeTitle" in layout and "homeDescription" in layout
    assert "Tervory AI: specialist AI" not in layout


def test_homepage_uses_approved_figma_copy_and_local_assets() -> None:
    import re

    page = (SITE / "app" / "page.tsx").read_text(encoding="utf-8")
    copy = (SITE / "app" / "home-copy.ts").read_text(encoding="utf-8")
    form = (SITE / "app" / "release-form.tsx").read_text(encoding="utf-8")
    interactions = (SITE / "app" / "home-interactions.tsx").read_text(encoding="utf-8")
    for line in (
        "Specialist AI that gets cheaper the more it works.",
        "Facts over hype. Work over fluff.",
        "What each product does",
        "Your shadow realm for digital threats.",
        "Attorney review is available as an option when you need it.",
    ):
        assert line in copy, line
    assert "Get early access" in form and "Join the list" in form
    assert 'fetch("/api/release-notice"' in form
    assert "fetch(" not in interactions  # Illustrations must not call paid/live services.
    assert "figma.com/api/mcp/asset" not in page + interactions
    assert "QUOTE-EMAILS" not in page + interactions
    assets = list((SITE / "public" / "home").iterdir())
    assert len(assets) == 27
    assert all(asset.stat().st_size > 0 for asset in assets)
    for src in re.findall(r'src="(/home/[^"]+)"', page + interactions):
        assert (SITE / "public" / src.lstrip("/")).stat().st_size > 0
