"""zenas.compose 1.1.0 keeps the template unless the smoothed memo keeps the legal effect.
reason.brief 1.1.0 asks the model to lead with "I recommend". Old cases are copied unchanged."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

import skala

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tank" / "skills"


def _load(skill: str, version: str):
    path = SKILLS / skill / version / "run.py"
    spec = importlib.util.spec_from_file_location(f"{skill}_{version}_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cases(skill: str, version: str) -> list[dict]:
    return [json.loads(line) for line in (SKILLS / skill / version / "evals" / "cases.jsonl").read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("skill", ["zenas.compose", "reason.brief"])
def test_old_cases_are_byte_identical(skill):
    old = (SKILLS / skill / "1.0.1" / "evals" / "cases.jsonl").read_bytes()
    assert (SKILLS / skill / "1.1.0" / "evals" / "cases.jsonl").read_bytes() == old


class _Ctx:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def model(self, messages, task_type: str, **_kwargs):
        self.prompts.append(messages[0]["content"])
        return self.reply


CASE = next(case for case in _cases("zenas.compose", "1.1.0") if case["name"] == "configured model preserves citations and legal effect")
REFERENCE = CASE["properties"]["reference_text"]


@pytest.mark.parametrize(
    "reply, smoothed",
    [
        (REFERENCE, True),
        ("Issue: Can a mutual NDA be relied on?\nRule: The promise is in writing. (8 Del. C. § 101)\nApplication: written: met. form=written\nConclusion: Every element is met on these facts.", True),
        ("Rule: The promise is in writing (8 Del. C. § 101). The NDA is enforceable.\nConclusion: All elements are met.", False),
        ("Rule: The promise is in writing. (8 Del. C. § 101) See also Smith v Jones.\nApplication: written: met.\nConclusion: Every element is met.", False),
        ("Rule: The promise is in writing.\nConclusion: Every element is met.", False),
        ("Rule: The promise is in writing. (8 Del. C. § 101)\nConclusion: Not every element is met.", False),
    ],
)
def test_compose_keeps_the_template_unless_the_legal_effect_is_kept(reply, smoothed):
    run = _load("zenas.compose", "1.1.0").run
    out = asyncio.run(run(json.loads(json.dumps(CASE["input"])), _Ctx(reply)))
    assert out["smoothed"] is smoothed
    ok, why = skala.eval_properties(CASE, out, True)
    assert ok, why


def test_reason_brief_leads_with_a_recommendation_and_still_refuses_empty_input():
    module = _load("reason.brief", "1.1.0")
    ctx = _Ctx("I recommend keeping the supplier.\n- Prices rose 3%.")
    out = asyncio.run(module.run({"text": "Supplier prices rose 3% this quarter."}, ctx))
    assert out["text"].startswith("I recommend")
    assert 'begin with "I recommend"' in ctx.prompts[0]
    assert "Supplier prices rose 3% this quarter." in ctx.prompts[0]
    assert asyncio.run(module.run({"text": "  "}, ctx)) == {"text": "", "error": "empty input"}
