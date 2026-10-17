"""Rig agent page. No database and no network."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "rig"


def _source() -> str:
    parts = [path.read_text(encoding="utf-8") for path in sorted(PAGE.rglob("*")) if path.is_file()]
    return "\n".join(parts)


def test_panel_is_fixed_and_split_with_the_standard_nav():
    css = (PAGE / "rig.css").read_text(encoding="utf-8")
    assert ".panel" in css
    assert "position: fixed" in css
    assert "overflow: hidden" in css
    assert ".body" in css
    assert "overflow: auto" in css
    source = _source()
    assert "panel-top" in source
    assert "panel-own" in source
    assert "panel-bottom" in source
    assert "tervory-logo-reversed.png" in source
    assert "Rig logo, coming later" not in source
    assert "headerLinks" in (PAGE / "page.tsx").read_text(encoding="utf-8")
    assert "RIG" in source
    assert "Plugins" in source
    assert "Last refreshed" in source
    assert "Workspace" in source
    nav = (PAGE / "copy.ts").read_text(encoding="utf-8")
    assert nav.index('label: "Search"') < nav.index('label: "Overview"')
    assert "TABS.map" in (PAGE / "lab.tsx").read_text(encoding="utf-8")
    assert "Integrations" not in source


def test_plugins_is_a_tab_and_sources_means_answer_references():
    source = _source()
    assert 'label: "Plugins"' not in source or "Plugins" in source
    assert ">Plugins<" in source
    assert 'href="/sources"' not in source
    assert "API keys" in source
    assert "MCP connections" in source
    assert "Source links" in source
    lab = (PAGE / "lab.tsx").read_text(encoding="utf-8")
    plugins = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    copy = (PAGE / "copy.ts").read_text(encoding="utf-8")
    for text in (lab, plugins, copy):
        assert "Sources" not in text.replace("Source links", "")
    ask = (PAGE / "search-view.tsx").read_text(encoding="utf-8")
    assert ">Sources<" in ask
    assert "Ask Rig" in ask
    assert "Send" in ask


def test_secrets_are_dots_and_example_products_stay_out():
    source = _source()
    assert "Example" in source
    assert "•••• saved 17 Oct" in source
    assert "rk_pub_" not in source
    assert "api_key=" not in source.lower()
    assert "sk-" not in source
    assert "Example Rifle" not in source
    assert "ExampleBrand" not in source
    assert "/v1/rig/admin" not in source
    assert "/v1/rig/search" in source
    assert "/v1/rig/ask" in source
    assert "I don't know" in source


def test_one_red_button_style():
    css = (PAGE / "rig.css").read_text(encoding="utf-8").lower()
    assert css.count("#e80008") == 1
    assert ".primary" in css
    assert "search" in (PAGE / "search-view.tsx").read_text(encoding="utf-8").lower()
