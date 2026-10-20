"""Versioned gap rejection evals and area/segment regression checks."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tank/skills/market.gap_score/1.1.0"
spec = importlib.util.spec_from_file_location("gap_v110", PACKAGE / "run.py")
gap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gap)
BASE = json.loads((PACKAGE / "evals/cases.jsonl").read_text().splitlines()[0])["input"]


@pytest.mark.asyncio
async def test_all_versioned_evals():
    for line in (PACKAGE / "evals/cases.jsonl").read_text().splitlines():
        case = json.loads(line)
        result = await gap.run(case["input"], None)
        assert all(result[key] == value for key, value in case["expected"].items()), case["name"]


def test_same_area_different_segments_keep_both_results_and_trends():
    payload = copy.deepcopy(BASE)
    for index, area in enumerate(payload["areas"]):
        area["area"] = "same place"
        area["segment"] = ("thin", "hot")[index]
        for role in ("demand", "supply"):
            area[role].insert(0, {"date": "2025-10-01", "value": 10})
    result = gap.score(payload)
    by_segment = result["by_area_segment"]["same place"]
    assert set(by_segment) == {"thin", "hot"}
    assert by_segment["thin"]["gap"] == 87.5
    assert by_segment["hot"]["gap"] == -60
    assert by_segment["thin"]["trend"]["m3"] == 87.5
    assert by_segment["hot"]["trend"]["m3"] == -60
    assert result["top_segment"] == "thin" and result["hot_segment"] == "hot"
    assert len(result["ranked"]) == 2


def test_partial_historical_cohort_is_not_used_for_trends():
    payload = copy.deepcopy(BASE)
    for role in ("demand", "supply"):
        payload["areas"][0][role].insert(0, {"date": "2025-10-01", "value": 10})
    result = gap.score(payload)
    assert all(row["trend"]["m3"] is None for row in result["ranked"])


@pytest.mark.parametrize('field', ['competitors', 'reachability', 'targets', 'reachable', 'size', 'fit'])
def test_negative_metadata_rejected(field):
    payload = copy.deepcopy(BASE)
    payload["areas"][0][field] = -1
    assert gap.score(payload)["reason"] == "negative values are not allowed"


@pytest.mark.parametrize('value', [float('inf'), float('nan'), True, 'not a number'])
def test_nonfinite_or_wrong_values_rejected(value):
    payload = copy.deepcopy(BASE)
    payload["areas"][0]["supply"][0]["value"] = value
    assert gap.score(payload)["status"] == "rejected"


def test_population_absent_for_everyone_is_valid():
    payload = copy.deepcopy(BASE)
    for area in payload["areas"]:
        area.pop("population")
    assert all(not row["per_capita"] for row in gap.score(payload)["ranked"])


def test_existing_parity_fields_unchanged():
    spec = importlib.util.spec_from_file_location("old_gap", PACKAGE.parent / "1.0.0/run.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    expected = old._load().gap_score(BASE)
    result = gap.score(BASE)
    assert all(result[key] == value for key, value in expected.items())
