"""Product shell type: Jost Light headings, Inter body and nav, JetBrains Mono for cost and meta."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "workspace" / "app"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_shell_loads_the_admin_faces():
    fonts = _text(APP / "fonts" / "index.ts")
    layout = _text(APP / "layout.tsx")
    admin = _text(APP / "admin" / "layout.tsx")
    assert 'from "next/font/local"' in fonts
    assert 'from "next/font/google"' not in layout
    assert 'from "next/font/google"' not in admin
    for line in (
        'src: "./Jost-300-latin.woff2"',
        'weight: "300"',
        'variable: "--font-jost"',
        'display: "swap"',
        'src: "./Inter-latin.woff2"',
        'weight: "100 900"',
        'variable: "--font-inter"',
        'path: "./JetBrainsMono-latin.woff2", weight: "400"',
        'path: "./JetBrainsMono-latin.woff2", weight: "500"',
        'variable: "--font-mono"',
    ):
        assert line in fonts
    for page in (layout, admin):
        assert 'from "./fonts"' in page or 'from "../fonts"' in page
        assert "jost.variable" in page and "inter.variable" in page and "mono.variable" in page


def test_product_pages_use_the_pairing_and_rows_stay_in_inter():
    css = _text(APP / "globals.css")
    shell = _text(APP / "shell.tsx")
    assert "system-ui" not in css
    assert "app-shell product" in shell
    assert "font-size: 17px" in css
    assert "font-weight: 400" in css
    assert ".product h1, .product h2, .product h3" in css
    assert "var(--font-jost)" in css
    assert "font-weight: 300" in css
    assert ".product .top nav" in css
    assert "font-size: 15px" in css
    assert "font-weight: 500" in css
    assert ".product .meta, .product .tile b" in css
    assert 'var(--font-mono), "JetBrains Mono"' in css
    for selector in (".row {", ".row-main {", ".rows {", "table {", "th, td {"):
        block = css.split(selector, 1)[1].split("}", 1)[0]
        assert "font-family" not in block, selector
    assert 'href: "/skala"' in _text(APP / "product-nav.ts")
