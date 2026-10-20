"""Public, region-local candidate labels; no client rows or model calls."""

from __future__ import annotations

import json
from typing import Any

from agents.zenas.core.convert import criminal_case, fact_passages
from agents.zenas.core.engine import quote_in_source
from agents.zenas.core.release_mask import COURT_SOURCES
from agents.zenas.core.scope_rules import classify
from agents.zenas.pool.catalogue import CATALOGUE


def _object(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def case_candidate(row: dict[str, Any], region: str) -> dict[str, Any] | None:
    jurisdiction = "za" if region == "za" else "us"
    if (
        region not in {"za", "us-east"}
        or row.get("region") != region or row.get("jurisdiction") != jurisdiction
        or row.get("tenant_id") is not None or row.get("source") != "case"
        or row.get("material_type") != "public_record"
        or row.get("source_id") not in COURT_SOURCES or criminal_case(row)
    ):
        return None
    pattern = _object(row.get("fact_pattern") or {})
    facts = str(pattern.get("facts") or pattern.get("narrative") or "")
    judgment = str(row.get("text") or "")
    if not facts or not judgment or classify(facts, jurisdiction).get("criminal"):
        return None
    if not all(quote_in_source(part, judgment) for part in fact_passages(facts)):
        return None
    findings = _object(row.get("element_findings") or [])
    outcome = str(row.get("outcome") or "")
    if not findings or not outcome:
        return None
    held = bool(row.get("holdout"))
    return {
        "skill_id": "zenas.case_facts",
        "input": {
            "pool_doc_id": str(row["pool_doc_id"]), "judgment": judgment,
            "home_region": region, "holdout": held,
        },
        "expected": {
            "features": pattern.get("features") or {}, "narrative": facts,
            "element_findings": findings, "outcome": outcome,
        },
        "label_source": f"{'held_out' if held else 'converted'}:{row['source_id']}:{row['pool_version_id']}",
        "region": region,
        "public": True,
    }


def statute_candidate(row: dict[str, Any], region: str) -> dict[str, Any] | None:
    jurisdiction = "za" if region == "za" else "us"
    sources = {item.source_id for item in CATALOGUE if item.region == region}
    if (
        region not in {"za", "us-east"}
        or row.get("jurisdiction") != jurisdiction or row.get("source_id") not in sources
        or row.get("kind") != "statute" or not row.get("text") or not row.get("citation")
        or classify(str(row.get("title") or "") + " " + str(row["text"]), jurisdiction).get("criminal")
    ):
        return None
    passage = {
        "doc_id": str(row["document_id"]), "version_id": str(row["version_id"]),
        "citation": row["citation"], "heading": row.get("heading") or "", "text": row["text"],
        "jurisdiction": jurisdiction, "kind": "statute", "status": "effective",
        "path": row.get("path") or "", "level": "",
    }
    return {
        "skill_id": "zenas.retrieve",
        "input": {"citation": row["citation"], "jurisdiction": jurisdiction, "corpus": [passage]},
        "expected": {"count": 1, "citations": [row["citation"]], "passages": [passage]},
        "label_source": f"statute_section:{row['source_id']}:{row['version_id']}:{row.get('path') or ''}",
        "region": region,
        "public": True,
    }


async def candidates(pool: Any, *, region: str, limit: int = 200) -> list[dict[str, Any]]:
    if region not in {"za", "us-east"}:
        raise ValueError("wrong region")
    limit = max(0, min(limit, 200))
    if not limit:
        return []
    jurisdiction = "za" if region == "za" else "us"
    sources = [item.source_id for item in CATALOGUE if item.region == region]
    async with pool.acquire() as conn:
        cases = await conn.fetch(
            """
            SELECT w.*, d.text, d.source_id, d.title, d.docket_number, d.nature_of_suit
            FROM agent_zenas.worked_matters w
            JOIN zenas_pool.documents d ON d.version_id = w.pool_version_id
              AND d.document_id = w.pool_doc_id AND d.jurisdiction = w.jurisdiction
            WHERE w.region = $1 AND w.jurisdiction = $2 AND w.tenant_id IS NULL
              AND w.source = 'case' AND w.material_type = 'public_record'
              AND d.kind = 'case' AND d.source_id = ANY($3::text[])
              AND d.effective_to IS NULL AND d.status IS DISTINCT FROM 'superseded'
            ORDER BY row_number() OVER (PARTITION BY w.holdout ORDER BY w.id), w.holdout LIMIT $4
            """,
            region, jurisdiction, sorted(COURT_SOURCES), limit,
        )
        sections = await conn.fetch(
            """
            SELECT c.*, d.source_id, d.kind, d.title
            FROM zenas_pool.chunks c JOIN zenas_pool.documents d ON d.version_id = c.version_id
            WHERE c.jurisdiction = $1 AND d.jurisdiction = $1
              AND d.source_id = ANY($2::text[]) AND d.kind = 'statute'
              AND d.effective_to IS NULL AND d.status IS DISTINCT FROM 'superseded'
            ORDER BY c.chunk_id LIMIT $3
            """,
            jurisdiction, sources, limit,
        )
    worked = [candidate for row in cases if (candidate := case_candidate(dict(row), region)) is not None]
    statutes = [candidate for row in sections if (candidate := statute_candidate(dict(row), region)) is not None]
    result = []
    for index in range(max(len(worked), len(statutes))):
        if index < len(worked):
            result.append(worked[index])
        if index < len(statutes):
            result.append(statutes[index])
    return result[:limit]
