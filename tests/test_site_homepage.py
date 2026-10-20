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


def test_homepage_uses_the_brief_copy_and_logo_files() -> None:
    page = (SITE / "app" / "page.tsx").read_text(encoding="utf-8")
    footer = (SITE / "app" / "footer.tsx").read_text(encoding="utf-8")
    form = (SITE / "app" / "release-form.tsx").read_text(encoding="utf-8")
    for line in (
        "Tervory AI · In build",
        "Specialist AI for the work that runs a business.",
        "How it works",
        "Describe the job the way you would brief a colleague.",
        "It gets cheaper the more it works",
        "The squad",
        "Nine specialists. Each one built for a single job.",
        "Measured, not promised",
        "Be first in",
        "We are opening to a small group of businesses first.",
    ):
        assert line in page, line
    assert "Every answer shows its sources, the model that ran it, and what it cost." in footer
    assert "Get early access" in form and "Join the list" in form
    for name, mark in (
        ("Base", "/brand/base-on-light.png"),
        ("Tiger", "/brand/tiger-on-light.png"),
        ("Market Lab", "/brand/market-lab-on-light.png"),
        ("Rig", "/brand/rig-on-light.png"),
        ("Tisan", "/brand/tisan-on-light.png"),
        ("Radix", "/brand/radix-on-light.png"),
        ("Zenas", "/brand/zenas-on-light.png"),
        ("Skala", "/brand/skala-on-light.png"),
        ("Tank", "/brand/tank-on-light.png"),
    ):
        assert name in page and mark in page
        assert (SITE / "public" / mark.lstrip("/")).is_file()
