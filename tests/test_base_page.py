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
    sources = (PAGE / "sources.tsx").read_text(encoding="utf-8")
    for part in ("function KeysTab", "function FilesTab", "function LinksTab", "function McpTab"):
        start = sources.index(part)
        end = sources.find("\nfunction ", start + 1)
        body = sources[start:end]
        assert body.count('className="bcp-primary"') == 1, part
    assert "visibility: hidden" in css  # the page's red button steps back while Sources is open


def test_no_secrets_and_keys_show_as_dots():
    text = _sources()
    sources = (PAGE / "sources.tsx").read_text(encoding="utf-8")
    assert "••••" in sources
    # Secret fields are password inputs and nothing is sent anywhere.
    assert 'placeholder="Paste key"' in sources and 'type="password"' in sources
    for banned in ("fetch(", "localStorage", "sessionStorage", "document.cookie", "process.env"):
        assert banned not in sources, banned
    assert not re.search(r"(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}", text)
    assert not re.search(r"BSA[A-Za-z0-9_-]{20,}", text)
    assert "BRAVE_API_KEY" not in text


def test_examples_stay_labelled_and_page_only_reads():
    sources = (PAGE / "sources.tsx").read_text(encoding="utf-8")
    assert sources.count("<Example />") >= 1
    assert "Not connected yet. Nothing was saved or sent." in sources
    load = (PAGE / "load.ts").read_text(encoding="utf-8")
    for write in ("baseRun", "baseRerun", "baseRetry", "approveSkill", "retireSkill"):
        assert write not in load, write
    actions = (PAGE / "actions.ts").read_text(encoding="utf-8")
    assert "revalidatePath" in actions and "tank" not in actions.lower()
