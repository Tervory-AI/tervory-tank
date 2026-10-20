import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "tank/skills/zenas.deadlines/1.2.0"
spec = importlib.util.spec_from_file_location("service_deadlines", SKILL / "run.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.asyncio
async def test_service_date_controls_sa_even_when_order_date_is_earlier():
    result = await module.run({
        "jurisdiction": "za", "service_date": "2026-04-24",
        "trigger": "2026-04-01", "order_date": "2026-04-01",
        "kind": "notice_of_intention_to_defend",
    }, None)
    assert result["deadline"] == "2026-05-12"
    assert result["service_date"] == result["trigger"] == "2026-04-24"
    assert "sheriff's service date" in result["steps"][0]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("service_date", [None, "", "not a date", "2026-02-30"])
async def test_missing_or_invalid_service_never_uses_order(service_date):
    result = await module.run({
        "jurisdiction": "za", "service_date": service_date, "trigger": "2026-04-24", "days": 10,
    }, None)
    assert not result["ok"]
    assert "service_date" in result["reason"]


@pytest.mark.asyncio
async def test_version_evals():
    for line in (SKILL / "evals/cases.jsonl").read_text().splitlines():
        case = json.loads(line)
        result = await module.run(case["input"], None)
        for key, value in case["expected"].items():
            assert result[key] == value, case["name"]
