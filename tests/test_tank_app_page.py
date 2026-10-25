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
    assert "Your account" in view
    assert "Account name" not in view
    assert "Plugins" in view
    assert "Ask Tank" in view
    assert "Search agents, models, ledger and tasks" in view
    assert "Skills" not in view
    assert "pipelineTo(" not in view
    assert 'aria-label="Boxes"' not in view
    assert 'className="tk-box"' not in view
    assert "The key is held by LiteLLM." in (PAGE / "squads.ts").read_text(encoding="utf-8")
    assert "MODEL_KEY_LINE" in view
    assert "Key is missing" not in view
    assert 'squad.id === "tank"' not in view
    assert "models.ts" not in text
    assert "MODEL_ROSTER" not in text
    assert "listRoster" in (PAGE / "page.tsx").read_text(encoding="utf-8")
    squads = (PAGE / "squads.ts").read_text(encoding="utf-8")
    for name in ("Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas", "Skala", "Tank"):
        assert f'name: "{name}"' in squads
    assert "app/skala" not in text
    assert 'type="password"' not in text
    assert "sk-" not in text
    assert "market.vault" not in text
    assert "base.vault" not in text
    assert "position: fixed" in css
    assert "data-scroll-root" in view
    assert "overflow: hidden" in css
    assert ".tk-main" in css and "overflow-y: auto" in css
    assert ".tk-box" in css and "height: 188px" in css
    assert ".tk-mark" in css and "#001840" in css
    for squad_id in ("base", "tiger", "market-lab", "rig", "tisan", "radix", "zenas", "skala", "tank"):
        logo = ROOT / "workspace" / "public" / "brand" / f"{squad_id}-on-dark.png"
        assert logo.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    assert 'from "@/lib/tank"' in chat
    assert "route(" in chat
    assert "currentTenant" in chat
    assert "process.env" not in chat
    assert "vault-server" not in chat
    assert "loadLabPlugins" not in chat

    nav = NAV.read_text(encoding="utf-8")
    own = nav.split("const OWN_SHELL = ", 1)[1].split("] as const", 1)[0]
    assert '"/tank"' in own
    routes = nav.split("export const SHELL_ROUTES", 1)[1].split("];", 1)[0]
    assert '"/tank"' not in routes

    assert not (PAGE / "models.ts").exists()
    assert "process.env" not in view
    page = (PAGE / "page.tsx").read_text(encoding="utf-8")
    assert "process.env" not in page
    tank_client = (ROOT / "workspace" / "lib" / "tank.ts").read_text(encoding="utf-8")
    assert "/v1/models" in tank_client
    assert "key_missing" not in tank_client
    assert "keyMissing" not in tank_client
    assert "listRoster" in tank_client
