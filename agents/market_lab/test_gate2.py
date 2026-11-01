"""Offline Gate 2 regression tests; none of these inputs are published."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "_chassis"))
from core.ledger import MemoryLedger, PostgresLedger
from core.predictions import calibration, classify, metadata
from core.pure import make_prediction, surge_detect, shift_detect
from core.jobs import perform_resolve

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TENANT, OTHER = str(uuid4()), str(uuid4())


def prediction(**extra):
    return {**make_prediction(tenant_id=TENANT, statement="stored statement", metric_series_id="series",
                             comparator="gte", target=12, made_at=NOW,
                             resolve_by=NOW + timedelta(days=28), rationale="stored rationale"),
            "confidence": .75, "kind": "surge", "feed": "feed", **extra}


def test_classifier_reuses_existing_pure_rules():
    points = [{"date": f"2026-01-{i:02}", "value": 10 if i < 8 else 20} for i in range(1, 10)]
    config = {"window": 6, "z_threshold": 2, "pct_threshold": .25}
    result = classify(points, config)
    assert result["rung"] == 3
    assert result["events"] == surge_detect({"points": points, **config})["events"]
    assert result["shifts"] == shift_detect({"areas": [{"area": "series", "points": points}], **config})["events"]


@pytest.mark.parametrize("confidence", [-.1, 1.1, float("nan"), float("inf")])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises(ValueError):
        metadata(prediction(confidence=confidence))


@pytest.mark.asyncio
async def test_missing_stale_future_and_wrong_tenant_values_never_resolve():
    ledger = MemoryLedger()
    row = prediction()
    ledger.save_prediction(row)
    deadline = NOW + timedelta(days=28)
    for points, clock in [([], deadline), ([{"date": "2026-01-28", "value": 99}], deadline),
                          ([{"date": "2026-01-30", "value": 99}], deadline),
                          ([{"date": "2026-01-29", "value": 99}], deadline - timedelta(days=1))]:
        result = await perform_resolve(tenant_id=TENANT, ledger=ledger,
                                      points_by_series={"series": points}, now=clock)
        assert result["resolved"] == 0
    assert (await perform_resolve(tenant_id=OTHER, ledger=ledger, now=deadline))["resolved"] == 0
    assert ledger.predictions_for(TENANT)[0]["outcome"] is None


@pytest.mark.asyncio
async def test_outcome_preserves_confidence_horizon_and_actual_observation():
    ledger = MemoryLedger()
    row = prediction()
    ledger.save_prediction(row)
    kwargs = dict(tenant_id=TENANT, ledger=ledger, now=NOW + timedelta(days=30),
                  points_by_series={"series": [{"date": "2026-01-30", "value": 13}]})
    assert (await perform_resolve(**kwargs))["resolved"] == 1
    assert (await perform_resolve(**kwargs))["resolved"] == 0
    original, result = ledger.predictions_for(TENANT)
    assert original["outcome"] is None
    assert result["outcome"] == "hit"
    assert result["realised_value"] == 13
    assert result["realised_date"] == "2026-01-30"
    assert result["confidence"] == .75
    assert result["horizon_seconds"] == 28 * 86400
    curve = ledger.calibration_for(TENANT)["curves"][0]
    assert curve["count"] == 1
    assert curve["bins"][0]["realised_rate"] == 1
    assert curve["brier_score"] == .0625
    assert ledger.calibration_for(OTHER)["curves"] == []


def test_calibration_excludes_legacy_unmeasurable_duplicates_and_other_tenants():
    original = metadata(prediction())
    resolved = {**original, "id": str(uuid4()), "outcome": "hit", "resolved_at": NOW + timedelta(days=29),
                "sources": [{"resolves": original["id"]}]}
    duplicate = {**resolved, "id": str(uuid4())}
    legacy = {**original, "id": str(uuid4()), "confidence": None}
    unmeasurable = {**resolved, "id": str(uuid4()), "outcome": "not_measurable",
                   "sources": [{"resolves": legacy["id"]}]}
    foreign = {**resolved, "id": str(uuid4()), "tenant_id": OTHER}
    curves = calibration([original, resolved, duplicate, legacy, unmeasurable, foreign], TENANT)["curves"]
    assert len(curves) == 1 and curves[0]["count"] == 1
    assert calibration([original], TENANT)["curves"] == []


@pytest.mark.asyncio
async def test_postgres_insert_binds_all_metadata_without_mutating_original():
    class Connection:
        async def execute(self, query, *args):
            self.query, self.args = query, args
    conn = Connection()
    row = prediction(realised_date="2026-01-29", realised_value=13)
    await PostgresLedger(conn).save_prediction(row)
    assert len(conn.args) == 19
    assert conn.args[13:] == (28 * 86400, .75, 13, (NOW + timedelta(days=28)).date(), "surge", "feed")
    assert "horizon_seconds" not in row
