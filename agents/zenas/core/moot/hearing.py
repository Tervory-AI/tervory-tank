"""Durable text-hearing transitions. No storage, providers, fixtures or synthetic receipts.

All commands run under a repository transaction. Internal state includes bench notes;
only ``view`` may be returned to a participant. A committed turn is the handover
boundary: streamed/draft text never becomes hearing history until ``turn`` commits.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

SEATS = ("applicant", "respondent", "judge")
SIDES = ("applicant", "respondent")


class HearingError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Actor:
    """Trusted server identity, never populated from a browser JSON body."""
    tenant_id: str
    user_id: str
    region: str
    founder: bool = False


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HearingError(code)


def _text(value: Any, *, maximum: int = 24000) -> str:
    _require(isinstance(value, str) and bool(value.strip()) and len(value) <= maximum, "invalid_text")
    return value.strip()


def _uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise HearingError("invalid_id") from None


def _seat(value: Any) -> str:
    _require(value in SEATS, "invalid_seat")
    return value


def _controller(value: Any) -> dict[str, Any]:
    _require(isinstance(value, dict) and value.get("kind") in ("ai", "human"), "invalid_controller")
    kind = value["kind"]
    user = _text(value.get("user_id"), maximum=200) if kind == "human" else None
    _require(kind != "ai" or value.get("user_id") is None, "invalid_controller")
    return {"kind": kind, "user_id": user, "epoch": 0}


def _problem(value: Any, region: str) -> dict[str, Any]:
    _require(isinstance(value, dict), "invalid_problem")
    _require(value.get("region") == region and region in ("us-east", "za"), "wrong_region")
    _require(value.get("kind") == "civil_appeal" and value.get("criminal") is False, "civil_only")
    _uuid(value.get("worked_id"))
    _text(value.get("title"), maximum=400)
    _text(value.get("facts"))
    _require(isinstance(value.get("issues"), list) and 0 < len(value["issues"]) <= 50, "invalid_issues")
    for issue in value["issues"]:
        _text(issue, maximum=2000)
    _require(isinstance(value.get("bundles"), dict) and all(s in value["bundles"] for s in SIDES), "invalid_bundles")
    _require(isinstance(value.get("bench_notes"), dict), "invalid_bench_notes")
    _text(value.get("real_holding"))
    _require(isinstance(value.get("authorities"), list) and len(value["authorities"]) <= 200, "invalid_authorities")
    ids = []
    for authority in value["authorities"]:
        _require(isinstance(authority, dict), "invalid_authority")
        ids.append(_text(authority.get("id"), maximum=200))
        _text(authority.get("name"), maximum=500)
        _text(authority.get("quote"))
        _text(authority.get("source_url"), maximum=2000)
        _require(authority.get("verified") is True, "unverified_authority")
    _require(len(set(ids)) == len(ids), "duplicate_authority")
    # Whitelist snapshots: verification is performed by the worked-matter adapter
    # before this domain function; arbitrary caller fields cannot enter the state.
    return {key: deepcopy(value[key]) for key in (
        "worked_id", "region", "kind", "criminal", "title", "facts", "issues",
        "bundles", "bench_notes", "real_holding", "authorities")}


def authorize(state: dict[str, Any], actor: Actor) -> None:
    _require(actor.tenant_id == state["tenant_id"] and actor.region == state["region"], "not_found")
    assigned = {seat["user_id"] for seat in state["seats"].values() if seat["kind"] == "human"}
    _require(actor.user_id == state["owner_id"] or actor.user_id in assigned or actor.founder, "not_found")


def _operator(state: dict[str, Any], actor: Actor) -> None:
    authorize(state, actor)
    _require(actor.founder and actor.user_id == state["owner_id"], "operator_required")


def create(hearing_id: str, actor: Actor, problem: dict[str, Any], seats: dict[str, Any]) -> dict[str, Any]:
    _require(actor.founder and bool(actor.user_id), "operator_required")
    _uuid(actor.tenant_id)
    _require(set(seats) == set(SEATS), "invalid_seats")
    return {
        "id": _uuid(hearing_id), "tenant_id": actor.tenant_id, "region": actor.region,
        "owner_id": actor.user_id, "revision": 0, "phase": "draft", "problem_version": 1,
        "problem": _problem(problem, actor.region),
        "seats": {s: _controller(seats[s]) for s in SEATS},
        "floor": "applicant", "current_issue": 0, "pending_question": None,
        "transcript": [], "citations": [], "receipts": [], "pending_ai": None,
        "ai_attempts": [], "ruling": None, "published": False,
    }


def _begin(state: dict[str, Any], actor: Actor, revision: int) -> dict[str, Any]:
    authorize(state, actor)
    _require(type(revision) is int and revision == state["revision"], "stale_revision")
    return deepcopy(state)


def _finish(state: dict[str, Any]) -> dict[str, Any]:
    state["revision"] += 1
    return state


def change(state: dict[str, Any], actor: Actor, revision: int, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Operator transitions. No command resets transcript, issues, citations or floor."""
    out = _begin(state, actor, revision)
    _operator(out, actor)
    if action == "edit":
        _require(out["phase"] == "draft", "problem_locked")
        out["problem"] = _problem(payload["problem"], out["region"])
        out["problem_version"] += 1
    elif action == "lock":
        _require(out["phase"] == "draft", "invalid_phase")
        out["phase"] = "locked"
    elif action == "start":
        _require(out["phase"] == "locked", "problem_not_locked")
        out["phase"] = "hearing"
    elif action == "handover":
        _require(out["phase"] in ("draft", "locked", "hearing"), "invalid_phase")
        seat = _seat(payload.get("seat"))
        controller = _controller(payload.get("controller"))
        controller["epoch"] = out["seats"][seat]["epoch"] + 1
        out["seats"][seat] = controller
        _invalidate_ai(out, "handover")
    elif action == "issue":
        _require(out["phase"] == "hearing" and out["floor"] == "judge", "judge_floor_required")
        index = payload.get("index")
        _require(type(index) is int and 0 <= index < len(out["problem"]["issues"]), "invalid_issue")
        out["current_issue"] = index
        _invalidate_ai(out, "issue_changed")
    else:
        raise HearingError("invalid_action")
    return _finish(out)


