"""The weekly re-test alerts only when a gold score drops by more than 2 points."""

from __future__ import annotations

from weekly import alert_for


def _score(build: float, holdout: float) -> dict:
    return {"groups": {"build": {"pct": build, "n": 80}, "holdout": {"pct": holdout, "n": 20}}}


def test_a_two_point_drop_does_not_alert() -> None:
    result = alert_for(_score(96.0, 95.0), _score(98.0, 97.0))
    assert result["alert"] is False
    assert result["reasons"] == []


def test_more_than_two_points_alerts() -> None:
    result = alert_for(_score(95.9, 98.0), _score(98.0, 98.0))
    assert result["alert"] is True
    assert "build" in result["reasons"][0]


def test_holdout_drop_alerts_on_its_own() -> None:
    result = alert_for(_score(98.0, 90.0), _score(98.0, 98.0))
    assert result["alert"] is True
    assert "holdout" in result["reasons"][0]
