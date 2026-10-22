"""The Tervory logo is never shown as a white stamp or squashed (founder, 21 Oct 2026).

tervory-logo-on-white.png has a solid white background. On any page whose background is
not pure white it shows as a white box. App pages use the transparent tervory-logo.png
(light pages) or tervory-logo-reversed.png (dark pages). The on-white file is kept only
for documents that are themselves white.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "workspace" / "app"
SOURCES = [p for p in APP.rglob("*") if p.suffix in {".tsx", ".ts", ".css", ".jsx", ".js"}]


def test_no_app_page_uses_the_white_background_logo():
    offenders = [str(p.relative_to(ROOT)) for p in SOURCES if "tervory-logo-on-white" in p.read_text(errors="ignore")]
    assert offenders == [], f"Use /brand/tervory-logo.png (transparent) instead: {offenders}"


def test_transparent_logos_really_are_transparent():
    Image = pytest.importorskip("PIL.Image")

    for name in ("tervory-logo.png", "tervory-logo-reversed.png"):
        alpha = Image.open(ROOT / "workspace/public/brand" / name).getchannel("A")
        assert alpha.getpixel((2, 2)) == 0, f"{name} must have a transparent background"
