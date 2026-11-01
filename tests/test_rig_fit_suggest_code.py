"""rig.fit_suggest 1.1.0 answers from fitment data. The model only writes a sentence.

1.0.0 is unchanged and still unapproved-output. This version is not approved.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

import skala  # noqa: E402
from rigbox.catalogue import families_from
from rig_fixture_loader import load_folder  # noqa: E402
from rigbox.logic import approved as room_approved  # noqa: E402

PACKAGE = ROOT / "tank" / "skills" / "rig.fit_suggest" / "1.1.0"
CATALOGUES = ROOT / "tests" / "fixtures" / "rig_catalogues"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


suggest = _load(PACKAGE / "run.py", "rig_fit_suggest_11")
fit_code = _load(PACKAGE / "code.py", "rig_fit_suggest_code_11")
previous = _load(ROOT / "tank" / "skills" / "rig.fit_suggest" / "1.0.0" / "ground.py", "rig_fit_suggest_10")


class Boom:
    async def model(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("model")


class Recorder:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[list, str, int | None]] = []

    async def model(self, messages: list, task_type: str, max_tokens: int | None = None) -> str:
        self.calls.append((messages, task_type, max_tokens))
        return self.text


def _cases() -> list[dict]:
    return [json.loads(line) for line in (PACKAGE / "evals" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.asyncio
async def test_eval_cases_pass_without_calling_the_model() -> None:
    meta = (PACKAGE / "skill.yaml").read_text(encoding="utf-8")
    assert "version: 1.1.0" in meta
    assert "\nstate:" not in meta
    for case in _cases():
        output = await suggest.run(case["input"], Boom())
        ok, why = skala.score_case(case["expected"], output, case["tolerance"])
        assert ok, (case["name"], why)


@pytest.mark.asyncio
async def test_model_writes_one_sentence_and_cannot_add_a_part() -> None:
    payload = {
        "part_sku": "SHADE",
        "products": [
            {"sku": "LAMP", "family": "DESK", "active": True},
            {"sku": "SHADE", "active": True},
            {"sku": "BULB", "active": True},
        ],
        "fits": [
            {"part_sku": "SHADE", "fits_sku": "LAMP", "rule": {"neck": "e27"}},
            {"part_sku": "BULB", "fits_sku": "LAMP", "rule": {}},
        ],
    }
    ctx = Recorder("The shade fits the lamp. Also add the bulb, and a second sentence.")
    output = await suggest.run(payload, ctx)
    assert output["fits"] == [
        {"part_sku": "SHADE", "fits_sku": "LAMP", "fits_family": None, "rule": {"neck": "e27"}}
    ]
    assert output["explanation"] == "The shade fits the lamp."
    assert len(ctx.calls) == 1
    assert ctx.calls[0][1] == "rig.fit_suggest"
    assert ctx.calls[0][2] == 80
    sent = json.loads(ctx.calls[0][0][1]["content"])
    assert sent["fits"] == output["fits"]
    assert "BULB" not in sent["fits"][0]["part_sku"]
    empty = Recorder("Invent a fit.")
    assert await suggest.run({"products": payload["products"], "fits": []}, empty) == {
        "fits": [],
        "explanation": "",
    }
    assert empty.calls == []


def _catalogue_gold() -> list[dict]:
    """The same label as the room gold route: one part's own list, exact then family."""
    rows: list[dict] = []
    for path in sorted(item for item in CATALOGUES.iterdir() if item.is_dir()):
        loaded = load_folder(path)
        if loaded["products"]["rejected"] or loaded["fits"]["rejected"]:
            continue
        products = [row for row in loaded["products"]["rows"] if row.get("active")]
        known = {str(row["sku"]) for row in products}
        families = families_from(products)
        labelled: list[dict] = []
        for fit in loaded["fits"]["rows"]:
            part = str(fit["part_sku"])
            fits_sku = fit.get("fits_sku") or None
            fits_family = fit.get("fits_family") or None
            if part not in known or bool(fits_sku) == bool(fits_family):
                continue
            if fits_sku and str(fits_sku) not in known:
                continue
            if fits_family and str(fits_family) not in families:
                continue
            labelled.append(
                {
                    "part_sku": part,
                    "fits_sku": str(fits_sku) if fits_sku else None,
                    "fits_family": str(fits_family) if fits_family else None,
                    "rule": dict(fit.get("rule") or {}),
                }
            )
        slim = [
            {
                "sku": str(row["sku"]),
                "id": str(row["sku"]),
                "name": row["name"],
                "family": row.get("family") or "",
                "active": True,
                "attributes": row.get("attributes") or {},
            }
            for row in products
        ]
        parts = sorted({row["part_sku"] for row in labelled})
        for part in parts:
            own = [row for row in labelled if row["part_sku"] == part]
            exact = sorted((row for row in own if row["fits_sku"]), key=lambda row: row["fits_sku"] or "")
            family = sorted((row for row in own if row["fits_family"]), key=lambda row: row["fits_family"] or "")
            rows.append(
                {
                    "label_source": f"{loaded['slug']}:{part}",
                    "input": {"part_sku": part, "products": slim, "fits": labelled, "model_text": "Listed in the catalogue."},
                    "expected": exact + family,
                }
            )
    return rows


