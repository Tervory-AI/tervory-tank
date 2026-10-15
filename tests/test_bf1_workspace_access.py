"""Workspace access: customers cannot call Skills or Tank, and sign-in has its own shell.

The rejection itself is exercised in tests/bf1_access.test.ts. This file checks the
routes call that check before any Tank action, and runs that test.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "workspace" / "app"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _handler(source: str, name: str) -> str:
    marker = f"export async function {name}"
    start = source.index(marker)
    rest = source[start + len(marker):]
    nxt = rest.find("\nexport ")
    return source[start:] if nxt < 0 else source[start:start + len(marker) + nxt]


SKILLS = _text(APP / "api" / "skala" / "route.ts")
TANK = _text(APP / "api" / "tank" / "route.ts")
ACCESS = _text(APP / "review" / "access.ts")
LAYOUT = _text(APP / "layout.tsx")
SHELL = _text(APP / "shell.tsx")
NAV = _text(APP / "product-nav.ts")


def test_customer_call_is_rejected():
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "bf1_access.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_skills_and_tank_routes_reject_before_any_tank_call():
    assert "rejectUnlessFounder" in ACCESS
    assert 'from "@/app/review/access"' in SKILLS
    assert 'from "@/app/review/access"' in TANK
    for source, calls in (
        (SKILLS, ("listSkills(", "trySkill(", "runSkillEvals(", "approveSkill(", "retireSkill(")),
        (TANK, ("ladder(", "evalsSummary(", "setCandidate(", "promoteCandidate(", "rollbackModel(")),
    ):
        for name in ("GET", "POST"):
            body = _handler(source, name)
            assert body.index("deny()") < body.index("currentTenant("), name
            assert "if (denied) return denied" in body
        for call in calls:
            assert source.index("rejectUnlessFounder()") < source.index(call)


def test_rejection_is_not_found():
    founder = _text(APP / "review" / "founder.ts")
    assert 'error: "Not found"' in founder
    assert "status: 404" in founder
    for source in (SKILLS, TANK):
        assert "status: denied.status" in source
        assert "error: denied.error" in source


def test_page_address_is_skala():
    assert 'label: "Skala"' in NAV
    assert 'href: "/skala"' in NAV
    assert 'href: "/tank"' in NAV
    page = _text(APP / "skala" / "page.tsx")
    assert "<h1>Skala</h1>" in page
    assert "/api/skala" in page
    config = _text(ROOT / "workspace" / "next.config.ts")
    middleware = _text(ROOT / "workspace" / "middleware.ts")
    assert "redirect" not in config
    assert "redirect" not in middleware
    client = _text(ROOT / "workspace" / "lib" / "tank.ts")
    assert "/v1/skala" in client
    assert (APP / "skala" / "page.tsx").is_file()
    assert (APP / "api" / "skala" / "route.ts").is_file()


def test_product_header_skips_sign_in_sign_up_and_onboarding():
    assert "OrganizationSwitcher" not in LAYOUT
    body = SHELL.split("export function Shell", 1)[1]
    assert body.index("if (usesOwnShell(pathname)) return") < body.index("<header")
    assert body.index("<header") < body.index("<OrganizationSwitcher")
    assert "headerLinks(founder)" in SHELL
    for rel in (
        "sign-in/layout.tsx",
        "sign-in/[[...sign-in]]/page.tsx",
        "sign-up/layout.tsx",
        "sign-up/[[...sign-up]]/page.tsx",
        "onboarding/layout.tsx",
        "onboarding/page.tsx",
    ):
        text = _text(APP / rel)
        assert "OrganizationSwitcher" not in text, rel
    assert "OrganizationList" in _text(APP / "onboarding" / "page.tsx")
    admin = _text(ROOT / "workspace" / "lib" / "admin.ts")
    founder = _text(APP / "review" / "founder.ts")
    for snippet in ('.split(",")', ".trim()", ".includes(userId)"):
        assert snippet in admin
        assert snippet in founder
