"""Rig agent page. No database and no network."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "rig"


def _source() -> str:
    parts = [path.read_text(encoding="utf-8") for path in sorted(PAGE.rglob("*")) if path.is_file()]
    return "\n".join(parts)


def test_panel_is_fixed_and_split_with_the_account_nav():
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
    lab = (PAGE / "lab.tsx").read_text(encoding="utf-8")
    panel = lab.split('<aside className="panel"', 1)[1].split("</aside>", 1)[0]
    assert "rig-on-dark.png" in panel
    assert panel.index("rig-on-dark.png") < panel.index("panel-top")
    assert panel.index("panel-own") < panel.index("tervory-logo-reversed.png")
    assert panel.index("tervory-logo-reversed.png") < panel.index("ACCOUNT_BOTTOM")
    assert (ROOT / "workspace" / "public" / "brand" / "rig-on-dark.png").is_file()
    assert "Rig logo, coming later" not in source
    assert "headerLinks" not in source
    assert "Last refreshed" not in source
    assert ">Workspace<" not in source
    assert ">Help<" not in source
    page = (PAGE / "page.tsx").read_text(encoding="utf-8")
    assert "headerLinks" not in page
    assert 'accountName = "Your account"' in page
    assert 'accountName = "Account name"' not in page
    nav = (PAGE / "copy.ts").read_text(encoding="utf-8")
    for label in ("Dashboard", "Projects", "Chats", "Settings", "Support"):
        assert f'label: "{label}"' in nav
    for gone in ("Chat", "Tasks", "Data", "Ledger"):
        assert f'label: "{gone}"' not in nav
    assert "RIG" in source
    assert "Plugins" in source
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
    assert "•••• saved 17 Oct" not in source
    assert 'MASK = "••••••••"' in source
    assert "rk_pub_" not in source
    assert "api_key=" not in source.lower()
    assert "sk-" not in source
    assert "Example Rifle" not in source
    assert "ExampleBrand" not in source
    assert "/v1/rig/admin" not in source
    assert "/v1/rig/search" in source
    assert "/v1/rig/ask" in source
    assert "I don't know" in source


def test_plugins_vault_starts_off_and_is_rig_only():
    source = _source()
    assert 'VAULT_OFF_MESSAGE = "This vault is off. Turn it on in Tank."' in source
    assert 'className="vault-off"' in (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    assert "if (!raw.enabled) return offPanel()" in source
    vaults = set(__import__("re").findall(r"[A-Za-z_]+\.vault", source))
    assert vaults == {"rig.vault"}
    server = (PAGE / "vault-server.ts").read_text(encoding="utf-8")
    assert 'const VAULT = "rig.vault"' in server
    assert 'const SQUAD = "rig"' in server
    assert "/switch" not in source
    assert "admin/vaults" not in source
    assert "enabled" not in server


def test_vault_keys_stay_masked_and_calls_stay_on_the_server():
    model = (PAGE / "vault-model.ts").read_text(encoding="utf-8")
    plugins = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    actions = (PAGE / "plugin-actions.ts").read_text(encoding="utf-8")
    server = (PAGE / "vault-server.ts").read_text(encoding="utf-8")
    assert "value?" not in model and "value:" not in model and ".value" not in model
    assert "content" not in model
    assert ".token" not in model
    assert "row.mask" in plugins
    assert "type=\"password\"" in plugins
    assert "./vault-server" not in plugins
    assert "fetch(" not in plugins
    assert actions.startswith('"use server"')
    assert "x-tank-key" in server
    assert "TANK_API_KEY" in server
    assert "/v1/vaults/" in server
    assert "fetch(" in server
    for path in sorted(PAGE.rglob("*")):
        if not path.is_file() or path.name == "vault-server.ts":
            continue
        text = path.read_text(encoding="utf-8")
        assert "x-tank-key" not in text
        assert "TANK_API_KEY" not in text
        assert "/v1/vaults/" not in text


def test_one_red_button_style():
    css = (PAGE / "rig.css").read_text(encoding="utf-8").lower()
    assert css.count("#e80008") == 1
    assert ".primary" in css
    assert "search" in (PAGE / "search-view.tsx").read_text(encoding="utf-8").lower()
