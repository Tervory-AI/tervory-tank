"""Product shell type: Jost Light headings, Inter body and nav, JetBrains Mono for cost and meta."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "workspace" / "app"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_shell_loads_the_admin_faces():
    layout = _text(APP / "layout.tsx")
    admin = _text(APP / "admin" / "layout.tsx")
    for line in (
        'Jost({ subsets: ["latin"], weight: "300", variable: "--font-jost", display: "swap" })',
        'Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" })',
        'JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" })',
    ):
        assert line in layout
        assert line in admin
    assert "jost.variable" in layout and "inter.variable" in layout and "mono.variable" in layout


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
