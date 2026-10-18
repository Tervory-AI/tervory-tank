"""Weekly re-test, client corrections, and the checks that already exist."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "tiger"))
sys.path.insert(0, str(ROOT / "tests"))

from admin import DEFAULT_MIN_SHADOW, shadow_for_model  # noqa: E402
from feedback import record_correction  # noqa: E402
from tiger_alert_page.score import DROP_POINTS, score_all, tracked, weekly_alerts  # noqa: E402
from tiger_alert_page.weekly import load_baseline  # noqa: E402


def test_review_sheet_is_unverified() -> None:
    text = (ROOT / "tests" / "tiger_alert_page" / "GOLD_REVIEW.md").read_text(encoding="utf-8")
    assert "unverified until Zenas checks it" in text
    assert "| yes |" not in text
    assert text.count("| no |") > 100
    decided = [line for line in text.splitlines() if "| decided by Zenas |" in line]
    assert [line.split("|")[1].strip() for line in decided] == [
        "ca-negation-kinds-s20",
        "ca-positive-keep-s00",
        "ca-positive-keep-s01",
    ]


def test_weekly_retest_is_quiet_and_alerts_on_a_drop() -> None:
    current = tracked(score_all())
    baseline = load_baseline()
    assert weekly_alerts(current, baseline) == []
    slipped = dict(current)
    slipped["build_catch"] = (current["build_catch"] or 0) - (DROP_POINTS + 0.1)
    assert weekly_alerts(slipped, baseline)
    noisy = dict(current)
    noisy["build_false"] = (current["build_false"] or 0) + (DROP_POINTS + 0.1)
    assert weekly_alerts(noisy, baseline)
    same_edge = dict(current)
    same_edge["heldout_refusal"] = (current["heldout_refusal"] or 0) - DROP_POINTS
    assert weekly_alerts(same_edge, baseline) == []


def test_a_client_correction_becomes_an_unverified_gold_row(tmp_path: Path) -> None:
    path = tmp_path / "corrections.jsonl"
    saved = record_correction(
        path,
        skill="change-alerts",
        case_id="fix-001",
        what_changed="Client said the $10.00 to $10.01 move was not worth an alert.",
        expected="no alert",
        note="Saved for Zenas to check. Not part of the build score yet.",
    )
    assert saved["verified"] is False
    again = json.loads(path.read_text(encoding="utf-8").strip())
    assert again["verified"] is False
    assert again["source"] == "client-correction"
    assert again["expected"] == "no alert"


def test_shadow_runs_stay_on_the_existing_tank_check() -> None:
    scored = shadow_for_model([
        {
            "task_type": "tiger.price_extract",
            "candidate_model": "cheap",
            "n": 30,
            "agreement": 0.98,
        }
    ])
    sample, agreement = scored[("tiger.price_extract", "cheap")]
    assert sample == 30
    assert agreement == 0.98
    assert DEFAULT_MIN_SHADOW == 30


def test_room_and_client_checks_stay_in_the_existing_suite() -> None:
    text = (ROOT / "tests" / "test_tiger.py").read_text(encoding="utf-8")
    assert "def test_two_tenants_get_separate_rows_and_a_price_change_alerts" in text
    assert "def test_queries_are_tenant_scoped_and_the_room_is_wired" in text
    image = (ROOT / "agents" / "tiger" / "Dockerfile").read_text(encoding="utf-8")
    assert "page_guard.py" in image
    assert "change_alert.py" in image
