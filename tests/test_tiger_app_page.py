"""Tiger app page source. No database and no network."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "tiger"
NAV = ROOT / "workspace" / "app" / "product-nav.ts"

INDUSTRY = (
    "firearm",
    "gun",
    "ammo",
    "ammunition",
    "hunting",
    "dealer",
    "ffl",
    "nics",
    "atf",
    "rifle",
)


def _files() -> list[Path]:
    return [path for path in sorted(PAGE.rglob("*")) if path.is_file()]


def _source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in _files())


def test_panel_stays_fixed_and_split_in_three():
    css = (PAGE / "tiger.css").read_text(encoding="utf-8")
    assert "position: fixed" in css
    assert "overflow: hidden" in css
    assert ".body" in css
    assert "overflow: auto" in css
    source = _source()
    assert "panel-top" in source
    assert "panel-own" in source
    assert "panel-bottom" in source
    assert "Your account" in source
    assert "Account name" not in source
    assert "Dashboard" in source
    assert "Projects" in source
    assert "Chats" in source
    assert "Settings" in source
    assert "Support" in source
    assert 'href="/"' in source
    assert "/brand/tervory-logo-reversed.png" in source


def test_tiger_tabs_and_plugins_popup():
    source = _source()
    assert "Overview" in source
    assert "Ask Tiger" in source
    assert "Alerts" in source
    assert "Watch list" in source
    assert "Can't read" in source
    assert "Plugins" in source
    assert "API keys" in source
    assert "Source links" in source
    assert "MCP connections" in source
    assert "Integrations" not in source
    # The word Sources is the label on an answer, not a nav tab.
    assert 'className="sources-label">Sources:' in source
    assert '"Sources"' not in source
    assert 'label: "Sources"' not in source
    assert 'href="/plugins"' not in source
    assert 'href="/tiger/plugins"' not in source


def test_example_values_stay_and_secrets_are_dots():
    source = _source()
    assert "No products watched yet." in source
    assert "Trail running shoe" not in source
    assert "••••••••" in source
    assert 'type="password"' in source
    assert "api_key=" not in source.lower()
    assert "sk-" not in source
    assert "Add a product" in source
    assert "Start watching" in source
    assert "Search watched products, reads and alerts" in source
    lowered = source.lower()
    for word in INDUSTRY:
        assert word not in lowered


def test_one_red_button_style():
    css = (PAGE / "tiger.css").read_text(encoding="utf-8").lower()
    assert css.count("#e80008") == 1
    assert ".primary" in css


def test_wires_existing_tiger_reads_and_leaves_shared_nav():
    source = _source()
    assert "listTigerWatches" in source
    assert "listTigerObservations" in source
    assert "listTigerAlerts" in source
    assert "createTigerWatch" in source
    assert "deleteTigerWatch" in source
    nav = NAV.read_text(encoding="utf-8")
    assert '"/tiger"' in nav
    assert '"/market-lab"' in nav


def test_page_is_tiger_only():
    names = {path.name for path in _files()}
    assert "page.tsx" in names
    assert "view.tsx" in names
    assert "plugins.tsx" in names
    assert "load.ts" in names
    assert "actions.ts" in names
    joined = " ".join(path.as_posix() for path in _files())
    assert "/zenas" not in joined


OTHER_VAULTS = (
    "tank.vault",
    "lab.vault",
    "tisan.vault",
    "base.vault",
    "rig.vault",
    "zenas.vault",
    "radix.vault",
    "tervory.vault",
)


def test_plugins_use_only_tiger_vault():
    source = _source()
    assert source.count("tiger.vault") >= 2
    for vault in OTHER_VAULTS:
        assert vault not in source
    assert "vaultPlugins" in source
    assert "saveVaultSecret" in source
    assert "uploadVaultFiles" in source
    assert "addVaultLink" in source
    assert "addVaultConnection" in source
    assert "set_switch" not in source
    assert "This vault is off. Turn it on in Tank." in source
    assert "resolveVaultSecret" not in source


def test_plugin_payload_drops_secrets():
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(PAGE / "plugins-data.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
