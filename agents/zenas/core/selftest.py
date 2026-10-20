"""Held-out decided cases, and LegalBench on the US box only.

Twenty percent of decided cases, by a stable hash, are never reused and never
written as training pairs. A self-test sees only the facts the court stated.
US runs see only US cases. SA runs see only SA cases.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from agents.zenas.core.engine import cite_check, code_finding, compose_memo, decide_without_model
from agents.zenas.core.legalbench import legalbench_scores
from agents.zenas.core.scope_rules import classify

_PLATFORM = "00000000-0000-0000-0000-000000000001"


def is_holdout(stable_id: str) -> bool:
    """One stable fifth. The same id is held out on every run."""
    digest = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 5 == 0


def box_jurisdiction(region: str) -> str:
    return "za" if region == "za" else "us"


def _facts_only(row: dict[str, Any]) -> dict[str, Any]:
    """The court's stated facts. Not the judgment, the findings, or the outcome."""
    pattern = row.get("fact_pattern") or {}
    features = dict(pattern.get("features") or {})
    facts = str(pattern.get("facts") or "")
    question = str(pattern.get("question") or "")
    return {"features": features, "facts": facts, "question": question}


def _predicted_outcome(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "unclear"
    states = [str(item.get("finding") or "") for item in findings]
    if all(item == "met" for item in states):
        return "met"
    if any(item == "not_met" for item in states):
        return "not_met"
    return "unclear"


def _court_outcome(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text in {"met", "not_met", "unclear"}:
        return text
    if text in {"enforced", "affirmed", "granted", "liable"}:
        return "met"
    if text in {"dismissed", "reversed", "denied"}:
        return "not_met"
    return text


_ERROR_REASONS = frozenset({"no rule card", "criminal law is refused", "the ladder did not run"})


def _error(case: dict[str, Any], reason: str) -> dict[str, Any]:
    """The ladder did not produce a score. The reason is a fixed phrase."""
    clean = reason if reason in _ERROR_REASONS else "the ladder did not run"
    return {
        "pool_doc_id": case.get("pool_doc_id"),
        "area": str(case.get("area") or ""),
        "jurisdiction": str(case.get("jurisdiction") or ""),
        "outcome_hit": False,
        "element_agreement": 0.0,
        "citations_valid": False,
        "cost_usd": 0.0,
        "error": True,
        "reason": clean,
    }


def _element_agreement(court: list[dict[str, Any]], ours: list[dict[str, Any]]) -> float:
    if not court:
        return 0.0
    by_id = {str(item.get("element_id") or ""): str(item.get("finding") or "") for item in ours}
    same = 0
    for item in court:
        if by_id.get(str(item.get("element_id") or "")) == str(item.get("finding") or ""):
            same += 1
    return 100.0 * same / len(court)


def _passages(card: dict[str, Any]) -> list[dict[str, Any]]:
    passages = []
    for element in card.get("elements") or []:
        quote = str(element.get("quote") or "")
        citation = str(element.get("citation") or "")
        if quote and citation:
            passages.append(
                {
                    "citation": citation,
                    "text": quote,
                    "doc_id": element.get("doc_id") or "",
                    "status": "in_force",
                }
            )
    return passages


async def _one(ladder: Any, case: dict[str, Any], *, region: str) -> dict[str, Any]:
    given = _facts_only(case)
    scope = classify(given["facts"] or given["question"], box_jurisdiction(region))
    if scope.get("criminal"):
        return _error(case, "criminal law is refused")
    card = None
    for card_id in case.get("rule_card_ids") or []:
        loaded = await ladder.get_rule_card(str(card_id), region=region, tenant_id=_PLATFORM)
        if loaded is not None and str(loaded.get("status") or "") != "stale":
            card = loaded
            break
    if card is None:
        return _error(case, "no rule card")
    # Reuse reads visible_worked, which already drops holdout rows, so this case
    # cannot be matched against itself. The code table decides the elements.
    try:
        return await _score(card, case, given)
    except Exception:
        return _error(case, "the ladder did not run")


async def _score(card: dict[str, Any], case: dict[str, Any], given: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    cost = 0.0
    for element in card.get("elements") or []:
        decided = code_finding(str(element.get("id") or ""), given["features"], card.get("decision_table") or [])
        if decided is None:
            found = decide_without_model(
                element,
                given["features"],
                card.get("decision_table") or [],
                [],
                tenant_id=_PLATFORM,
            )
        else:
            found = {
                "element_id": str(element.get("id") or ""),
                "finding": decided,
                "support": "",
                "missing": "",
                "rung": "code",
                "cost_usd": 0,
            }
        if found is None:
            found = {
                "element_id": str(element.get("id") or ""),
                "finding": "unclear",
                "support": "",
                "missing": "no code path",
                "rung": "code",
                "cost_usd": 0,
            }
        findings.append(found)
        cost += float(found.get("cost_usd") or 0)
    memo = compose_memo(card, findings)
    statements = [
        {"citation": element.get("citation"), "quote": element.get("quote")}
        for element in card.get("elements") or []
        if element.get("citation")
    ]
    checked = cite_check(statements, _passages(card)) if statements else {"passed": False}
    predicted = _predicted_outcome(findings)
    court = _court_outcome(str(case.get("outcome") or ""))
    return {
        "pool_doc_id": case.get("pool_doc_id"),
        "area": str(case.get("area") or ""),
        "jurisdiction": str(case.get("jurisdiction") or ""),
        "outcome_hit": predicted == court,
        "element_agreement": _element_agreement(list(case.get("element_findings") or []), findings),
        "citations_valid": bool(checked.get("passed")),
        "cost_usd": cost,
        "memo_citations": memo.get("citations") or [],
        "error": False,
        "reason": "",
    }


def _group(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    errors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("error"):
            errors[str(row.get("reason") or "the ladder did not run")].append(row)
            continue
        buckets[(row["area"], row["jurisdiction"])].append(row)
    grouped = []
    for (area, jurisdiction), items in sorted(buckets.items()):
        count = len(items)
        grouped.append(
            {
                "area": area,
                "jurisdiction": jurisdiction,
                "cases": count,
                "outcome_agreement": round(100.0 * sum(1 for item in items if item["outcome_hit"]) / count, 2),
                "element_agreement": round(sum(item["element_agreement"] for item in items) / count, 2),
                "citations_valid": round(100.0 * sum(1 for item in items if item["citations_valid"]) / count, 2),
                "cost_per_case": round(sum(item["cost_usd"] for item in items) / count, 6),
                "case_ids": [str(item.get("pool_doc_id") or "") for item in items],
                "error": False,
                "reason": "",
            }
        )
    for reason, items in sorted(errors.items()):
        grouped.append(
            {
                "area": "",
                "jurisdiction": str(items[0].get("jurisdiction") or ""),
                "cases": len(items),
                "outcome_agreement": 0,
                "element_agreement": 0,
                "citations_valid": 0,
                "cost_per_case": 0,
                "case_ids": [str(item.get("pool_doc_id") or "") for item in items],
                "error": True,
                "reason": reason,
            }
        )
    return grouped


# One real case, copied from the saved Grancy judgment. The nightly traps are not this case.
_MADE_UP_LIBRARY = (
    {
        "name": "Grancy Property Limited and Another v Gihwala and Others",
        "citation": "[2026] ZACC 40",
        "quote": "Leave to appeal is refused.",
        "text": (
            "On appeal from the Supreme Court of Appeal (hearing an appeal from the High Court "
            "of South Africa, Western Cape Division, Cape Town): 1. Leave to appeal is refused."
        ),
    },
)


def made_up_questions() -> list[dict[str, str]]:
    """Fifty questions. Forty name cases that are not in the library."""
    rows: list[dict[str, str]] = []
    codes = ("ZASCA", "ZAGPJHC", "ZAWCHC", "ZACC", "ZAFSHC")
    for index in range(40):
        name = f"Fictional Party {index} v Nobody {index}"
        citation = f"[2099] {codes[index % len(codes)]} {9000 + index}"
        rows.append(
            {
                "kind": "trap",
                "question": f"What did {name} {citation} decide?",
                "name": name,
                "citation": citation,
            }
        )
    real = _MADE_UP_LIBRARY[0]
    for index in range(10):
        rows.append(
            {
                "kind": "real",
                "question": f"Question {index}: what did {real['name']} {real['citation']} hold?",
                "name": real["name"],
                "citation": real["citation"],
            }
        )
    return rows


def answer_from_library(question: str) -> str:
    """Answer only from the library. A name that is not there is left out."""
    from agents.zenas.core.engine import cite_check
    from agents.zenas.core.precedent import drop_unverified_cases, named_cases

    known: list[str] = []
    for item in _MADE_UP_LIBRARY:
        known.extend((item["name"], item["citation"], item["text"], item["quote"]))
    library = " \n ".join(known)
    named = named_cases(question or "")
    if any(name.lower() not in library.lower() for name in named):
        return drop_unverified_cases(question, known)
    hit = _MADE_UP_LIBRARY[0]
    answer = f"{hit['name']} {hit['citation']}. {hit['quote']}"
    checked = cite_check(
        [{"citation": hit["citation"], "quote": hit["quote"]}],
        [{"citation": hit["citation"], "text": hit["text"], "status": "in_force"}],
    )
    if not checked.get("passed"):
        return f"I could not verify {hit['name']}, so I have left it out. I cannot find it."
    return answer


def run_made_up_test() -> dict[str, Any]:
    """The nightly gate. Every question is code. No model is called."""
    questions = made_up_questions()
    passed = 0
    for item in questions:
        answer = answer_from_library(item["question"])
        if item["kind"] == "trap":
            ok = (
                "cannot find" in answer.lower()
                and "I could not verify" in answer
                and "I have left it out" in answer
            )
        else:
            ok = "cannot find" not in answer.lower() and item["citation"] in answer and _MADE_UP_LIBRARY[0]["quote"] in answer
        if ok:
            passed += 1
    asked = len(questions)
    return {
        "asked": asked,
        "passed": passed,
        "skills_may_be_approved": passed == asked == 50,
    }


def zenas_skills_may_be_approved() -> bool:
    """No Zenas skill is ready to approve unless the made-up-case test is perfect."""
    return bool(run_made_up_test()["skills_may_be_approved"])


def _made_up_row(box: str, jurisdiction: str) -> dict[str, Any]:
    result = run_made_up_test()
    asked = int(result["asked"])
    passed = int(result["passed"])
    score = round(100.0 * passed / asked, 2) if asked else 0
    approved = bool(result["skills_may_be_approved"])
    standing = "Zenas skills may be approved." if approved else "Zenas skills may not be approved."
    return {
        "region": box,
        "kind": "holdout",
        "area": f"Made-up cases: {passed} of {asked}. {standing}",
        "jurisdiction": jurisdiction,
        "cases": asked,
        "outcome_agreement": score,
        "element_agreement": score,
        "citations_valid": score,
        "cost_per_case": 0,
        "detail": {
            "case_ids": [],
            "made_up": True,
            "asked": asked,
            "passed": passed,
            "skills_may_be_approved": approved,
        },
    }


async def run_selftest(ladder: Any, *, region: str) -> dict[str, Any]:
    """Score this box's held-out cases. The other region's cases are ignored."""
    box = "za" if region == "za" else "us-east"
    jurisdiction = box_jurisdiction(box)
    raw = await ladder.holdout_cases(region=box, jurisdiction=jurisdiction)
    cases = [
        row
        for row in raw
        if row.get("region") == box and row.get("jurisdiction") == jurisdiction and row.get("holdout")
    ]
    scored = [await _one(ladder, row, region=box) for row in cases]
    groups = _group(scored) if scored else []
    saved = []
    if not groups:
        row = await ladder.add_selftest(
            {
                "region": box,
                "kind": "holdout",
                "area": "",
                "jurisdiction": jurisdiction,
                "cases": 0,
                "outcome_agreement": 0,
                "element_agreement": 0,
                "citations_valid": 0,
                "cost_per_case": 0,
                "detail": {"case_ids": [], "baseline": False},
            }
        )
        saved.append(row)
    for group in groups:
        detail: dict[str, Any] = {"case_ids": group["case_ids"]}
        if group.get("error"):
            detail["error"] = True
            detail["reason"] = group["reason"]
        row = await ladder.add_selftest(
            {
                "region": box,
                "kind": "holdout",
                "area": group["area"],
                "jurisdiction": group["jurisdiction"],
                "cases": group["cases"],
                "outcome_agreement": group["outcome_agreement"],
                "element_agreement": group["element_agreement"],
                "citations_valid": group["citations_valid"],
                "cost_per_case": group["cost_per_case"],
                "detail": detail,
            }
        )
        saved.append(row)
    if box == "us-east":
        for item in legalbench_scores():
            saved.append(await ladder.add_selftest({"region": box, **item}))
    saved.append(await ladder.add_selftest(_made_up_row(box, jurisdiction)))
    return {
        "ok": True,
        "region": box,
        "runs": [_public_run(row) for row in saved],
    }


def _public_run(row: dict[str, Any]) -> dict[str, Any]:
    """Scores only. No judgment text, no matter, no document body.

    A LegalBench row is a code baseline. The label is on the response so a
    reader does not take the percentage for a model score.
    """
    detail = row.get("detail") or {}
    kind = str(row.get("kind") or "")
    error = bool(detail.get("error"))
    reason = str(detail.get("reason") or "") if error else ""
    if error and reason not in _ERROR_REASONS:
        reason = "the ladder did not run"
    published: dict[str, Any] = {
        "id": row.get("id"),
        "region": row.get("region"),
        "kind": kind,
        "area": row.get("area") or "",
        "jurisdiction": row.get("jurisdiction") or "",
        "cases": int(row.get("cases") or 0),
        "outcome_agreement": float(row.get("outcome_agreement") or 0),
        "element_agreement": float(row.get("element_agreement") or 0),
        "citations_valid": float(row.get("citations_valid") or 0),
        "cost_per_case": float(row.get("cost_per_case") or 0),
        "case_ids": [str(item) for item in (detail.get("case_ids") or [])],
        "set": str(detail.get("set") or ""),
        "scored_by": "",
        "error": error,
        "reason": reason,
    }
    if error:
        published["label"] = "error"
    if kind == "legalbench":
        published["scored_by"] = "code baseline"
        published["label"] = "LegalBench code baseline"
        published["model"] = False
    return published


async def list_scores(ladder: Any, *, region: str) -> dict[str, Any]:
    box = "za" if region == "za" else "us-east"
    rows = await ladder.list_selftest(region=box)
    return {"ok": True, "region": box, "runs": [_public_run(row) for row in rows]}


async def run_scheduled(conn: Any, *, region: str) -> None:
    """Nightly, after the pool load. A failure here does not change the pool report."""
    try:
        import os

        os.nice(19)
    except OSError:
        pass
    from agents.zenas.core.ladder_store import PgLadder
    from agents.zenas.core.store import PgStore

    class _Hold:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        async def __aenter__(self) -> Any:
            return self.inner

        async def __aexit__(self, *_exc: object) -> bool:
            return False

    class _Pool:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        def acquire(self) -> _Hold:
            return _Hold(self.inner)

    pool = conn if hasattr(conn, "acquire") else _Pool(conn)
    store = PgStore(pool)
    try:
        await store.apply_schema()
    except Exception:
        return
    ladder = PgLadder(pool)
    await run_selftest(ladder, region=region)
