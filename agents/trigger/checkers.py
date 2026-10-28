"""Deterministic checks only. No model clients or remote fallback."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from proselint.tools import LintFile
from proselint.checks import __register__
from proselint.registry import CheckRegistry

CheckRegistry().register_many(__register__)

from .voice import Voice

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "vendor"))
from agent_style.review import detectors_mech, detectors_struct  # noqa: E402
from agent_style.review.loader import parse_rules  # noqa: E402

RULES = parse_rules((ROOT / "vendor/agent_style/RULES.md").read_text())
MECHANICAL = {"RULE-05", "RULE-06", "RULE-12", "RULE-B", "RULE-D"}
STRUCTURAL = {"RULE-A", "RULE-C", "RULE-E"}
SKIPPED = [r.id for r in RULES if r.id not in MECHANICAL | STRUCTURAL]


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
        module = detectors_mech if rule.id in MECHANICAL else detectors_struct if rule.id in STRUCTURAL else None
        if module is None:
            continue
        result = module.run(rule, text, "input.md")
        issues.extend({"source": "agent-style", "rule": v.rule, "line": v.line,
                       "column": v.column, "message": v.detail} for v in result.violations)
    # Passive-voice candidates, not a semantic verdict about whether passive is appropriate.
    for match in re.finditer(r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(?:\w+ed|written|given|made|seen|known|taken|built|sent|shown|found|done)\b", text, re.I):
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
            if "descriptive link" in guide.lower():
                for match in re.finditer(r"\[(?:click here|here|read more)\]\([^)]*\)", text, re.I):
                    issues.append({"source": "stylebook", "rule": "link_text", "offset": match.start(),
                                   "message": "Use descriptive link text."})
    # Practical Prose F3: mechanical markup checks only; no scorer or semantic grade.
    fences = re.findall(r"^\s*(`{3,}|~{3,})", text, re.M)
    if len(fences) % 2:
        issues.append({"source": "practical-prose", "rule": "F3", "message": "Unclosed fenced code block."})
    return {"issues": issues, "skipped_agent_style_rules": SKIPPED,
            "checklist": {"E1": "grammar/readability findings", "E3": "proselint and phrase findings",
                          "F3": "fence balance only"},
            "limitations": "Mechanical findings only; semantic accuracy, voice fit and rubric grades are not assessed."}


async def check(text: str, voice: Voice | None, http: httpx.AsyncClient) -> dict:
    import asyncio
    result = await asyncio.to_thread(local_checks, text, voice)
    try:
        # Fixed internal destination, no configurable public service or cloud fallback.
        response = await http.post("http://trigger-languagetool:8081/v2/check",
                                   data={"text": text, "language": "en-US"}, timeout=30)
        response.raise_for_status()
        matches = response.json()["matches"]
        if not isinstance(matches, list):
            raise ValueError("Invalid matches")
        for match in matches:
            result["issues"].append({"source": "languagetool", "rule": match["rule"]["id"],
                                     "message": match["message"], "offset": match["offset"], "length": match["length"]})
        result["complete"] = True
        result["checker_errors"] = []
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        result["complete"] = False
        result["checker_errors"] = ["LanguageTool is unavailable; its checks have not completed."]
    result["voice_revision"] = voice.revision if voice else None
    result["stylebook"] = voice.stylebook if voice else None
    result["model_calls"] = 0
    return result


def report_text(report: dict) -> str:
    lines = [f'{i["source"]} / {i["rule"]}: {i["message"]}' for i in report["issues"]]
    lines.extend(report["checker_errors"])
    lines.append(report["limitations"])
    return "\n".join(lines)
