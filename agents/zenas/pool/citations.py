"""Citation strings for the graph.

eyecite (Free Law Project, BSD) extracts reporters it knows. A few forms it
does not ship — federal rules, the Delaware Code, HTSUS — are added here so
those pool documents still link. South African forms are added beside them.
"""

from __future__ import annotations

import re

_KEEP = {
    "FullLawCitation",
    "FullCaseCitation",
    "ShortCaseCitation",
    "FullJournalCitation",
    "SupraCitation",
    "IdCitation",
}

# Forms eyecite 2.7 does not return. Information for the graph, not a licence call.
_EXTRA = (
    re.compile(r"\bFed\. R\. Civ\. P\. \d+(?:\.\d+)?(?:\([0-9A-Za-z]+\))*", re.I),
    re.compile(r"\bFed\. R\. Evid\. \d+(?:\.\d+)?(?:\([0-9A-Za-z]+\))*", re.I),
    re.compile(r"\bFed\. R\. App\. P\. \d+(?:\.\d+)?(?:\([0-9A-Za-z]+\))*", re.I),
    re.compile(r"\b\d+\s+Del\. C\.\s+§\s*[0-9A-Za-z.\-]+", re.I),
    re.compile(r"\bHTSUS\s+[0-9]+(?:\.[0-9]+)*", re.I),
    re.compile(r"\[\d{4}\]\s+ZA[A-Z]{2,8}\s+\d+", re.I),
    re.compile(r"\b\d{4}\s+\(\d+\)\s+SA\s+\d+\s+\([A-Za-z]{2,6}\)", re.I),
    re.compile(r"\bAct\s+\d+\s+of\s+\d{4},\s+s\s+\d+[A-Za-z]*", re.I),
    re.compile(r"\bUniform Rule\s+\d+[A-Za-z]?", re.I),
    re.compile(r"\bMagistrates' Courts Rule\s+\d+[A-Za-z]?", re.I),
)


def extract_citations(text: str) -> list[str]:
    """Unique citation strings, eyecite first, then the forms it skips."""
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        matched = " ".join(raw.split())
        if len(matched) < 4:
            return
        key = matched.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(matched)

    if not (text or "").strip():
        # eyecite raises on empty input ("Both markup_text and plain_text are empty").
        return found

    from eyecite import get_citations

    for cite in get_citations(text or ""):
        if type(cite).__name__ not in _KEEP:
            continue
        add(cite.matched_text())
    for pattern in _EXTRA:
        for match in pattern.finditer(text or ""):
            add(match.group(0))
    return found


_NEUTRAL_CITE = re.compile(r"\[(\d{4})\]\s+(ZA[A-Z]{2,8})\s+(\d+)", re.I)
_VERSUS_NAME = (
    r"[A-Z][A-Za-z0-9&'’.\-]*(?:\s+(?:\([^)]+\)|[A-Z][A-Za-z0-9&'’.\-]*)){0,10}"
)
_VERSUS = re.compile(rf"\b({_VERSUS_NAME}\s+v\.?\s+{_VERSUS_NAME})")
_PARA = re.compile(r"\[(\d+)\](?!\s*ZA[A-Z])")
# Stronger treatments win when one citation is discussed more than once.
_TREATMENT_RANK = {
    "overruled": 6,
    "not followed": 5,
    "distinguished": 4,
    "approved": 3,
    "applied": 2,
    "followed": 1,
    "referred to": 0,
}


def _treatment_of(window: str) -> str:
    """Treatment from the court's words. 'do not follow that approach' is not a treatment."""
    folded = " ".join((window or "").split()).lower()
    if re.search(r"\b(?:we |i )?declin(?:e|ed) to follow\b|\bnot followed\b", folded):
        return "not followed"
    if re.search(r"\bwas overruled\b|\boverruled\b", folded):
        return "overruled"
    if re.search(r"\bis distinguishable\b|\bdistinguished\b|\bdistinguishable\b", folded):
        return "distinguished"
    if re.search(r"\bapproved\b", folded):
        return "approved"
    if re.search(r"\bapplied\b", folded):
        return "applied"
    if re.search(r"\bfollowed\b", folded):
        return "followed"
    return "referred to"


def _paragraph_at(text: str, index: int) -> str:
    marks = list(_PARA.finditer(text[: index + 1]))
    if not marks:
        return ""
    return marks[-1].group(1)


def cite_treatments(text: str) -> list[dict[str, str]]:
    """How this judgment treats each case it cites.

    The treatment, the court's words, and the paragraph number come from the
    paragraph that contains the citation. The default treatment is "referred to".
    """
    body = text or ""
    if not body.strip():
        return []
    found: dict[str, dict[str, str]] = {}

    def keep(citation: str, start: int, end: int) -> None:
        key = " ".join(citation.split())
        if len(key) < 4:
            return
        left = body.rfind("\n\n", 0, start)
        right = body.find("\n\n", end)
        if left < 0:
            left = 0
        else:
            left += 2
        if right < 0:
            right = len(body)
        evidence = " ".join(body[left:right].split())
        treatment = _treatment_of(evidence)
        row = {
            "citation": key,
            "treatment": treatment,
            "evidence": evidence,
            "paragraph": _paragraph_at(body, start),
        }
        previous = found.get(key.lower())
        if previous is None or _TREATMENT_RANK[treatment] > _TREATMENT_RANK[previous["treatment"]]:
            found[key.lower()] = row

    for match in _NEUTRAL_CITE.finditer(body):
        keep(f"[{match.group(1)}] {match.group(2).upper()} {match.group(3)}", match.start(), match.end())
    for match in _VERSUS.finditer(body):
        keep(match.group(1), match.start(), match.end())
    return list(found.values())
