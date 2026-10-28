"""Deterministic checks only. No model clients or remote fallback."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from proselint.checks import __register__
from proselint.registry import CheckRegistry
from proselint.tools import LintFile

_registry = CheckRegistry()
if not getattr(_registry, "_tervory_proselint_loaded", False):
    _registry.register_many(__register__)
    _registry._tervory_proselint_loaded = True

from .voice import Voice

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "vendor"))
from agent_style.review import detectors_mech, detectors_struct
from agent_style.review.loader import parse_rules

RULES = parse_rules((ROOT / "vendor/agent_style/RULES.md").read_text())
MECHANICAL = {"RULE-05", "RULE-06", "RULE-12", "RULE-B", "RULE-D"}
STRUCTURAL = {"RULE-A", "RULE-C", "RULE-E"}
SKIPPED = [r.id for r in RULES if r.id not in MECHANICAL | STRUCTURAL]
# Literal candidates from each book's Avoid section. These flag review candidates;
# a code checker cannot decide whether the surrounding context justifies a phrase.
BOOK_TERMS = {
    "18f-content": ["easy", "simple", "obvious"],
    "apple-interface-writing": ["click here", "OK"],
    "github-docs": ["this", "that", "it"],
    "gitlab-docs": ["allow", "enable", "easy", "easily", "simple", "obvious"],
    "google-developer-docs": ["simply", "easily", "obviously", "allows you to", "please"],
    "govuk": ["please", "simply", "easy", "obvious"],
    "kubernetes-docs": ["new", "currently", "soon", "just", "simply", "easy"],
    "microsoft-writing-style": ["please"],
}

# Skala skill ids. Until the founder approves each 1.0.0, the room keeps today's local path.
SKILL_PROSELINT = "trigger.proselint"
SKILL_LANGUAGETOOL = "trigger.languagetool"
SKILL_AGENT_STYLE = "trigger.agent_style"
SKILL_HOUSE_STYLE = "trigger.house_style"
SKILL_READABILITY = "trigger.readability"
SKILL_VOICE = "trigger.voice_check"


def phrase_spans(text: str, phrase: str):
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(p) for p in phrase.split()) + r"(?!\w)"
    return list(re.finditer(pattern, text, re.IGNORECASE))


def local_checks(text: str, voice: Voice | None) -> dict:
    issues = []
    for found in LintFile("input", text).lint():
        item = found.into_dict()
        issues.append({"source": "proselint", "rule": item["check_path"], "message": item["message"],
                       "line": found.pos[0], "column": found.pos[1]})
    for rule in RULES:
        if rule.id == "RULE-12" and voice and voice.maxSentenceWords != 30:
            continue
        module = detectors_mech if rule.id in MECHANICAL else detectors_struct if rule.id in STRUCTURAL else None
        if module is None:
            continue
        result = module.run(rule, text, "input.md")
        issues.extend({"source": "agent-style", "rule": v.rule, "line": v.line,
                       "column": v.column, "message": v.detail} for v in result.violations)
    # Passive-voice candidates, not a semantic verdict about whether passive is appropriate.
    for match in re.finditer(r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(?:\w+ed|written|given|made|seen|known|taken|built|sent|shown|found|done)\b", text, re.IGNORECASE):
        issues.append({"source": "readability", "rule": "passive_voice", "offset": match.start(),
                       "length": match.end()-match.start(), "message": "Possible passive voice; review the actor and verb."})
    # Tenant-specific length threshold; the upstream detector supplies the default 30-word check.
    if voice and voice.maxSentenceWords != 30:
        for sentence in re.finditer(r"[^.!?]+[.!?]?", text):
            count = len(re.findall(r"\b[\w'-]+\b", sentence.group()))
            if count > voice.maxSentenceWords:
                issues.append({"source": "voice", "rule": "sentence_length", "offset": sentence.start(),
                               "message": f"Sentence has {count} words; voice limit is {voice.maxSentenceWords}."})
    if voice:
        for term in voice.bannedTerms:
            for match in phrase_spans(text, term):
                issues.append({"source": "voice", "rule": "banned_term", "offset": match.start(),
                               "length": match.end()-match.start(), "message": f"Banned term: {term}"})
        for term in voice.requiredTerms:
            if not phrase_spans(text, term):
                issues.append({"source": "voice", "rule": "required_term", "message": f"Required term missing: {term}"})
        # These are mechanical subsets of the selected book, not a semantic style grade.
        if voice.stylebook:
            guide = (ROOT / "sources/stylebooks" / voice.stylebook / "SKILL.md").read_text()
            for term in BOOK_TERMS.get(voice.stylebook, []):
                for match in phrase_spans(text, term):
                    issues.append({"source": "stylebook", "rule": "avoid_candidate", "offset": match.start(),
                                   "message": f"{voice.stylebook}: review '{term}' against the guide's Avoid section."})
            if "descriptive link" in guide.lower():
                for match in re.finditer(r"\[(?:click here|here|read more)\]\([^)]*\)", text, re.IGNORECASE):
                    issues.append({"source": "stylebook", "rule": "link_text", "offset": match.start(),
                                   "message": "Use descriptive link text."})
    # Practical Prose F3: mechanical markup checks only; no scorer or semantic grade.
    fences = re.findall(r"^\s*(`{3,}|~{3,})", text, re.MULTILINE)
    if len(fences) % 2:
        issues.append({"source": "practical-prose", "rule": "F3", "message": "Unclosed fenced code block."})
    return {"issues": issues, "skipped_agent_style_rules": SKIPPED,
            "checklist": {"E1": "grammar/readability findings", "E3": "proselint and phrase findings",
                          "F3": "fence balance only"},
            "limitations": "Mechanical findings only; semantic accuracy, voice fit and rubric grades are not assessed."}


def _strip_skill_meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not str(key).startswith("_")}


async def _run_approved(tank: Any, tenant_id: UUID | str, skill_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the approved Skala skill output, or None so the room keeps today's local copy."""
    if tank is None or not hasattr(tank, "run_skill"):
        return None
    try:
        out = await tank.run_skill(str(tenant_id), skill_id, payload)
    except (RuntimeError, AttributeError, TypeError):
        return None
    if not isinstance(out, dict):
        return None
    return _strip_skill_meta(out)


