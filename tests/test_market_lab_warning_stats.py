"""No look-ahead, no overlapping votes, and missing observations are not misses."""

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.warning_stats import analyze, measured
from engines.ffl.warnings import plan, product_series


def history(episodes=3, *, missing=False):
    start = date(2020, 1, 1)
    drops = [42 + 126 * i for i in range(episodes + 1)]
    end = drops[-1] + 7
    up, down = [], []
    for d in range(0, end + 1, 7):
        up.append(
            {
                "date": (start + timedelta(days=d)).isoformat(),
                "value": 70 if d in drops else 100,
            }
        )
        out = any(trigger + 35 <= d <= trigger + 56 for trigger in drops)
        if not (missing and 50 <= d <= 100):
            down.append(
                {
                    "date": (start + timedelta(days=d)).isoformat(),
                    "value": 1 if out else 2,
                }
            )
    return up, down, start + timedelta(days=end)


def test_three_past_episodes_and_the_current_episode_is_not_a_vote():
    up, down, now = history()
    result = analyze(up, down, plan()["pairs"][0], now)
    assert result["episode_count"] == result["hits"] == 3
    assert result["lag_min"] == result["lag_max"] == 35
    assert result["current"]["start"] == up[-2]["date"]
    assert result["hit_rate"] == 1


def test_one_episode_does_not_meet_the_gate_and_future_rows_do_not_help():
    up, down, now = history(1)
    config = plan()["pairs"][0]
    result = analyze(up, down, config, now)
    assert result["episode_count"] == 1 < config["min_episodes"]
    assert (
        analyze(up + [{"date": "2099-01-01", "value": 1}], down, config, now) == result
    )


def test_missing_coverage_is_excluded_from_both_counts():
    up, down, now = history(missing=True)
    result = analyze(up, down, plan()["pairs"][0], now)
    assert result["episode_count"] == result["hits"] == 2
    assert not measured(down, date(2020, 1, 1), now, 14)


def test_miss_is_part_of_the_denominator_and_not_the_lag_range():
    up, down, now = history()
    for point in down:
        if date.fromisoformat(point["date"]) < date(2020, 5, 1):
            point["value"] = 2
    result = analyze(up, down, plan()["pairs"][0], now)
    assert result["episode_count"] == 3 and result["hits"] == 2
    assert result["hit_rate"] == 2 / 3 and result["lag_min"] == 35


def test_engine_understands_actual_stored_stock_spellings_and_keeps_unknown_missing():
    watch = {"id": "watch", "engine": "ffl", "url": "https://shop.test/item"}
    rows = [
        {
            "id": str(i),
            "ts": f"2020-01-0{i + 1}",
            "product_name": "Ammunition",
            "availability": value,
        }
        for i, value in enumerate(
            ["InStock", "OutOfStock", "in_stock", "out_of_stock", None]
        )
    ]
    output = product_series(watch, rows)
    assert [p["value"] for p in output[0]["points"]] == ["2", "1", "2", "1"]
    assert product_series({**watch, "engine": "other"}, rows) == []


def test_already_changed_baseline_is_not_a_comparable_episode():
    up, down, now = history()
    first_change = date(2020, 1, 1) + timedelta(days=42)
    next(point for point in down if date.fromisoformat(point["date"]) == first_change)[
        "value"
    ] = 1
    assert analyze(up, down, plan()["pairs"][0], now)["episode_count"] == 2


def test_nearby_upstream_moves_count_as_one_episode():
    up, down, now = history()
    up[8]["value"] = 50
    result = analyze(up, down, plan()["pairs"][0], now)
    assert result["episode_count"] == 3
    for episode in result["episodes"]:
        # The stored coverage evidence includes the observation that closes the window.
        assert episode["observations"][-1]["date"] >= episode["end"]


def test_a_changed_product_name_does_not_supply_history_for_its_replacement():
    watch = {"id": "watch", "engine": "ffl", "url": "https://shop.test/item"}
    rows = [
        {
            "id": "old",
            "ts": "2020-01-01",
            "product_name": "Old product",
            "availability": "InStock",
        },
        {
            "id": "new",
            "ts": "2020-02-01",
            "product_name": "New product",
            "availability": "OutOfStock",
        },
        {
            "id": "unknown",
            "ts": "2020-02-08",
            "product_name": None,
            "availability": "InStock",
        },
    ]
    result = product_series(watch, rows)[0]
    assert result["ref"] != product_series(watch, rows[:1])[0]["ref"]
    assert result["name"] == "New product"
    assert [p["observation_id"] for p in result["points"]] == ["new"]
