"""Skala: the skills lifecycle (Build Pack v2, "Skala — the skills lifecycle").

A skill is a versioned package on disk:

    skills/<id>/<version>/
        skill.yaml      id, version, agent, rung, task_type, description, schemas, eval_threshold
        run.py          async def run(input: dict, ctx: SkillContext) -> dict
        evals/cases.jsonl   one {"input":…, "expected":…, "tolerance":…} per line
        CHANGELOG.md

Phase 1 registry = this folder (Git) + tank.skills (Postgres).

States: candidate -> staging -> approved -> retired
    candidate  the package exists and parsed
    staging    its evals scored at or above threshold (Skala moves it)
    approved   a human signed off; only approved versions run for clients
    retired    superseded; kept for rollback

Rules enforced here: agents may call `run` on approved versions only (preview runs
are for the owner's own testing and are labelled as such in the ledger); approval
is a separate, human-only call; a new approved version retires the previous one.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import yaml

SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "skills")))

ModelFn = Callable[..., Awaitable[dict[str, Any]]]


# ---------- package on disk ----------

@dataclass
class SkillPackage:
    id: str
    version: str
    agent: str
    rung: int
    task_type: str | None
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    eval_threshold: float
    path: Path
    cases: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


def _load_cases(path: Path) -> list[dict[str, Any]]:
    f = path / "evals" / "cases.jsonl"
    if not f.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(json.loads(line))
    return out


def load_packages(root: Path = SKILLS_DIR) -> dict[tuple[str, str], SkillPackage]:
    """Every skills/<id>/<version>/skill.yaml under root."""
    found: dict[tuple[str, str], SkillPackage] = {}
    if not root.exists():
        return found
    for yaml_path in sorted(root.glob("*/*/skill.yaml")):
        pkg_dir = yaml_path.parent
        try:
            pkg = _parse_package(yaml_path, pkg_dir)
        except Exception as exc:  # noqa: BLE001 — one broken package must never stop Tank
            log.error("skala: skipping %s: %s", yaml_path, exc)
            continue
        found[(pkg.id, pkg.version)] = pkg
    return found


log = logging.getLogger("tank.skala")


def _parse_package(yaml_path: Path, pkg_dir: Path) -> SkillPackage:
    meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if True:
        pkg = SkillPackage(
            id=str(meta["id"]),
            version=str(meta["version"]),
            agent=str(meta.get("agent", "tier0")),
            rung=int(meta.get("rung", 1)),
            task_type=meta.get("task_type"),
            description=str(meta.get("description", "")).strip(),
            input_schema=meta.get("input", {}) or {},
            output_schema=meta.get("output", {}) or {},
            eval_threshold=float(meta.get("eval_threshold", 0.95)),
            path=pkg_dir,
            cases=_load_cases(pkg_dir),
        )
        if pkg_dir.parent.name != pkg.id or pkg_dir.name != pkg.version:
            raise ValueError(f"folder is {pkg_dir.parent.name}/{pkg_dir.name} but skill.yaml says {pkg.ref}")
        return pkg


_run_cache: dict[tuple[str, str], Callable[..., Awaitable[dict[str, Any]]]] = {}


def _import_run(pkg: SkillPackage) -> Callable[[dict[str, Any], "SkillContext"], Awaitable[dict[str, Any]]]:
    cached = _run_cache.get((pkg.id, pkg.version))
    if cached is not None:
        return cached
    run = _import_run_uncached(pkg)
    _run_cache[(pkg.id, pkg.version)] = run
    return run


def _import_run_uncached(pkg: SkillPackage) -> Callable[[dict[str, Any], "SkillContext"], Awaitable[dict[str, Any]]]:
    spec = importlib.util.spec_from_file_location(f"skill_{pkg.id}_{pkg.version}".replace(".", "_").replace("-", "_"), pkg.path / "run.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    run = getattr(mod, "run", None)
    if run is None:
        raise ValueError(f"{pkg.ref}: run.py has no run()")
    return run


# ---------- what a skill may touch ----------

@dataclass
class SkillContext:
    """Everything a skill is allowed to reach. Models only through Tank (so the
    call is policy-routed and in the ledger, tagged with this skill); the web
    through a shared HTTP client with a sane timeout and user agent."""

    tenant_id: uuid.UUID
    skill_ref: str
    agent: str
    task_id: uuid.UUID | None
    _model: ModelFn
    http: httpx.AsyncClient
    env: dict[str, str] = field(default_factory=dict)   # optional provider keys a skill may use
    calls: int = 0
    cost_usd: float = 0.0

    async def model(self, messages: list[dict[str, str]], task_type: str, max_tokens: int | None = None) -> str:
        res = await self._model(
            tenant_id=self.tenant_id, agent=self.agent, task_type=task_type, skill=self.skill_ref,
            messages=messages, task_id=self.task_id, max_tokens=max_tokens,
        )
        self.calls += 1
        self.cost_usd += float(res.get("cost_usd") or 0)
        return str(res.get("content") or "")


# ---------- running ----------

async def run_skill(pkg: SkillPackage, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
    run = _import_run(pkg)
    started = time.perf_counter()
    out = await run(payload, ctx)
    if not isinstance(out, dict):
        raise ValueError(f"{pkg.ref}: run() must return a dict")
    out.setdefault("_skill", pkg.ref)
    out["_ms"] = int((time.perf_counter() - started) * 1000)
    return out


# ---------- scoring evals ----------

def _norm(v: Any) -> str:
    return " ".join(str(v).lower().split())


def score_case(expected: dict[str, Any], output: dict[str, Any], tolerance: str) -> tuple[bool, str]:
    """exact: every expected key equal. contains: expected text appears in output text (per key).
    fields: like exact but lists compared as sets. Returns (passed, reason)."""
    for key, want in expected.items():
        got = output.get(key)
        if tolerance == "contains":
            if _norm(want) not in _norm(got):
                return False, f"{key}: {want!r} not in {str(got)[:80]!r}"
        elif tolerance == "fields":
            if isinstance(want, list) and isinstance(got, list):
                if set(map(_norm, want)) != set(map(_norm, got)):
                    return False, f"{key}: {want!r} != {got!r}"
            elif _norm(want) != _norm(got):
                return False, f"{key}: {want!r} != {got!r}"
        else:  # exact
            if want != got:
                return False, f"{key}: {want!r} != {got!r}"
    return True, "ok"


def zenas_approval_reason(skill_id: str, area: str | None) -> str | None:
    """Why a zenas.* skill cannot be approved. None means this box's gate passed.

    The latest made-up-case row must be 50 of 50 through answer_question.
    Any other skill is not this gate.
    """
    if not str(skill_id or "").startswith("zenas."):
        return None
    text = " ".join(str(area or "").split())
    if text.startswith("Made-up cases: 50 of 50.") and "path: answer_question" in text:
        return None
    if not text or "not run" in text:
        return (
            "This Zenas skill stays unapproved. The made-up-case test has not run "
            "on this box through answer_question."
        )
    if "path: answer_question" not in text:
        return (
            "This Zenas skill stays unapproved. The latest made-up-case test on this box "
            "did not run through answer_question."
        )
    return (
        "This Zenas skill stays unapproved. The latest made-up-case test on this box is "
        f"{text.removeprefix('Made-up cases: ').split('. path:')[0]}, not 50 of 50 through answer_question."
    )


_MADE_UP_AREA_SQL = """
SELECT area
FROM agent_zenas.selftest_runs
WHERE region = $1
  AND area LIKE 'Made-up cases:%'