def map_languagetool(payload: dict[str, Any] | None, *, available: bool) -> dict[str, Any]:
    """Local LanguageTool mapper; same shape as trigger.languagetool until that skill is approved."""
    if not available or payload is None:
        return {
            "issues": [],
            "complete": False,
            "checker_errors": ["LanguageTool is unavailable; its checks have not completed."],
        }
    try:
        matches = payload["matches"]
        if not isinstance(matches, list):
            raise TypeError("Invalid matches")
        issues = [
            {
                "source": "languagetool",
                "rule": match["rule"]["id"],
                "message": match["message"],
                "offset": match["offset"],
                "length": match["length"],
            }
            for match in matches
        ]
        warnings = payload.get("warnings", {})
        if not isinstance(warnings, dict):
            raise TypeError("Invalid warnings")
        complete = not warnings.get("incompleteResults", False)
        return {
            "issues": issues,
            "complete": complete,
            "checker_errors": [] if complete else ["LanguageTool returned incomplete results."],
        }
    except (ValueError, KeyError, TypeError):
        return {
            "issues": [],
            "complete": False,
            "checker_errors": ["LanguageTool is unavailable; its checks have not completed."],
        }


async def fetch_languagetool(text: str, http: httpx.AsyncClient) -> tuple[dict[str, Any] | None, bool]:
    try:
        # Fixed internal destination, no configurable public service or cloud fallback.
        response = await http.post(
            "http://trigger-languagetool:8081/v2/check",
            data={"text": text, "language": "en-US"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Invalid LanguageTool payload")
        return payload, True
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None, False


async def check(
    text: str,
    voice: Voice | None,
    http: httpx.AsyncClient,
    tank: Any = None,
    tenant_id: UUID | str | None = None,
) -> dict:
    import asyncio

    lt_payload, lt_ok = await fetch_languagetool(text, http)

    if tank is not None and tenant_id is not None:
        issues: list[dict[str, Any]] = []
        skipped = list(SKIPPED)
        used_skala: list[str] = []
        local: dict[str, Any] | None = None

        async def fallback_local() -> dict[str, Any]:
            nonlocal local
            if local is None:
                local = await asyncio.to_thread(local_checks, text, voice)
            return local

        prose = await _run_approved(tank, tenant_id, SKILL_PROSELINT, {"text": text})
        if prose is None:
            issues.extend(
                item for item in (await fallback_local())["issues"] if item.get("source") == "proselint"
            )
        else:
            used_skala.append(SKILL_PROSELINT)
            issues.extend(prose.get("issues") or [])

        style = await _run_approved(
            tank,
            tenant_id,
            SKILL_AGENT_STYLE,
            {
                "text": text,
                "max_sentence_words": voice.maxSentenceWords if voice else 30,
            },
        )
        if style is None:
            bundle = await fallback_local()
            issues.extend(item for item in bundle["issues"] if item.get("source") == "agent-style")
            skipped = list(bundle.get("skipped_agent_style_rules") or SKIPPED)
        else:
            used_skala.append(SKILL_AGENT_STYLE)
            issues.extend(style.get("issues") or [])
            skipped = list(style.get("skipped_rules") or SKIPPED)

        house = await _run_approved(
            tank,
            tenant_id,
            SKILL_HOUSE_STYLE,
            {"text": text, "stylebook": voice.stylebook if voice else None},
        )
        if house is None:
            issues.extend(
                item for item in (await fallback_local())["issues"] if item.get("source") == "stylebook"
            )
        else:
            used_skala.append(SKILL_HOUSE_STYLE)
            issues.extend(house.get("issues") or [])

        read = await _run_approved(tank, tenant_id, SKILL_READABILITY, {"text": text})
        if read is None:
            issues.extend(
                item
                for item in (await fallback_local())["issues"]
                if item.get("source") in {"readability", "practical-prose"}
            )
        else:
            used_skala.append(SKILL_READABILITY)
            issues.extend(read.get("issues") or [])

        voice_payload = {
            "text": text,
            "banned_terms": list(voice.bannedTerms) if voice else [],
            "required_terms": list(voice.requiredTerms) if voice else [],
            "max_sentence_words": voice.maxSentenceWords if voice else 30,
        }
        voice_out = await _run_approved(tank, tenant_id, SKILL_VOICE, voice_payload)
        if voice_out is None:
            issues.extend(
                item for item in (await fallback_local())["issues"] if item.get("source") == "voice"
            )
        else:
            used_skala.append(SKILL_VOICE)
            issues.extend(voice_out.get("issues") or [])

        lt_skill = await _run_approved(
            tank,
            tenant_id,
            SKILL_LANGUAGETOOL,
            {"text": text, "lt_response": lt_payload if lt_ok else None},
        )
        if lt_skill is None:
            mapped = map_languagetool(lt_payload, available=lt_ok)
        else:
            used_skala.append(SKILL_LANGUAGETOOL)
            mapped = {
                "issues": list(lt_skill.get("issues") or []),
                "complete": bool(lt_skill.get("complete")),
                "checker_errors": list(lt_skill.get("checker_errors") or []),
            }
        issues.extend(mapped["issues"])
        result = {
            "issues": issues,
            "skipped_agent_style_rules": skipped,
            "checklist": {
                "E1": "grammar/readability findings",
                "E3": "proselint and phrase findings",
                "F3": "fence balance only",
            },
            "limitations": "Mechanical findings only; semantic accuracy, voice fit and rubric grades are not assessed.",
            "complete": mapped["complete"],
            "checker_errors": mapped["checker_errors"],
            "skala_skills": used_skala,
        }
    else:
        result = await asyncio.to_thread(local_checks, text, voice)
        mapped = map_languagetool(lt_payload, available=lt_ok)
        result["issues"].extend(mapped["issues"])
        result["complete"] = mapped["complete"]
        result["checker_errors"] = mapped["checker_errors"]
        result["skala_skills"] = []

    result["issue_count"] = len(result["issues"])
    result["issues"] = result["issues"][:200]
    result["truncated"] = result["issue_count"] > len(result["issues"])
    result["voice_revision"] = voice.revision if voice else None
    result["stylebook"] = voice.stylebook if voice else None
    result["model_calls"] = 0
    return result


def report_text(report: dict) -> str:
    lines = [f'{report["issue_count"]} issues found.']
    if report["truncated"]:
        lines.append("First 200 issues shown; check shorter sections for the remaining findings.")
    lines.extend(f'{i["source"]} / {i["rule"]}: {i["message"]}' for i in report["issues"])
    lines.extend(report["checker_errors"])
    lines.append(report["limitations"])
    return "\n".join(lines)
