"""Market Lab page source. No database and no network."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "market-lab"


def _source() -> str:
    parts = [path.read_text(encoding="utf-8") for path in sorted(PAGE.rglob("*")) if path.is_file()]
    return "\n".join(parts)


def test_panel_stays_fixed_and_split_in_three():
    css = (PAGE / "market-lab.css").read_text(encoding="utf-8")
    assert ".panel" in css
    assert "position: fixed" in css
    assert "overflow: hidden" in css
    assert ".body" in css
    assert "overflow: auto" in css
    source = _source()
    assert "panel-top" in source
    assert "panel-own" in source
    assert "panel-bottom" in source
    assert "Sources" in source.split("panel-bottom")[0]
    assert "Last refreshed" in source
    assert "Workspace" in source


def test_sources_is_a_tab_on_the_page():
    source = _source()
    assert "Sources" in source
    assert 'href="/sources"' not in source
    assert 'href="/market-lab/sources"' not in source
    assert "API keys" in source
    assert "MCP connections" in source
    assert "Source links" in source


def test_example_values_stay_and_secrets_are_dots():
    source = _source()
    assert "Example" in source
    assert "•••• saved 17 Oct" in source
    assert "Off. Needs a key." in source
    assert "Not called" in source
    assert "FRED_API_KEY" in source
    assert "api_key=" not in source.lower()
    assert "sk-" not in source
    assert "matters" not in source.lower()


def test_one_red_button_style():
    css = (PAGE / "market-lab.css").read_text(encoding="utf-8").lower()
    assert css.count("#e80008") == 1
    assert ".primary" in css
