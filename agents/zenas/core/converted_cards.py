"""Attach law-only rule cards to public converted matters in this region."""

from __future__ import annotations

from typing import Any
import hashlib
import json

from agents.zenas.core.engine import cite_check
from agents.zenas.core.scope_rules import classify, load_config
from agents.zenas.core.service import _passages_from_pool, build_rule_card

PLATFORM = "00000000-0000-0000-0000-000000000001"


async def link_card(pool: Any, ladder: Any, model: Any, worked: dict[str, Any], *, region: str) -> bool:
    jurisdiction = "za" if region == "za" else "us"
    if (
        region not in {"za", "us-east"}
        or worked.get("region") != region
        or worked.get("jurisdiction") != jurisdiction
        or worked.get("source") != "case"
        or worked.get("material_type") != "public_record"
        or worked.get("tenant_id") is not None
        or getattr(pool, "home_region", region) not in {None, region}
    ):
        return False
    pattern = worked.get("fact_pattern") or {}
    facts = str(pattern.get("question") or "") + " " + str(pattern.get("facts") or pattern.get("narrative") or "")
    scope = classify(facts, jurisdiction)
    if not scope.get("in_scope") or scope.get("criminal"):
        return False
    area = str(scope["area"])
    config = load_config()
    topic = next((
        phrase for item in config["allowed"] + config["regulatory"]
        for phrase in item["phrases"] if phrase.casefold() in facts.casefold()
        and (item["id"] == area or area == "regulatory_compliance")
    ), area.replace("_", " "))
    passages = []
    for kind in ("statute", "court_rule"):
        passages.extend(await _passages_from_pool(
            pool, query=topic, citation="", jurisdiction=jurisdiction,
            as_at=worked.get("as_at"), level=None, kind=kind,
        ))
    passages = [
        passage for passage in passages
        if passage.get("jurisdiction") == jurisdiction and passage.get("kind") in {"statute", "court_rule"}
    ]
    if not passages:
        return False
    registered = await ladder.register_tenant(PLATFORM, region)
    if not registered.get("ok"):
        return False
    source_versions = {(str(item["doc_id"]), str(item["version_id"])) for item in passages}
    version_key = hashlib.sha256(json.dumps(sorted(source_versions)).encode()).hexdigest()[:12]
    question = f"What are the legal elements for {topic} in {jurisdiction}? Source set {version_key}."
    for card in await ladder.list_cards(region=region):
        if (
            card.get("tenant_id") is None and card.get("jurisdiction") == jurisdiction
            and card.get("question") == question and card.get("status") != "stale"
            and card.get("elements")
            and {(str(item.get("doc_id")), str(item.get("version_id"))) for item in card.get("sources") or []}
            <= source_versions
        ):
            checked = cite_check(card["elements"], passages)
            if checked.get("passed"):
                return await ladder.link_worked_card(
                    region=region, worked_id=str(worked["id"]), card_id=str(card["id"]), area=area,
                )
    result = await build_rule_card(
        ladder, None, model, tenant_id=PLATFORM, home_region=region, box_region=region,
        jurisdiction=jurisdiction, question=question, passages=passages, as_at=worked.get("as_at"),
    )
    if not result.get("ok"):
        return False
    card = result["rule_card"]
    if not card.get("elements") or not cite_check(card["elements"], passages).get("passed"):
        return False
    return await ladder.link_worked_card(
        region=region, worked_id=str(worked["id"]), card_id=str(card["id"]), area=area,
    )