def _invalidate_ai(state: dict[str, Any], reason: str) -> None:
    pending = state["pending_ai"]
    if pending:
        state["ai_attempts"].append({**pending, "status": "invalidated", "reason": reason})
        state["pending_ai"] = None


def claim_ai(state: dict[str, Any], actor: Actor, revision: int, token: str) -> dict[str, Any]:
    out = _begin(state, actor, revision)
    _operator(out, actor)
    _require(out["phase"] == "hearing", "invalid_phase")
    seat = out["floor"]
    _require(out["seats"][seat]["kind"] == "ai", "human_controls_seat")
    _require(out["pending_ai"] is None, "ai_turn_pending")
    token = _uuid(token)
    _require(not any(a["token"] == token for a in out["ai_attempts"]), "ai_token_reused")
    out["pending_ai"] = {"token": token, "seat": seat, "epoch": out["seats"][seat]["epoch"],
                         "revision": revision + 1, "status": "claimed"}
    return _finish(out)


def mark_ai_started(state: dict[str, Any], actor: Actor, revision: int, token: str) -> dict[str, Any]:
    out = _begin(state, actor, revision)
    _operator(out, actor)
    pending = out["pending_ai"]
    _require(pending is not None and pending["token"] == token and pending["status"] == "claimed", "ai_claim_invalid")
    pending["status"] = "started"
    pending["revision"] = revision + 1
    return _finish(out)


def abandon_ai(state: dict[str, Any], actor: Actor, revision: int, token: str) -> dict[str, Any]:
    """Explicitly resolve an uncertain call before another call; never auto-replay it."""
    out = _begin(state, actor, revision)
    _operator(out, actor)
    _require(out["pending_ai"] is not None and out["pending_ai"]["token"] == token, "ai_claim_invalid")
    _invalidate_ai(out, "operator_abandoned_uncertain_call")
    return _finish(out)


def _receipt(value: Any) -> dict[str, Any]:
    _require(isinstance(value, dict), "receipt_required")
    ledger_id = _uuid(value.get("ledger_id"))
    cost = value.get("cost_usd")
    _require(cost is None or (type(cost) in (int, float) and 0 <= cost < float("inf")), "invalid_receipt")
    return {"ledger_id": ledger_id, "cost_usd": cost,
            "model": _text(value.get("model"), maximum=300),
            "settings_hash": value.get("settings_hash")}


