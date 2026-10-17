"""Replay price history. Pass: 95%+ of real changes, under 2% false alarms."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "tiger"))
sys.path.insert(0, str(ROOT / "tests"))

import change_alert  # noqa: E402
from tiger_alert_page.score import (  # noqa: E402
    ALERT_MEAN_MS,
    COST_TARGET_USD,
    _rows,
    score_alerts,
)


def test_hand_checked_boundaries() -> None:
    history = [
        {"price": "100.00", "availability": "InStock", "method": "jsonld"},
        {"price": "100.004", "availability": "InStock", "method": "jsonld"},
        {"price": "95.00", "availability": "InStock", "method": "jsonld"},
        {"price": "94.99", "availability": "OutOfStock", "method": "jsonld"},
        {"price": "80.00", "availability": "OutOfStock", "method": "jsonld"},
    ]
    got = change_alert.replay(history, "0.05")
    assert [row["alerts"] for row in got[:3]] == [[], [], []]
    assert [row["kind"] for row in got[3]["alerts"]] == ["stock"]
    assert [row["kind"] for row in got[4]["alerts"]] == ["price"]


def test_gold_change_alerts_meet_the_bar() -> None:
    report = score_alerts(_rows("change_alerts.jsonl"))
    build = report["summary"]["build"]
    held = report["summary"]["heldout"]
    assert build["catch_n"] > 0 and build["quiet_n"] > 0
    assert build["catch_pct"] >= 95
    assert build["false_pct"] < 2
    assert held["catch_pct"] >= 95
    assert held["false_pct"] < 2
    assert report["cost_usd"] == COST_TARGET_USD
    assert report["mean_ms"] <= ALERT_MEAN_MS
    assert all(row["verified"] == "no" for row in report["rows"])


def test_alert_traps() -> None:
    report = score_alerts(_rows("change_alert_traps.jsonl"))
    assert report["rows"]
    assert all(row["pass"] for row in report["rows"])
    failed = [row["id"] for row in report["rows"] if not row["pass"]]
    assert not failed
