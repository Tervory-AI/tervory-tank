"""Tank app page: fixed panel, search, Ask Tank, and no vault secrets."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "tank"
CHAT = ROOT / "workspace" / "app" / "api" / "tank" / "chat" / "route.ts"
NAV = ROOT / "workspace" / "app" / "product-nav.ts"


def test_tank_records():
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--import",
            str(ROOT / "tests" / "market_lab_register.mjs"),
            "--test",
            str(PAGE / "records.test.ts"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_page_matches_the_panel_and_hides_keys():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PAGE.rglob("*")
        if path.suffix in {".ts", ".tsx", ".css"} and not path.name.endswith(".test.ts")
    )
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    css = (PAGE / "tank.css").read_text(encoding="utf-8")
    chat = CHAT.read_text(encoding="utf-8")

    panel = view.split("<aside", 1)[1].split("</aside>", 1)[0]
    assert panel.index("/brand/tank-on-dark.png") < panel.index("TOP_LINKS")
    assert panel.index("TOP_LINKS") < panel.index("MIDDLE_LINKS")
    assert panel.index("MIDDLE_LINKS") < panel.index("Plugins")
    assert panel.index("Plugins") < panel.index('alt="Tervory"')
    assert panel.index('alt="Tervory"') < panel.index("BOTTOM_LINKS")
    assert view.index('label: "Dashboard"') < view.index('label: "Projects"') < view.index('label: "Chats"')
    assert view.index('label: "Ledger"') < view.index('label: "Tasks"') < view.index('label: "Data"')
    assert view.index('label: "Settings"') < view.index('label: "Support"')
    assert "Account name" in view
    assert "Plugins" in view
    assert "Ask Tank" in view
    assert "Search ledger, tasks and data" in view
    assert "Skills" not in view
    assert "skala" not in text.lower()
    assert 'type="password"' not in text
    assert "sk-" not in text
    assert "market.vault" not in text
    assert "base.vault" not in text
    assert "position: fixed" in css
    assert "data-scroll-root" in view
    assert "overflow: hidden" in css
    assert ".tk-main" in css and "overflow-y: auto" in css

    assert 'from "@/lib/tank"' in chat
    assert "route(" in chat
    assert "currentTenant" in chat
    assert "process.env" not in chat
    assert "vault-server" not in chat
    assert "loadLabPlugins" not in chat

    nav = NAV.read_text(encoding="utf-8")
    assert '"/tank"' not in nav.split("OWN_SHELL", 1)[-1]
