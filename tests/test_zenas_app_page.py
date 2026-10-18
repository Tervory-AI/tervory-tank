"""Zenas app page: own panel, zenas.vault only, vault starts off."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "zenas"


def test_zenas_frame_rules() -> None:
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--import",
            str(ROOT / "tests" / "market_lab_register.mjs"),
            "--test",
            str(PAGE / "frame.test.ts"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_page_uses_zenas_vault_and_does_not_turn_it_on() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PAGE.rglob("*") if path.suffix in {".ts", ".tsx", ".css"})
    assert "This vault is off. Turn it on in Tank." in text
    assert "Search matters, drafts, documents and citations" in text
    assert "ZENAS · CIVIL · SOUTH AFRICA" in text
    assert "Sources" in text
    assert 'type="password"' in text
    assert "zenas-on-dark.png" in text
    assert "tervory-logo-reversed.png" in text
    assert "console." not in text
    assert "set_switch" not in text
    assert "tank.vault" not in text
    for name in ("vault-server.ts", "plugin-actions.ts"):
        server = (PAGE / name).read_text(encoding="utf-8")
        assert 'const VAULT = "zenas.vault"' in server
        assert 'const SQUAD = "zenas"' in server
        assert "resolveVaultSecret" not in server
    css = (PAGE / "zenas.css").read_text(encoding="utf-8")
    assert re.search(r"\.zn-panel\s*\{[^}]*position:\s*fixed", css)
    assert re.search(r"\.zn-panel\s*\{[^}]*overflow:\s*hidden", css)
    assert re.search(r"\.zn-body\s*\{[^}]*overflow-y:\s*auto", css)
    logo = ROOT / "workspace" / "public" / "brand" / "zenas-on-dark.png"
    assert logo.is_file()
    assert logo.stat().st_size > 1000
    nav = (ROOT / "workspace" / "app" / "product-nav.ts").read_text(encoding="utf-8")
    assert '"/zenas"' not in nav