def turn(state: dict[str, Any], actor: Actor, revision: int, payload: dict[str, Any], *,
         ai_token: str | None = None, receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    """Commit one complete turn. Payload is citation-validated by the service first."""
    out = _begin(state, actor, revision)
    _require(out["phase"] == "hearing", "invalid_phase")
    seat = out["floor"]
    controller = out["seats"][seat]
    if ai_token is None:
        _require(controller["kind"] == "human" and controller["user_id"] == actor.user_id, "seat_not_owned")
        _require(receipt is None, "human_receipt_forbidden")
    else:
        _operator(out, actor)
        p = out["pending_ai"]
        _require(controller["kind"] == "ai" and p is not None and p["status"] == "started"
                 and p["token"] == ai_token and p["seat"] == seat
                 and p["epoch"] == controller["epoch"] and p["revision"] == revision, "ai_claim_invalid")
        saved_receipt = _receipt(receipt)
        _require(not any(r["ledger_id"] == saved_receipt["ledger_id"] for r in out["receipts"]), "receipt_reused")
        out["receipts"].append({**saved_receipt, "seat": seat, "turn": len(out["transcript"]), "token": ai_token})
    kind = payload.get("kind")
    _require(kind in (("question", "direction", "ruling") if seat == "judge" else ("submission",)), "invalid_turn_kind")
    text = _text(payload.get("text"))
    cited = payload.get("authority_ids", [])
    _require(isinstance(cited, list) and all(isinstance(a, str) for a in cited), "invalid_authorities")
    known = {a["id"] for a in out["problem"]["authorities"]}
    _require(set(cited) <= known, "unverified_authority")
    entry = {"number": len(out["transcript"]), "seat": seat, "controller": controller["kind"],
             "actor_id": actor.user_id if ai_token is None else None, "epoch": controller["epoch"],
             "kind": kind, "text": text, "authority_ids": list(dict.fromkeys(cited)),
             "issue": out["current_issue"]}
    out["transcript"].append(entry)
    out["citations"] = list(dict.fromkeys([*out["citations"], *cited]))
    if seat != "judge":
        out["pending_question"] = None
        out["floor"] = "judge"
    elif kind in ("question", "direction"):
        target = payload.get("target")
        _require(target in SIDES, "invalid_target")
        out["floor"] = target
        out["pending_question"] = {"target": target, "text": text, "turn": entry["number"]} if kind == "question" else None
    else:
        heard = {t["seat"] for t in out["transcript"] if t["kind"] == "submission"}
        _require(set(SIDES) <= heard, "both_sides_must_be_heard")
        order = _text(payload.get("order"), maximum=4000)
        reasons = payload.get("reasons")
        _require(isinstance(reasons, list) and 0 < len(reasons) <= 100, "invalid_reasons")
        out["ruling"] = {"order": order, "reasons": [_text(r) for r in reasons],
                         "authority_ids": entry["authority_ids"], "text": text}
        out["phase"] = "closed"
        out["pending_question"] = None
    if ai_token is not None:
        out["ai_attempts"].append({**out["pending_ai"], "status": "committed"})
        out["pending_ai"] = None
    return _finish(out)


def view(state: dict[str, Any], actor: Actor, seat: str | None = None) -> dict[str, Any]:
    """Projection is positive-list only; counsel never receives the internal problem."""
    authorize(state, actor)
    if seat is not None:
        seat = _seat(seat)
        controller = state["seats"][seat]
        _require(actor.founder and actor.user_id == state["owner_id"]
                 or controller["kind"] == "human" and controller["user_id"] == actor.user_id, "seat_not_owned")
    problem = state["problem"]
    out = {k: deepcopy(state[k]) for k in (
        "id", "region", "revision", "phase", "problem_version", "seats", "floor",
        "current_issue", "pending_question", "transcript", "citations", "ruling", "published")}
    # Participant identifiers are visible only to the operator; students see controller kinds.
    if not (actor.founder and actor.user_id == state["owner_id"]):
        out["seats"] = {s: {"kind": c["kind"], "epoch": c["epoch"]} for s, c in out["seats"].items()}
        for entry in out["transcript"]:
            entry.pop("actor_id", None)
    out["problem"] = {k: deepcopy(problem[k]) for k in ("title", "facts", "issues")}
    if seat in SIDES:
        # Existing recursive bench-note stripping also applies to nested counsel bundles.
        from agents.zenas.core.moot.problem import _strip_private
        bundle = deepcopy(problem["bundles"][seat])
        _strip_private(bundle)
        out["problem"]["bundle"] = bundle
    if seat == "judge":
        out["problem"]["bench_notes"] = deepcopy(problem["bench_notes"])
        out["problem"]["real_holding"] = problem["real_holding"]
    if state["phase"] == "closed" or state["published"]:
        out["reveal"] = problem["real_holding"]
    return out


def ai_context(state: dict[str, Any], actor: Actor, token: str) -> dict[str, Any]:
    _operator(state, actor)
    p = state["pending_ai"]
    _require(p is not None and p["token"] == token and p["revision"] == state["revision"], "ai_claim_invalid")
    return view(state, actor, p["seat"])