def _identity(rows: list[dict]) -> set[tuple[str, str | None, str | None]]:
    return {(str(row["part_sku"]), row.get("fits_sku"), row.get("fits_family")) for row in rows}


def _score(expected: list[dict], got: list[dict]) -> float:
    want = _identity(expected)
    have = _identity(got)
    if not want and not have:
        return 1.0
    if not want or not have:
        return 0.0
    return len(want & have) / len(want | have)


def _invented(products: list[dict], expected: list[dict]) -> dict | None:
    skus = [str(row["sku"]) for row in products]
    have = {(row["part_sku"], row["fits_sku"]) for row in expected if row.get("fits_sku")}
    for part in skus:
        for target in skus:
            if part != target and (part, target) not in have:
                return {"part_sku": part, "fits_sku": target, "rule": {}, "confidence": 0.9, "approved": True}
    return None


@pytest.mark.asyncio
async def test_code_matches_or_beats_the_model_on_catalogue_lists() -> None:
    gold = _catalogue_gold()
    assert gold
    code_scores: list[float] = []
    model_scores: list[float] = []
    for row in gold:
        output = await suggest.run(row["input"], Boom())
        assert output["fits"] == row["expected"], row["label_source"]
        assert output["explanation"] == "Listed in the catalogue."
        code_scores.append(_score(row["expected"], output["fits"]))
        extra = _invented(row["input"]["products"], row["expected"])
        assert extra is not None
        reply = {"fits": [*row["expected"], extra]}
        guessed = previous.fit_suggest({"products": row["input"]["products"]}, json.dumps(reply))
        model_scores.append(_score(row["expected"], guessed["fits"]))
    assert code_scores
    assert all(code == 1.0 for code in code_scores)
    assert all(code >= model for code, model in zip(code_scores, model_scores, strict=True))
    assert any(model < 1.0 for model in model_scores)
    matched = previous.fit_suggest(
        {"products": gold[0]["input"]["products"]},
        json.dumps({"fits": gold[0]["expected"]}),
    )
    assert _score(gold[0]["expected"], matched["fits"]) == 1.0


def test_approval_matches_the_room_and_the_sentence_is_capped() -> None:
    samples = [
        {"source": "suggested", "approved": False},
        {"source": "suggested"},
        {"source": "suggested", "approved": True},
        {"source": "import", "approved": False},
        {"source": "import", "approved": True},
        {},
    ]
    for row in samples:
        assert fit_code._approved(row) is room_approved(row)
    long = "word " * 80
    assert len(fit_code.one_sentence(long)) == 200
    assert fit_code.one_sentence("The shade fits the lamp. " + long) == "The shade fits the lamp."


def test_previous_version_is_untouched() -> None:
    old = ROOT / "tank" / "skills" / "rig.fit_suggest" / "1.0.0"
    assert (old / "ground.py").read_bytes() == (ROOT / "agents" / "rig" / "rigbox" / "ground.py").read_bytes()
    assert "1.1.0" not in (old / "skill.yaml").read_text(encoding="utf-8")
    assert "not approved" in (PACKAGE / "CHANGELOG.md").read_text(encoding="utf-8").lower()
