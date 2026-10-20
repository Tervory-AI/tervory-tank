"""W-2 billing: plans, usage, and invoices. No Stripe network."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BILLING = ROOT / "workspace" / "app" / "billing"


def test_billing_logic_runs_without_stripe() -> None:
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "w2" / "billing.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_billing_screen_stays_in_the_workspace() -> None:
    page = (BILLING / "page.tsx").read_text(encoding="utf-8")
    screen = (BILLING / "screen.tsx").read_text(encoding="utf-8")
    billing = (BILLING / "billing.ts").read_text(encoding="utf-8")
    actions = (BILLING / "actions.ts").read_text(encoding="utf-8")
    nav = (ROOT / "workspace" / "app" / "product-nav.ts").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "Pricing is being finalised." in billing
    assert "Choose this plan" in (BILLING / "choose.tsx").read_text(encoding="utf-8")
    assert 'href: "/billing"' in nav
    assert 'label: "Billing"' in nav
    assert "@/lib/tank" not in page
    assert "@/lib/tank" not in actions
    assert "tank/main.py" not in billing
    webhook = (BILLING / "webhook.ts").read_text(encoding="utf-8")
    route = (ROOT / "workspace" / "app" / "api" / "billing" / "webhook" / "route.ts").read_text(encoding="utf-8")
    middleware = (ROOT / "workspace" / "middleware.ts").read_text(encoding="utf-8")
    assert re.search(r"\$\d", screen) is None
    assert "NEXT_PUBLIC_STRIPE" not in example
    assert "sk_live_" not in example
    assert "sk_live_" not in webhook
    assert "constructEvent" in webhook
    assert "STRIPE_WEBHOOK_SECRET" in route
    assert "/api/billing/webhook" in middleware
    for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PLAN_PRICE_IDS", "BILLING_PUBLIC_ORIGIN"):
        line = next(item for item in example.splitlines() if item.startswith(f"{name}="))
        assert line == f"{name}="
