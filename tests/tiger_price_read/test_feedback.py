"""A client correction becomes an unverified gold example. No new screen."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PATH = ROOT / "agents" / "tiger" / "gold_feedback.py"
_spec = importlib.util.spec_from_file_location("tiger_gold_feedback", _PATH)
assert _spec is not None and _spec.loader is not None
feedback = importlib.util.module_from_spec(_spec)
sys.modules["tiger_gold_feedback"] = feedback
_spec.loader.exec_module(feedback)

from reader import primary_price, read_price


def test_correction_is_stored_unverified(tmp_path: Path) -> None:
    inbox = tmp_path / "corrections.jsonl"
    row = feedback.record_correction(
        page_id="client-mug-1",
        layout="woocommerce-sale",
        expected_price="$12.00",
        html="<html><body><h1>Mug</h1><span class=\"product-price\">$12.00</span></body></html>",
        url="https://example.test/mug",
        currency="usd",
        note="Client said the sale price is 12, not 18.",
        inbox=inbox,
    )
    assert row["verified"] is False
    assert row["expected_price"] == "12.00"
    assert row["split"] == "inbox"
    assert row["source"] == "client_correction"
    saved = json.loads(inbox.read_text(encoding="utf-8").strip())
    assert saved["verified"] is False
    html = (tmp_path / "client-mug-1.html").read_text(encoding="utf-8")
    assert primary_price(read_price(html)) == "12.00"


def test_a_correction_without_a_price_is_refused(tmp_path: Path) -> None:
    try:
        feedback.record_correction(
            page_id="bad",
            layout="x",
            expected_price="free",
            html="<html></html>",
            inbox=tmp_path / "corrections.jsonl",
        )
    except ValueError as exc:
        assert "price" in str(exc)
    else:
        raise AssertionError("expected a refusal")
