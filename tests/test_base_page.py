"""Base page: counts come from Tank, only approved skills show, the panel stays fixed, and no key is stored in code."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "base"


def _sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(PAGE.rglob("*")) if path.suffix in {".ts", ".tsx", ".css"})


def test_base_model():
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--import",
            str(ROOT / "tests" / "base_page_register.mjs"),
            "--test",
            str(PAGE / "model.test.ts"),
            str(PAGE / "records.test.ts"),
            str(PAGE / "vault.test.ts"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_panel_is_anchored_and_only_body_scrolls():
    css = (PAGE / "base.css").read_text(encoding="utf-8")
    assert re.search(r"\.bcp-panel\s*\{[^}]*position:\s*fixed", css)
    assert re.search(r"\.bcp-panel\s*\{[^}]*height:\s*100dvh", css)
    assert re.search(r"\.bcp-main\s*\{[^}]*overflow-y:\s*auto", css)
    assert re.search(r"body:has\(\.bcp\)\s*\{[^}]*overflow:\s*hidden", css) or "body:has(.bcp) {" in css
    nav = (ROOT / "workspace" / "app" / "product-nav.ts").read_text(encoding="utf-8")
    assert '"/base"' in nav


def test_one_red_primary_per_view():
    css = (PAGE / "base.css").read_text(encoding="utf-8")
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    reds = re.findall(r"#e80008", rules, flags=re.I)
    assert len(reds) == 1, "red is only used by .bcp-primary"
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    assert view.count('className="bcp-primary"') == 1
    assert 'className="bcp-primary"' not in (PAGE / "ask.tsx").read_text(encoding="utf-8")
    sources = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    for part in ("function KeysTab", "function FilesTab", "function LinksTab", "function McpTab"):
        start = sources.index(part)
        end = sources.find("\nfunction ", start + 1)
        body = sources[start:end]
        assert body.count('className="bcp-primary"') == 1, part
    assert "visibility: hidden" in css  # the page's red button steps back while Plugins is open


def test_no_secrets_and_keys_show_as_dots():
    text = _sources()
    sources = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    assert "{row.mask}" in sources and "••••••••" in (PAGE / "plugin-panel.ts").read_text(encoding="utf-8")
    # Secret fields are password inputs. The browser never calls Tank itself: writes are server actions.
    assert 'type="password"' in sources and "Paste key (hidden once saved)" in sources
    assert "@/lib/tank" not in sources and "@/lib/tank" not in (PAGE / "view.tsx").read_text(encoding="utf-8")
    ask = (PAGE / "ask.tsx").read_text(encoding="utf-8")
    for banned in ("fetch(", "localStorage", "sessionStorage", "document.cookie", "process.env"):
        assert banned not in sources, banned
        assert banned not in ask, banned
    assert not re.search(r"(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}", text)
    assert not re.search(r"BSA[A-Za-z0-9_-]{20,}", text)
    assert "BRAVE_API_KEY" not in text


def test_page_only_reads_records():
    load = (PAGE / "load.ts").read_text(encoding="utf-8")
    search = (PAGE / "search.ts").read_text(encoding="utf-8")
    for write in ("baseRun", "baseRerun", "baseRetry", "approveSkill", "retireSkill", "route(", "createTask"):
        assert write not in load, write
        assert write not in search, write
    actions = (PAGE / "actions.ts").read_text(encoding="utf-8")
    assert "revalidatePath" in actions and "tank" not in actions.lower()


def test_connections_tab_is_plugins_and_sources_only_means_answer_references():
    assert not (PAGE / "sources.tsx").exists()
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    plugins = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    assert "<span>Plugins</span>" in view and 'id="bcp-plugins-title">Plugins<' in plugins
    panel = view[view.index("<aside"):view.index("</aside>")]
    code = re.sub(r"/\*.*?\*/", "", plugins, flags=re.S) + panel
    assert not re.search(r"\bSources\b", code.replace("Source links", "")), "Sources is not a name for connections"
    assert "Integrations" not in code and "Integrations" not in view
    for tab in ("API keys", "Files", "Source links", "MCP connections"):
        assert f'label: "{tab}"' in plugins, tab
    ask = (PAGE / "ask.tsx").read_text(encoding="utf-8")
    assert ">Sources<" in ask  # the references that come back with an answer


def test_search_and_ask_live_in_the_body():
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    body = view[view.index('className="bcp-main"'):]
    panel = view[view.index("<aside"):view.index("</aside>")]
    assert "<RecordSearch" in body and "<AskBase" in body
    assert "<RecordSearch" not in panel and "<AskBase" not in panel
    ask = (PAGE / "ask.tsx").read_text(encoding="utf-8")
    chat = ask[ask.index("export function AskBase"):]
    # The thread comes first, then the box with Send beside it.
    assert chat.index('className="bcp-thread"') < chat.index('className="bcp-composer"')
    composer = chat[chat.index('className="bcp-composer"'):]
    assert composer.index("<textarea") < composer.index("Send")


OTHER_VAULTS = ("tank.vault", "lab.vault", "tisan.vault", "tiger.vault", "rig.vault", "zenas.vault", "radix.vault", "tervory.vault")


def test_plugins_use_base_vault_only():
    panel = (PAGE / "plugin-panel.ts").read_text(encoding="utf-8")
    assert 'BASE_VAULT = "base.vault"' in panel and 'BASE_SQUAD = "base"' in panel
    text = _sources()
    code = re.sub(r"//.*|/\*.*?\*/", "", text, flags=re.S)
    for vault in OTHER_VAULTS:
        # Only the test of the refusal path names another vault.
        assert vault not in code, vault
    for name in ("vault-server.ts", "plugin-actions.ts"):
        body = (PAGE / name).read_text(encoding="utf-8")
        assert "BASE_VAULT, BASE_SQUAD" in body, name
        assert '"lab.vault"' not in body and "market_lab" not in body, name
    # Base never reads a secret value and never turns a vault on.
    assert "resolveVaultSecret" not in text and "platform_secret" not in text
    assert "/switch" not in text and "/v1/admin/vaults" not in text
    assert "enabled: true" not in code.replace("enabled: true,\n    message: null", "")


def test_vault_off_message_and_no_switch_in_the_ui():
    plugins = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    panel = (PAGE / "plugin-panel.ts").read_text(encoding="utf-8")
    assert 'VAULT_OFF_MESSAGE = "This vault is off. Turn it on in Tank."' in panel
    assert "!plugins.enabled ? (" in plugins and "{plugins.message || VAULT_OFF_MESSAGE}" in plugins
    lowered = re.sub(r"/\*.*?\*/", "", plugins, flags=re.S).lower()
    for banned in ("turn on</", ">turn it on<", "enable vault", "switch"):
        assert banned not in lowered, banned
    # The off check sits in front of every write.
    assert "if (!plugins.enabled || busy) return;" in plugins


def test_plugins_calls_go_through_tank_server_side():
    actions = (PAGE / "plugin-actions.ts").read_text(encoding="utf-8")
    assert actions.lstrip().startswith('"use server";')
    for call in ("saveVaultSecret", "removeVaultSecret", "uploadVaultFiles", "removeVaultFile", "addVaultLink", "removeVaultLink", "addVaultConnection", "removeVaultConnection"):
        assert call in actions, call
    server = (PAGE / "vault-server.ts").read_text(encoding="utf-8")
    assert '"use server"' not in server and "vaultPlugins(BASE_VAULT, BASE_SQUAD" in server
    tank = (ROOT / "workspace" / "lib" / "tank.ts").read_text(encoding="utf-8")
    assert 'headers.set("x-tervory-squad", squad);' in tank and 'headers.set("x-tank-key", TANK_API_KEY);' in tank


def test_left_panel_order():
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    panel = view[view.index("<aside"):view.index("</aside>")]
    order = [
        "bcp-logo",
        "base-on-dark.png",
        "bcp-account",
        "STANDARD_TOP",
        "pageNav.map",
        "<span>Plugins</span>",
        "tervory-logo-reversed.png",
        "STANDARD_BOTTOM",
    ]
    spots = [panel.index(mark) for mark in order]
    assert spots == sorted(spots), order
    top = panel[: panel.index("bcp-account")]
    assert 'src="/brand/base-on-dark.png"' in top
    assert "tervory-logo-reversed.png" not in top
    bottom = panel[panel.index("bcp-panel-bottom") :]
    assert bottom.index("tervory-logo-reversed.png") < bottom.index("STANDARD_BOTTOM")
    assert 'src="/brand/tervory-logo-reversed.png"' in bottom
    assert re.search(r'STANDARD_TOP = \[\s*\{ href: "[^"]+", label: "Dashboard" \},\s*\{ href: "[^"]+", label: "Projects" \},\s*\{ href: "[^"]+", label: "Chats" \}', view)
    assert re.search(r'STANDARD_BOTTOM = \[\s*\{ href: "[^"]+", label: "Settings" \},\s*\{ href: "[^"]+", label: "Support" \}', view)
    logo = ROOT / "workspace" / "public" / "brand" / "base-on-dark.png"
    assert logo.is_file()
    assert "Base logo" not in view and "base-logo" not in view
