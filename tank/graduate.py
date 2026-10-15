"""Graduation: prove a cheaper model, a code skill, or the semantic cache, then switch.

Pure decisions live here so tests can run them with no database and no model call.
tank/main.py shadow and /v1/graduation/* are the only callers.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

SKILL_PREFIX = "skill:"
CACHE_CANDIDATE = "cache:semantic"
TOOL_PREFIX = "tool:"
SEMANTIC_THRESHOLD = 0.97
DEFAULT_THRESHOLD = 0.97
DEFAULT_MIN_SAMPLES = 30
DEFAULT_MAX_REJECT = 0.05
DEFAULT_TOLERANCE = 0.01
WATCH_DAYS = 7
RESEARCH_DAYS = 30

_ID_KEY = re.compile(r"(^id$|_id$)", re.I)
_SKILL_REF = re.compile(r"^skill:([^@\s]+)@([^\s]+)$")


def _norm(value: Any) -> str:
    return " ".join(str(value).lower().split())


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str) and value:
        try:
            return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _meets(value: float, bar: float) -> bool:
    return round(value, 4) >= round(bar, 4)


def is_skill(candidate: str | None) -> bool:
    return bool(candidate) and str(candidate).startswith(SKILL_PREFIX)


def is_semantic_cache(candidate: str | None) -> bool:
    return candidate == CACHE_CANDIDATE


def is_tool(candidate: str | None) -> bool:
    return bool(candidate) and str(candidate).startswith(TOOL_PREFIX)


def parse_skill(candidate: str | None) -> tuple[str, str] | None:
    if not candidate:
        return None
    match = _SKILL_REF.match(str(candidate).strip())
    if match is None:
        return None
    return match.group(1), match.group(2)


def code_candidate_problem(
    candidate: str | None,
    *,
    state: str | None,
    task_type: str | None,
    on_disk: bool,
) -> str | None:
    """A code candidate is an approved skill with no task type, so it cannot call a model."""
    if not is_skill(candidate):
        return None
    if parse_skill(candidate) is None:
        return "a code candidate looks like skill:id@version"
    if not on_disk:
        return "no such skill package"
    if task_type:
        return "a code candidate must not call a model"
    if state != "approved":
        return "a code candidate must be an approved skill"
    return None


def skill_payload(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """The skill sees the same input the model saw. JSON in the last user message wins."""
    content = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = str(message.get("content") or "")
            break
    parsed = as_obj(content)
    if isinstance(parsed, dict):
        return parsed
    return {"text": content}


def as_obj(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_set(value: Any) -> bool:
    return isinstance(value, (list, tuple, set))


def _item_key(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str).lower()
    return _norm(value)


def jaccard(left: Any, right: Any) -> float:
    a = {_item_key(item) for item in (left or []) if _item_key(item)}
    b = {_item_key(item) for item in (right or []) if _item_key(item)}
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _as_set(value: Any) -> list[Any]:
    if _is_set(value):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def score_value(key: str, left: Any, right: Any, *, tolerance: float) -> float:
    if _is_number(left) and _is_number(right) and not _ID_KEY.search(key):
        if left == right:
            return 1.0
        scale = max(abs(float(left)), abs(float(right)), 1.0)
        return 1.0 if abs(float(left) - float(right)) <= tolerance * scale else 0.0
    if _ID_KEY.search(key):
        return 1.0 if str(left).strip() == str(right).strip() else 0.0
    if _is_set(left) or _is_set(right):
        return jaccard(_as_set(left), _as_set(right))
    if isinstance(left, dict) and isinstance(right, dict):
        score, _fields = field_scores(left, right, tolerance=tolerance)
        return score
    if left is None and right is None:
        return 1.0
    if left is None or right is None:
        return 0.0
    return 1.0 if _norm(left) == _norm(right) else 0.0


def field_scores(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    keys: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> tuple[float, dict[str, float]]:
    chosen = list(keys) if keys is not None else sorted(set(left) | set(right))
    chosen = [key for key in chosen if not str(key).startswith("_")]
    if not chosen:
        return 1.0, {}
    fields = {
        key: score_value(key, left.get(key), right.get(key), tolerance=tolerance)
        for key in chosen
    }
    return sum(fields.values()) / len(fields), fields


@dataclass
class Comparison:
    agreement: float | None
    method: str
    fields: dict[str, float]


def compare(primary: Any, candidate: Any, *, tolerance: float = DEFAULT_TOLERANCE) -> Comparison:
    """Field by field when both sides are JSON. Free text is left for the judge."""
    left, right = as_obj(primary), as_obj(candidate)
    if not isinstance(left, dict) or not isinstance(right, dict):
        return Comparison(agreement=None, method="text", fields={})
    score, fields = field_scores(left, right, tolerance=tolerance)
    return Comparison(agreement=score, method="fields", fields=fields)


def score_pair(expected: Any, output: Any, *, tolerance: float = DEFAULT_TOLERANCE) -> float:
    """One screen case. Expected keys only, so extra skill fields do not dilute the score.
    Free text falls back to word overlap so a screen does not need the judge."""
    if isinstance(expected, dict):
        got = output if isinstance(output, dict) else as_obj(output)
        if got is None:
            blobs = [str(value) for value in expected.values() if isinstance(value, str)]
            structured = any(isinstance(value, (dict, list)) for value in expected.values())
            if blobs and not structured:
                return jaccard(" ".join(blobs).split(), str(output or "").split())
            got = {}
        score, _fields = field_scores(expected, got, keys=list(expected.keys()), tolerance=tolerance)
        return score
    compared = compare(expected, output, tolerance=tolerance)
    if compared.agreement is None:
        return jaccard(str(expected).split(), str(output or "").split())
    return compared.agreement


def average_fields(rows: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        raw = row.get("fields") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = {}
        if not isinstance(raw, dict):
            continue
        for key, value in raw.items():
            try:
                buckets.setdefault(str(key), []).append(float(value))
            except (TypeError, ValueError):
                continue
    return {key: sum(values) / len(values) for key, values in buckets.items()}


def _floors(policy: dict[str, Any]) -> dict[str, float]:
    raw = policy.get("field_floors") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def fields_clear(scores: dict[str, float], policy: dict[str, Any]) -> tuple[bool, str | None]:
    bar = _float(policy.get("eval_threshold"), DEFAULT_THRESHOLD)
    floors = _floors(policy)
    for name, score in scores.items():
        floor = floors.get(name, bar)
        if not _meets(score, floor):
            return False, f"{name} is below its floor"
    return True, None


def proven_reason(policy: dict[str, Any], evidence: Evidence) -> tuple[bool, str | None]:
    bar = _float(policy.get("eval_threshold"), DEFAULT_THRESHOLD)
    minimum = _int(policy.get("min_shadow_samples"), DEFAULT_MIN_SAMPLES)
    ceiling = _float(policy.get("max_reject_rate"), DEFAULT_MAX_REJECT)
    if evidence.samples < minimum:
        return False, "too few shadow samples"
    if evidence.agreement is None or not _meets(evidence.agreement, bar):
        return False, "agreement is below the bar"
    ok, why = fields_clear(evidence.fields, policy)
    if not ok:
        return False, why
    if evidence.judged > 0 and round(evidence.rejected / evidence.judged, 4) > round(ceiling, 4):
        return False, "client rejections are above the bar"
    return True, None


@dataclass
class Evidence:
    samples: int = 0
    agreement: float | None = None
    fields: dict[str, float] = field(default_factory=dict)
    rejected: int = 0
    judged: int = 0
    live_agreement: float | None = None


@dataclass
class Move:
    action: str
    policy: dict[str, Any]
    reason: str | None = None


def _copied(policy: dict[str, Any]) -> dict[str, Any]:
    return dict(policy)


def _promoted(policy: dict[str, Any], now: datetime) -> dict[str, Any]:
    updated = _copied(policy)
    candidate = str(policy.get("candidate_model") or "")
    if router_cannot_serve(candidate):
        raise ValueError(ROUTER_BLOCK)
    updated["previous_model"] = policy.get("model")
    updated["model"] = candidate
    updated["candidate_model"] = None
    updated["shadow_rate"] = 0
    updated["promoted_at"] = _aware(now)
    if candidate.startswith(SKILL_PREFIX):
        updated["rung"] = 3
        updated["semantic_cache"] = False
    elif candidate == CACHE_CANDIDATE or candidate.startswith("cache:"):
        updated["rung"] = 4
        updated["semantic_cache"] = True
    return updated


def _rolled_back(policy: dict[str, Any], reason: str) -> dict[str, Any]:
    updated = _copied(policy)
    previous = str(policy.get("previous_model") or "")
    updated["model"] = previous
    updated["previous_model"] = None
    updated["promoted_at"] = None
    updated["shadow_rate"] = 0
    updated["note"] = reason
    if previous.startswith(SKILL_PREFIX):
        updated["rung"] = 3
        updated["semantic_cache"] = False
    elif previous.startswith("cache:"):
        updated["rung"] = 4
        updated["semantic_cache"] = True
    else:
        updated["rung"] = 1
        updated["semantic_cache"] = False
    return updated


def _wants_auto(policy: dict[str, Any]) -> bool:
    value = policy.get("auto_promote", True)
    if value is None:
        return True
    return bool(value)


def router_cannot_serve(candidate: str | None) -> bool:
    """run_route still posts policy.model to LiteLLM. A skill or the semantic cache is not a model name."""
    if not candidate:
        return False
    name = str(candidate)
    return is_skill(name) or is_semantic_cache(name) or name.startswith("cache:")


ROUTER_BLOCK = "the router cannot serve this name with no LiteLLM call yet"


def promote_if_proven(policy: dict[str, Any], evidence: Evidence, now: datetime, *, automatic: bool) -> Move:
    if not policy.get("candidate_model"):
        return Move("hold", _copied(policy), "no candidate")
    candidate = str(policy.get("candidate_model") or "")
    if router_cannot_serve(candidate):
        return Move("hold", _copied(policy), ROUTER_BLOCK)
    ok, reason = proven_reason(policy, evidence)
    if not ok:
        return Move("hold", _copied(policy), reason)
    if automatic and not _wants_auto(policy):
        return Move("hold", _copied(policy), "proven, waiting for a person")
    return Move("promote", _promoted(policy, now), None)


def rollback_if_dropped(policy: dict[str, Any], evidence: Evidence, now: datetime) -> Move:
    promoted_at = _as_dt(policy.get("promoted_at"))
    if promoted_at is None or not policy.get("previous_model") or policy.get("candidate_model"):
        return Move("hold", _copied(policy), None)
    if _aware(now) - promoted_at > timedelta(days=WATCH_DAYS):
        return Move("hold", _copied(policy), None)
    ceiling = _float(policy.get("max_reject_rate"), DEFAULT_MAX_REJECT)
    bar = _float(policy.get("eval_threshold"), DEFAULT_THRESHOLD)
    reasons: list[str] = []
    if evidence.judged > 0 and round(evidence.rejected / evidence.judged, 4) > round(ceiling, 4):
        reasons.append("client rejections are above the bar")
    if evidence.live_agreement is not None and not _meets(evidence.live_agreement, bar):
        reasons.append("live agreement is below the bar")
    if not reasons:
        return Move("hold", _copied(policy), None)
    reason = "; ".join(reasons)
    return Move("rollback", _rolled_back(policy, reason), reason)


def apply(policy: dict[str, Any], evidence: Evidence, now: datetime) -> Move:
    """Promote by itself when the candidate is proven. Roll back a fresh promotion that slips."""
    if policy.get("candidate_model"):
        return promote_if_proven(policy, evidence, now, automatic=True)
    return rollback_if_dropped(policy, evidence, now)


def budget_open(spent: float, limit: float, *, code: bool) -> bool:
    """Paid shadow stops at the daily cap. Code costs nothing and is always run."""
    if code:
        return True
    return float(spent) < float(limit)


def research_reason(
    searched_at: datetime | None,
    now: datetime,
    roster_fingerprint: str,
    price_fingerprint: str,
    stored_roster: str | None,
    stored_price: str | None,
) -> str | None:
    if searched_at is None:
        return "never searched"
    if roster_fingerprint != stored_roster:
        return "roster changed"
    if price_fingerprint != stored_price:
        return "price changed"
    if _aware(now) - _aware(searched_at) >= timedelta(days=RESEARCH_DAYS):
        return "monthly"
    return None


@dataclass(frozen=True)
class Quote:
    name: str
    price: float
    funds: bool = True
    kind: str = "model"  # model | code | tool


@dataclass
class Ranked:
    name: str
    kind: str
    price: float
    screen_agreement: float | None
    shadow_n: int
    shadow_agreement: float | None
    status: str
    cost_per_call: float
    monthly_saving_usd: float | None
    fields_ok: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "price": self.price,
            "screen_agreement": self.screen_agreement,
            "shadow_n": self.shadow_n,
            "shadow_agreement": self.shadow_agreement,
            "status": self.status,
            "cost_per_call": self.cost_per_call,
            "monthly_saving_usd": self.monthly_saving_usd,
            "fields_ok": self.fields_ok,
        }


@dataclass
class SearchResult:
    ranked: list[Ranked]
    proposed: str | None
    next_shadow: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ranked": [row.as_dict() for row in self.ranked],
            "proposed": self.proposed,
            "next_shadow": self.next_shadow,
        }


def quotes_from_roster(models: list[dict[str, Any]]) -> list[Quote]:
    quotes: list[Quote] = []
    for model in models:
        info = model.get("model_info") or {}
        price = float(info.get("input_cost_per_token") or 0) + float(info.get("output_cost_per_token") or 0)
        quotes.append(Quote(name=str(model["model_name"]), price=price, funds=True, kind="model"))
    return quotes


def load_price_roster(path: Path) -> list[Quote]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return quotes_from_roster(list(raw.get("model_list") or []))


def fingerprints(quotes: list[Quote]) -> tuple[str, str]:
    names = "|".join(sorted(quote.name for quote in quotes))
    prices = "|".join(f"{quote.name}:{quote.price:.8f}" for quote in sorted(quotes, key=lambda quote: quote.name))
    return (
        hashlib.sha256(names.encode()).hexdigest()[:16],
        hashlib.sha256(prices.encode()).hexdigest()[:16],
    )


def search(
    *,
    serving: str,
    roster: list[Quote],
    screens: dict[str, float],
    shadows: dict[str, tuple[int, float | None]] | None = None,
    field_scores_by_name: dict[str, dict[str, float]] | None = None,
    calls_30d: int = 0,
    serving_cost: float | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    floors: dict[str, float] | None = None,
) -> SearchResult:
    """Cheapest first. A cheaper option that misses the bar is not proposed."""
    by_name = {quote.name: quote for quote in roster}
    serving_quote = by_name.get(serving)
    serving_price = serving_quote.price if serving_quote is not None else _float(serving_cost, 0.0)
    paid_cost = _float(serving_cost, serving_price)
    live = shadows or {}
    fields_by = field_scores_by_name or {}
    floor_map = floors or {}
    ranked: list[Ranked] = []
    for quote in roster:
        if quote.name == serving:
            continue
        if quote.kind != "code" and not quote.funds:
            continue
        if quote.kind != "code" and quote.price >= serving_price:
            continue
        screen = screens.get(quote.name)
        shadow = live.get(quote.name)
        shadow_n = int(shadow[0]) if shadow is not None else 0
        shadow_agreement = shadow[1] if shadow is not None else None
        scores = fields_by.get(quote.name) or {}
        fields_ok = all(_meets(score, floor_map.get(name, threshold)) for name, score in scores.items())
        if screen is None:
            status = "unscreened"
        elif not _meets(screen, threshold) or not fields_ok:
            status = "dropped"
        elif shadow is not None and shadow_n >= min_samples and (
            shadow_agreement is None or not _meets(shadow_agreement, threshold) or not fields_ok
        ):
            status = "dropped"
        elif shadow is not None and shadow_n >= min_samples:
            status = "cleared"
        else:
            status = "shadow"
        saving = (paid_cost - quote.price) * calls_30d
        ranked.append(Ranked(
            name=quote.name,
            kind=quote.kind,
            price=quote.price,
            screen_agreement=screen,
            shadow_n=shadow_n,
            shadow_agreement=shadow_agreement,
            status=status,
            cost_per_call=quote.price,
            monthly_saving_usd=saving,
            fields_ok=fields_ok,
        ))
    ranked.sort(key=lambda row: (row.price, row.name))
    proposed: str | None = None
    next_shadow: str | None = None
    for row in ranked:
        if row.status == "dropped":
            continue
        if row.status == "unscreened":
            break
        if row.status == "cleared":
            if proposed is None:
                proposed = row.name
            continue
        if next_shadow is None:
            next_shadow = row.name
        if proposed is None:
            proposed = row.name
        break
    return SearchResult(ranked=ranked, proposed=proposed, next_shadow=next_shadow)


def cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def semantic_lookup(
    vector: list[float],
    rows: list[dict[str, Any]],
    *,
    tenant_id: str,
    scope: str,
    threshold: float = SEMANTIC_THRESHOLD,
) -> dict[str, Any] | None:
    """Near-identical question, same scope rules as the exact cache. No paid call."""
    if scope not in {"tenant", "platform"}:
        return None
    best: tuple[float, dict[str, Any]] | None = None
    for row in rows:
        if scope == "tenant" and str(row.get("tenant_id")) != str(tenant_id):
            continue
        similarity = cosine(vector, list(row.get("vector") or []))
        if similarity >= threshold and (best is None or similarity > best[0]):
            best = (similarity, row)
    if best is None:
        return None
    return {"content": best[1].get("content"), "similarity": best[0], "tenant_id": best[1].get("tenant_id")}


def _step(
    label: str,
    name: str | None,
    *,
    samples: int,
    agreement: float | None,
    cost_per_call: float | None,
    monthly_saving_usd: float | None,
    current: bool,
) -> dict[str, Any]:
    return {
        "label": label,
        "name": name,
        "samples": samples,
        "agreement": agreement,
        "cost_per_call": cost_per_call,
        "monthly_saving_usd": monthly_saving_usd,
        "current": current,
    }


def _saving(before: float | None, after: float | None, calls: int) -> float | None:
    if before is None or after is None:
        return None
    return (before - after) * calls


def ladder_from_policy(
    *,
    model: str,
    previous_model: str | None,
    candidate_model: str | None,
    calls_30d: int,
    prim_cost: float | None,
    cand_cost: float | None,
    shadow_n: int,
    shadow_agreement: float | None,
    ranked: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Paid model, then a cheaper model, then code. The serving step is marked current."""
    rows = list(ranked or [])
    serving = str(model)
    paid_name = previous_model if (is_skill(serving) or is_semantic_cache(serving) or serving.startswith("cache:")) else serving
    cheaper = next((row for row in rows if row.get("kind") == "model" and row.get("status") != "dropped"), None)
    if cheaper is None and candidate_model and not is_skill(candidate_model) and not is_semantic_cache(candidate_model):
        cheaper = {
            "name": candidate_model,
            "shadow_n": shadow_n,
            "shadow_agreement": shadow_agreement,
            "cost_per_call": cand_cost,
            "monthly_saving_usd": _saving(prim_cost, cand_cost, calls_30d),
        }
    code = next((row for row in rows if row.get("kind") == "code" and row.get("status") != "dropped"), None)
    if is_skill(serving):
        code = {
            "name": serving,
            "shadow_n": calls_30d,
            "shadow_agreement": shadow_agreement,
            "cost_per_call": 0.0,
            "monthly_saving_usd": _saving(prim_cost, 0.0, calls_30d),
        }
    elif is_skill(candidate_model):
        code = {
            "name": candidate_model,
            "shadow_n": shadow_n,
            "shadow_agreement": shadow_agreement,
            "cost_per_call": 0.0,
            "monthly_saving_usd": _saving(prim_cost, 0.0, calls_30d),
        }
    cheaper_name = str(cheaper["name"]) if cheaper and cheaper.get("name") else None
    code_name = str(code["name"]) if code and code.get("name") else None
    cheaper_cost = _maybe_float(cheaper.get("cost_per_call") if cheaper else None)
    if cheaper_cost is None and cheaper_name and cheaper_name == candidate_model:
        cheaper_cost = cand_cost
    code_cost = 0.0 if code_name else None
    return [
        _step(
            "Paid model",
            paid_name,
            samples=calls_30d,
            agreement=None,
            cost_per_call=prim_cost,
            monthly_saving_usd=None,
            current=paid_name == serving,
        ),
        _step(
            "Cheaper model",
            cheaper_name,
            samples=_int(cheaper.get("shadow_n") if cheaper else 0, 0),
            agreement=_maybe_float(cheaper.get("shadow_agreement") if cheaper else None),
            cost_per_call=cheaper_cost,
            monthly_saving_usd=_saving(prim_cost, cheaper_cost, calls_30d) if cheaper_name else None,
            current=bool(cheaper_name) and cheaper_name == serving,
        ),
        _step(
            "Code",
            code_name,
            samples=_int(code.get("shadow_n") if code else 0, 0),
            agreement=_maybe_float(code.get("shadow_agreement") if code else None),
            cost_per_call=code_cost,
            monthly_saving_usd=_saving(prim_cost, code_cost, calls_30d) if code_name else None,
            current=bool(code_name) and code_name == serving,
        ),
    ]


def _maybe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


@dataclass
class CallResult:
    content: str
    model_calls: int
    cost_usd: float
    rung: int


async def answer(model: str, payload: dict[str, Any], *, llm: Any, run_code: Any) -> CallResult:
    """A promoted skill or the semantic cache answers with no model call."""
    if is_skill(model) or is_semantic_cache(model) or str(model).startswith("cache:"):
        content = await run_code(model, payload)
        if not isinstance(content, str):
            content = json.dumps(content)
        rung = 4 if str(model).startswith("cache:") else 3
        return CallResult(content=content, model_calls=0, cost_usd=0.0, rung=rung)
    content, cost = await llm(model, payload)
    return CallResult(content=str(content), model_calls=1, cost_usd=float(cost), rung=1)
