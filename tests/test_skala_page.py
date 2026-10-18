"""Skala page keeps the skills registry and wires skala.vault, not tank.vault."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "skala"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in PAGE.rglob("*") if path.suffix in {".ts", ".tsx", ".css"})


def test_panel_keeps_the_registry_and_names_the_bot():
    text = _text()
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    css = (PAGE / "skala.css").read_text(encoding="utf-8")
    registry = (PAGE / "registry.tsx").read_text(encoding="utf-8")
    assert "Account name" in view
    for label in ("Dashboard", "Projects", "Chats", "Settings", "Support", "Skills", "Archive", "Plugins"):
        assert label in view
    assert "AGENT_LABEL.tier0" in view
    assert "Tier 0" in registry
    assert "Chat bot, to be named" in view
    assert "Ask Skala" in view
    assert ">Send<" in view
    assert "Search skills" in view
    assert "Run evals" in registry
    assert "Approve" in registry
    assert "splitPackages" in registry
    assert "/api/skala" in registry
    assert re.search(r"\.sk-panel\s*\{[^}]*position:\s*fixed", css)
    assert re.search(r"\.sk-panel\s*\{[^}]*overflow:\s*hidden", css)
    assert re.search(r"\.sk-main\s*\{[^}]*overflow:\s*auto", css)
    assert "/brand/tervory-logo-reversed.png" in view
    assert "/brand/skala-on-dark.png" in view
    assert "/brand/skala-on-light.png" in view
    assert "tank.vault" not in text
    assert "set_switch" not in text
    nav = (ROOT / "workspace" / "app" / "product-nav.ts").read_text(encoding="utf-8")
    assert '"/skala"' not in nav.split("OWN_SHELL", 1)[1]


def test_plugins_use_skala_vault_and_the_library_is_separate():
    plugins = (PAGE / "vault-server.ts").read_text(encoding="utf-8")
    actions = (PAGE / "plugin-actions.ts").read_text(encoding="utf-8")
    assert 'const VAULT = "skala.vault"' in plugins
    assert 'const VAULT = "skala.vault"' in actions
    assert "library.vault" not in plugins
    assert "library.vault" not in actions
    assert "resolveVaultSecret" not in plugins
    assert "This vault is off. Turn it on in Tank." in (PAGE / "plugins.ts").read_text(encoding="utf-8")
    assert "The skills library is off. Nothing can be linked or transferred." in (PAGE / "plugins.ts").read_text(encoding="utf-8")
    client = (ROOT / "workspace" / "lib" / "tank.ts").read_text(encoding="utf-8")
    assert "/v1/vaults/library.vault/skills" in client
    assert "linkLibrarySkill" in client
    assert "transferLibrarySkill" in client
