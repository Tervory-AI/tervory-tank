"""Skala page matches the app frame and wires skala.vault, not tank.vault."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "skala"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in PAGE.rglob("*") if path.suffix in {".ts", ".tsx", ".css"})


def test_page_matches_the_app_frame():
    text = _text()
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    css = (PAGE / "skala.css").read_text(encoding="utf-8")
    assert "Account name" in view
    for label in ("Dashboard", "Projects", "Chats", "Library", "Plugins", "Settings", "Support"):
        assert label in view
    assert "Ask Skala" in view
    assert "Search the library" in view
    assert ">Send<" in view
    assert "This vault is off." in view or "LIBRARY_OFF_MESSAGE" in view
    assert "Chat bot" not in text
    assert "Run evals" not in view
    assert not (PAGE / "registry.tsx").exists()
    assert "approve" not in view.lower()
    assert "retire" not in view.lower()
    assert re.search(r"\.sk-panel\s*\{[^}]*position:\s*fixed", css)
    assert re.search(r"\.sk-panel\s*\{[^}]*overflow:\s*hidden", css)
    assert re.search(r"\.sk-main\s*\{[^}]*overflow:\s*auto", css)
    assert "/brand/skala-on-dark.png" in view
    assert "/brand/tervory-logo-reversed.png" in view
    assert "skala-on-light" not in view
    assert view.index("/brand/skala-on-dark.png") < view.index("/brand/tervory-logo-reversed.png")
    assert "tank.vault" not in text
    assert "set_switch" not in text
    pipes = (PAGE / "pipelines.ts").read_text(encoding="utf-8")
    for label in ("Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas", "Skala", "Tank"):
        assert label in pipes
    for logo in (
        "/brand/base-on-dark.png",
        "/brand/tiger-on-dark.png",
        "/brand/market-lab-on-dark.png",
        "/brand/rig-on-dark.png",
        "/brand/tisan-on-dark.png",
        "/brand/radix-on-dark.png",
        "/brand/zenas-on-dark.png",
        "/brand/skala-on-dark.png",
        "/brand/tank-on-dark.png",
    ):
        assert logo in pipes
        assert (ROOT / "workspace" / "public" / logo.lstrip("/")).is_file()
    assert "sk-mark" in view
    assert "grid-auto-rows: 292px" in css
    assert "height: 292px" in css
    assert "This vault is off. The transfer waits." in pipes
    assert "This pipeline waits." in pipes
    assert "TRANSFER_WAITS" in view
    assert "TANK_WAITS" in view
    assert "transferLibrarySkill" in (PAGE / "pipeline-actions.ts").read_text(encoding="utf-8")
    assert "publish" not in (PAGE / "pipeline-actions.ts").read_text(encoding="utf-8")
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
    assert "This vault is off. Nothing can be linked or transferred." in (PAGE / "plugins.ts").read_text(encoding="utf-8")
    client = (ROOT / "workspace" / "lib" / "tank.ts").read_text(encoding="utf-8")
    assert "/v1/vaults/library.vault/skills" in client
    assert "linkLibrarySkill" in client
    assert "transferLibrarySkill" in client
