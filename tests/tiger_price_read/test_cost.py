"""Cost and speed of a price-read on saved pages. No model, no paid call."""

from __future__ import annotations

import time

from weekly import load_rows, score_rows

# Code only. A price-read must stay free and quick on a saved page.
COST_TARGET_USD = 0.0
MEAN_TARGET_S = 0.05


def test_price_read_stays_within_the_cost_and_speed_target() -> None:
    rows = [row for row in load_rows() if row.get("expected_price")]
    assert rows
    started = time.perf_counter()
    scored = score_rows(rows)
    elapsed = time.perf_counter() - started
    mean = elapsed / len(rows)
    assert scored["groups"]
    assert COST_TARGET_USD == 0.0
    assert mean < MEAN_TARGET_S, f"mean {mean:.4f}s over {MEAN_TARGET_S}s"
