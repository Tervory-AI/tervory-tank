"""Tisan page source. No database and no network."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "tisan"
NAV = ROOT / "workspace" / "app" / "product-nav.ts"


def _source() -> str:
    parts = [path.read_text(encoding="utf-8") for path in sorted(PAGE.rglob("*")) if path.is_file()]
    return "\n".join(parts)


def test_panel_stays_fixed_and_only_the_body_scrolls():
    css = (PAGE / "tisan.css").read_text(encoding="utf-8")
    assert ".panel" in css
    assert "position: fixed" in css
    assert "overflow: hidden" in css
    assert ".body" in css
    assert "overflow: auto" in css
    source = _source()
    assert "panel-top" in source
    assert "panel-own" in source
    assert "panel-bottom" in source
    assert "Last refreshed" in source
    assert "Workspace" in source
    assert "headerLinks" in source


def test_plugins_is_the_tab_and_sources_are_only_under_answers():
    source = _source()
    assert "Plugins" in source
    assert "Integrations" not in source
    assert 'label: "Plugins"' in source or ">Plugins<" in source
    assert "<h3>Sources</h3>" in source
    assert source.count("<h3>Sources</h3>") == 1
    assert 'href="/sources"' not in source
    assert 'href="/tisan/sources"' not in source
    assert "API keys" in source
    assert "Source links" in source
    assert "MCP connections" in source
    assert "FRED" not in source
    assert "CENSUS_API_KEY" not in source
    assert "Set by your admin in Plugins" in source


def test_example_values_stay_and_secrets_are_dots():
    source = _source()
    assert "Example" in source
    assert "•••• saved 17 Oct" in source
    assert "Tisan logo, coming later" in source
    assert "/brand/tervory-logo-reversed.png" in source
    assert "tervory-logo-on-white" not in source
    assert "fetch(" not in source
    assert "api.figma.com" not in source
    assert "sk-" not in source
    assert "matters" not in source.lower()
    assert 'label: "Skala"' in NAV.read_text(encoding="utf-8")
    assert '"/tisan"' in NAV.read_text(encoding="utf-8")


def test_one_red_button_style_and_the_swatch():
    css = (PAGE / "tisan.css").read_text(encoding="utf-8").lower()
    assert css.count("#e80008") == 2
    assert ".primary" in css
    assert ".swatch.red" in css


def test_search_and_the_red_button_rule():
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "tisan_page.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
