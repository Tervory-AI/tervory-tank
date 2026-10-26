"""Market Lab page: feed list matches ML-1, and the panel stays fixed."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "market-lab"


def _node_test() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--import",
            str(ROOT / "tests" / "market_lab_register.mjs"),
            "--test",
            str(PAGE / "model.test.ts"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_market_lab_model():
    result = _node_test()
    assert result.returncode == 0, result.stdout + result.stderr


def test_catalog_matches_feed_sources():
    sys.path.insert(0, str(ROOT / "agents" / "market_lab"))
    from feeds.engines.ffl.sources import sources
    from feeds.keys import bind_key

    listed = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            "import { CATALOG } from './workspace/app/market-lab/catalog.ts';"
            "process.stdout.write(JSON.stringify(CATALOG.map((item) => [item.id, item.keyName])));",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert listed.returncode == 0, listed.stderr
    catalog = {item_id: key for item_id, key in json.loads(listed.stdout)}
    specs = {spec.id: bind_key(spec).key_name for spec in sources()}
    assert catalog.keys() == specs.keys()
    assert catalog == specs


def test_page_does_not_invent_numbers_or_store_keys():
    text = "\n".join(path.read_text(encoding="utf-8") for path in PAGE.rglob("*") if path.suffix in {".ts", ".tsx", ".css"})
    assert "Example" not in text
    assert "3.71" not in text
    assert "52418" not in text
    assert "Integrations" not in text
    assert "Plugins" in text
    assert "Sources" in text
    assert "Nothing was stored" in text
    assert "Nothing was saved" in text
    assert "•••• saved" not in text
    assert "Provided by your workspace administrator" in text
    assert 'type="password"' in text
    assert "console." not in text
    readers = (PAGE / "load.ts").read_text(encoding="utf-8") + (PAGE / "page.tsx").read_text(encoding="utf-8")
    assert "writeFile" not in readers
    assert "INSERT" not in readers
    catalog = (PAGE / "catalog.ts").read_text(encoding="utf-8")
    assert 'MARKET_LAB_LOGO_SRC = "/brand/market-lab-on-dark.png"' in catalog
    assert (ROOT / "workspace/public/brand/market-lab-on-dark.png").is_file()
    css = (PAGE / "market-lab.css").read_text(encoding="utf-8")
    assert re.search(r"\.ml-panel\s*\{[^}]*position:\s*fixed", css)
    assert re.search(r"\.ml-panel\s*\{[^}]*overflow-y:\s*auto", css)
    assert re.search(r"\.ml-main\s*\{[^}]*overflow-y:\s*auto", css)
    nav = (ROOT / "workspace" / "app" / "product-nav.ts").read_text(encoding="utf-8")
    assert '"/market-lab"' in nav
    assert not (ROOT / "workspace/app/api/market-lab/chat/route.ts").exists()
    ask = (PAGE / "ask/route.ts").read_text(encoding="utf-8")
    assert 'marketLabRequest' in ask and '"ask"' in ask
    assert 'tier0.answer' not in text and 'route(' not in ask
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    assert "Help" not in view
    assert "WORKSPACE_HREF" not in view
    assert "headerLinks" not in view
    assert 'label: "Usage"' in view
    assert 'href: "/ledger"' in view
    assert 'label: "Tasks"' in view
    assert 'href: "/tasks"' in view
    assert 'label: "Chats"' in view
    assert 'label: "Workspace setup"' in view
    assert 'href: "/onboarding"' in view
    assert 'label: "Support"' not in view
    brand = view.index('className="ml-brand"')
    bottom = view.index('className="ml-bottom"')
    settings = view.index('aria-label="Workspace"')
    assert brand < bottom < settings
    assert "MARKET_LAB_LOGO_SRC" in view[brand:bottom]
    assert "tervory-logo-reversed.png" in view[bottom:settings]
    assert "Market Lab logo, added later" not in view
    for old in ("Chat", "Data", "Ledger", "Skills", "Tank"):
        assert f'label: "{old}"' not in view
    plugins = (PAGE / "plugins.ts").read_text(encoding="utf-8")
    assert "Plugins are not available yet. Ask your workspace administrator to enable them." in plugins
    for name in ("vault-server.ts", "plugin-actions.ts"):
        server = (PAGE / name).read_text(encoding="utf-8")
        assert 'const VAULT = "lab.vault"' in server
        assert "tank.vault" not in server
