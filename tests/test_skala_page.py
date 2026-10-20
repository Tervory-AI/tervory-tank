"""Skala is the skills library: versions, scores, and founder actions.

Vault pipelines and Transfer buttons are gone. Approve stays behind the founder check.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "skala"
ROUTE = ROOT / "workspace" / "app" / "api" / "skala" / "route.ts"


def _page_text() -> str:
    parts: list[str] = []
    for path in sorted(PAGE.rglob("*")):
        if "gold" in path.parts or not path.is_file():
            continue
        if path.suffix in {".ts", ".tsx", ".css"}:
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_page_has_no_vault_off_state_or_transfer_button():
    text = _page_text()
    assert "This vault is off" not in text
    assert ">Transfer<" not in text
    assert "transferToAgent" not in text
    assert "Pipelines" not in text
    for name in ("pipelines.ts", "pipeline-actions.ts", "plugins.ts", "plugin-actions.ts", "vault-server.ts"):
        assert not (PAGE / name).exists()
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    assert "Ask Skala" not in view
    assert '"Run evals"' in view
    assert re.search(r">\s*Approve\s*<", view)
    assert '"Retire"' in view
    assert "Check examples" in view
    assert 'href="/skala/gold"' in view
    assert "confirmApprove" in view
    library = (PAGE / "library.ts").read_text(encoding="utf-8")
    assert "Approve ${id} ${version}?" in library
    assert "no model" in library


def test_library_page_uses_the_skills_list_and_official_logos():
    text = _page_text()
    view = (PAGE / "view.tsx").read_text(encoding="utf-8")
    page = (PAGE / "page.tsx").read_text(encoding="utf-8")
    css = (PAGE / "skala.css").read_text(encoding="utf-8")
    assert "Your account" in view
    assert "Account name" not in view
    for label in ("Dashboard", "Projects", "Chats", "Library", "Settings", "Support"):
        assert label in view
    assert "Search skills" in view
    assert ">Agent<" in view or "Agent" in view
    assert "All states" in view
    assert "No skills yet." in view
    assert "rejectUnlessFounder" in page
    assert "listSkills" in page
    assert "skala.vault" not in text
    assert "library.vault" not in text
    assert "/brand/skala-on-dark.png" in view
    assert "/brand/tervory-logo-reversed.png" in view
    assert "skala-on-light" not in text
    assert view.index("/brand/skala-on-dark.png") < view.index("/brand/tervory-logo-reversed.png")
    for logo in (
        "/brand/base-on-dark.png",
        "/brand/tiger-on-dark.png",
        "/brand/market-lab-on-dark.png",
        "/brand/rig-on-dark.png",
        "/brand/tisan-on-dark.png",
        "/brand/radix-on-dark.png",
        "/brand/zenas-on-dark.png",
        "/brand/tank-on-dark.png",
    ):
        assert logo in text
        assert logo not in view
        assert (ROOT / "workspace" / "public" / logo.lstrip("/")).is_file()
    assert "position: fixed" in css
    assert "overflow: hidden" in css
    assert "overflow: auto" in css
    nav = (ROOT / "workspace" / "app" / "product-nav.ts").read_text(encoding="utf-8")
    assert '"/skala"' not in nav.split("OWN_SHELL", 1)[1]


def test_approve_is_refused_for_a_non_founder():
    route = ROUTE.read_text(encoding="utf-8")
    post = route.split("export async function POST", 1)[1]
    assert post.index("deny()") < post.index('action === "approve"')
    assert post.index("deny()") < post.index("currentTenant(")
    assert route.index("rejectUnlessFounder()") < route.index("approveSkill(")
    assert "status: denied.status" in route
    page = (PAGE / "page.tsx").read_text(encoding="utf-8")
    assert page.index("rejectUnlessFounder()") < page.index("listSkills()")
    assert page.index("if (denied) notFound()") < page.index("return <SkalaApp")
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "skala_library.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_skills_client_still_reaches_skala_and_the_old_vault_helpers():
    """The Tank client keeps its skill and vault helpers. This page no longer calls the vault."""
    client = (ROOT / "workspace" / "lib" / "tank.ts").read_text(encoding="utf-8")
    assert "/v1/skala" in client
    assert "approveSkill" in client
    assert "retireSkill" in client
    assert "runSkillEvals" in client
    assert "/v1/vaults/library.vault/skills" in client
    assert "linkLibrarySkill" in client
    assert "transferLibrarySkill" in client
    page = _page_text()
    assert "transferLibrarySkill" not in page
    assert "linkLibrarySkill" not in page
