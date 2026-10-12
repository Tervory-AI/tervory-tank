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


def _import_run(pkg: SkillPackage) -> Callable[[dict[str, Any], "SkillContext"], Awaitable[dict[str, Any]]]:
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


async def run_evals(pkg: SkillPackage, make_ctx: Callable[[], SkillContext]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    passed = 0
    cost = 0.0
    for i, case in enumerate(pkg.cases):
        ctx = make_ctx()
        try:
            out = await run_skill(pkg, case["input"], ctx)
            ok, why = score_case(case.get("expected", {}), out, case.get("tolerance", "exact"))
        except Exception as exc:  # noqa: BLE001 — an exception is a failed case, recorded
            ok, why, out = False, f"error: {exc}", {}
        cost += ctx.cost_usd
        passed += int(ok)
        details.append({"case": i, "name": case.get("name"), "passed": ok, "why": why})
    total = len(pkg.cases)
    return {
        "skill": pkg.ref,
        "passed": passed,
        "total": total,
        "score": round(passed / total, 4) if total else 0.0,
        "threshold": pkg.eval_threshold,
        "cost_usd": round(cost, 6),
        "details": details,
    }