ORDER BY created_at DESC
LIMIT 1
""".strip()


async def zenas_approval_refusal(conn: Any, skill_id: str, *, region: str) -> str | None:
    """The sentence Skala shows when this box has not passed the made-up-case test."""
    if not str(skill_id or "").startswith("zenas."):
        return None
    box = "za" if str(region or "").strip().lower() == "za" else "us-east"
    area = ""
    if conn is not None and hasattr(conn, "fetchrow"):
        row = await conn.fetchrow(_MADE_UP_AREA_SQL, box)
        if row is not None:
            try:
                area = str(row["area"] or "")
            except (KeyError, IndexError, TypeError):
                area = ""
    return zenas_approval_reason(skill_id, area)


def eval_properties(case: dict[str, Any], output: dict[str, Any], model_configured: bool) -> tuple[bool, str]:
    from collections import Counter
    import re

    properties = case.get("properties")
    if not properties:
        return True, "ok"
    text = str(output.get("text") or "")
    reference = properties.get("reference_text", case["input"].get("text", ""))
    citations = properties.get("citations", case["input"].get("citations", []))
    if any(_norm(citation) not in {_norm(allowed) for allowed in citations}
           for citation in output.get("citations", [])):
        return False, "new citation"
    if not text.strip() or not reference.strip():
        return False, "legal wording needs text and a reference"
    for citation in citations:
        if _norm(citation) not in _norm(text):
            return False, "original citation missing"
    stripped = text
    for citation in sorted(citations, key=len, reverse=True):
        stripped = re.sub(re.escape(citation), "", stripped, flags=re.I)
    if re.search(r"§|\b(?:section|article|rule)\s+\d|\[\d{4}\]|\b\w+\s+v\.?\s+\w+|\d+\s+(?:F\.|U\.S\.|Del\.)", stripped, re.I):
        return False, "new citation"
    def effect(value: str) -> tuple:
        value = re.sub(r"(?m)^Issue:.*$", "", value)
        folded = _norm(value)
        folded = re.sub(r"\b(?:can be enforced|is enforceable)\b", "enforceable", folded)
        folded = re.sub(r"\b(?:shall|is required to|has to)\b", "must", folded)
        folded = re.sub(r"\b(?:may|is permitted to)\b", "can", folded)
        markers = Counter(re.findall(
            r"\b(?:not|never|must|can|enforceable|unenforceable|met|unclear|liable|unless|except|only|before|after|within)\b|\d+",
            folded,
        ))
        if "met" in markers:
            markers["met"] = 1
        return tuple(sorted(markers.items()))
    if effect(reference) != effect(text):
        return False, "legal effect changed"
    if output.get("smoothed") and not model_configured:
        return False, "smoothed without a configured model"
    return True, "ok"


async def run_evals(pkg: SkillPackage, make_ctx: Callable[[], SkillContext],
                    execute: Callable[..., Awaitable[dict[str, Any]]] | None = None) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    passed = 0
    cost = 0.0
    for i, case in enumerate(pkg.cases):
        ctx = make_ctx()
        if "model" in case:
            from dataclasses import replace

            async def saved_model(**_kwargs: Any) -> dict[str, Any]:
                return {"content": case["model"], "cost_usd": 0}

            ctx = replace(ctx, _model=saved_model)
        goal = case.get("expected", {})
        try:
            out = await (execute or run_skill)(pkg, case["input"], ctx)
            ok, why = score_case(goal, out, case.get("tolerance", "exact"))
            if case.get("expected_error"):
                ok, why = False, "expected refusal exception was not raised"
            if ok:
                configured = case.get("model_configured", "model" in case or bool(pkg.task_type))
                ok, why = eval_properties(case, out, configured and getattr(ctx, "calls", 0) > 0)
        except Exception as exc:  # noqa: BLE001 — an exception is a failed case, recorded
            ok, why, out = False, f"error: {exc}", {}
            expected_error = case.get("expected_error") or {}
            if (case.get("must_refuse") and type(exc).__name__ == expected_error.get("type")
                    and str(exc) == expected_error.get("message")):
                ok, why = True, "expected refusal"
        cost += ctx.cost_usd
        passed += int(ok)
        details.append({
            "case": i,
            "name": case.get("name"),
            "passed": ok,
            "why": why,
            "goal": goal,
            "result": out,
        })
    total = len(pkg.cases)
    distinct = {json.dumps(case["input"], sort_keys=True) + json.dumps(case.get("model"), sort_keys=True)
                for case in pkg.cases}
    negative_results = [detail["passed"] for case, detail in zip(pkg.cases, details)
                        if case.get("must_refuse") is True and (case.get("expected") or case.get("expected_error"))]
    negative_passed = bool(negative_results) and all(negative_results)
    return {
        "skill": pkg.ref,
        "passed": passed,
        "total": total,
        "score": round(passed / total, 4) if total else 0.0,
        "threshold": pkg.eval_threshold,
        "eligible": len(distinct) >= 5 and negative_passed,
        "evidence_reason": ("ok" if len(distinct) >= 5 and negative_passed else
                            "At least five distinct cases and passing refusal or abstention evidence are required."),
        "cost_usd": round(cost, 6),
        "details": details,
    }
