"""The summary model cannot supply or overwrite lookup results."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tank/skills/market.research/1.1.0"
spec = importlib.util.spec_from_file_location("market_research_code", PACKAGE / "run.py")
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


class Summary:
    def __init__(self):
        self.calls = []

    async def model(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return "A summary; model guesses must not change structured numbers."


@pytest.mark.asyncio
async def test_gold_results():
    for line in (PACKAGE / "evals/cases.jsonl").read_text().splitlines():
        case = json.loads(line)
        ctx = Summary()
        result = await research.run(case["input"], ctx)
        for key, expected in case["expected"].items():
            assert result[key] == expected, case["name"]
        assert not ctx.calls


@pytest.mark.asyncio
async def test_series_references_and_summary_only():
    ctx = Summary()
    def series(sid, value):
        return dict(adapter="csv", series_id=sid, text=f"date,value\n2025-01-01,{value}\n", fetched_at="2025-01-02")
    payload = dict(question="Where is demand strongest?", series=[series("d", 100), series("s", 10)],
                   areas=[dict(area="one", demand_series_id="d", supply_series_id="s")])
    expected = research.prepare(payload)
    result = await research.run(payload, ctx)
    assert len(ctx.calls) == 1
    assert ctx.calls[0][1] == dict(task_type="market.research", max_tokens=600)
    sent = json.loads(ctx.calls[0][0][1]["content"])
    assert sent["evidence"]["gaps"] == expected["gaps"]
    assert "points" not in sent["evidence"]["series"][0]
    for key in ("gaps", "series", "citations"):
        assert result[key] == expected[key]
    payload["areas"][0]["supply_series_id"] = "missing"
    with pytest.raises(ValueError, match="missing"):
        await research.run(payload, ctx)
    assert len(ctx.calls) == 1


@pytest.mark.asyncio
async def test_no_sources_and_duplicate_ids_do_not_call_model():
    ctx = Summary()
    result = await research.run({"question": "Invent an answer"}, ctx)
    assert result["answer"] == "no sources yet" and not ctx.calls
    row = dict(adapter="csv", series_id="x", text="date,value\n2025-01-01,2\n")
    with pytest.raises(ValueError, match="unique"):
        await research.run(dict(series=[row, row]), ctx)
    assert not ctx.calls


def test_fred_raw_observations_are_not_returned():
    result = research.prepare(dict(series=[dict(adapter="fred", series_id="rate", observations=[dict(date="2025-01-01", value="5")])]))
    assert result["series"] == []


@pytest.mark.asyncio
async def test_legacy_citation_gold_unchanged():
    old_spec = importlib.util.spec_from_file_location("old_research", PACKAGE.parent / "1.0.0/run.py")
    old = importlib.util.module_from_spec(old_spec)
    old_spec.loader.exec_module(old)
    for line in (PACKAGE.parent / "1.0.0/evals/cases.jsonl").read_text().splitlines():
        payload = json.loads(line)["input"]
        before = await old.run(payload, Summary())
        after = await research.run(payload, Summary())
        assert all(after[k] == v for k, v in before.items())
