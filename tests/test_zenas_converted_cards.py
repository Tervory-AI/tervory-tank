import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.zenas.core.converted_cards import link_card
from agents.zenas.core.ladder_store import LadderMemory
from agents.zenas.core.selftest import run_selftest


LAW = "A supply agreement requires a written offer and acceptance."


class Pool:
    def __init__(self, region):
        self.home_region = region
        self.queries = []

    async def search_text(self, query, **kwargs):
        self.queries.append(kwargs)
        if kwargs["kind"] != "statute":
            return []
        return [SimpleNamespace(
            chunk_id="section", document_id="statute", version_id="v1",
            citation="Civil statute section 1", heading="Supply", text=LAW,
            path="1", jurisdiction=kwargs["jurisdiction"],
        )]


class Model:
    def __init__(self):
        self.calls = []

    async def complete(self, messages, *, task_type, provider):
        self.calls.append((task_type, messages))
        return json.dumps({"elements": [{
            "id": "written", "test": "Written agreement",
            "citation": "Civil statute section 1", "quote": LAW,
        }], "decision_table": []})


@pytest.mark.asyncio
@pytest.mark.parametrize("region,jurisdiction", [("za", "za"), ("us-east", "us")])
async def test_converted_holdout_gets_law_only_card_and_reuses_it(region, jurisdiction):
    ladder = LadderMemory()
    row = await ladder.add_worked({
        "region": region, "jurisdiction": jurisdiction, "source": "case", "tenant_id": None,
        "material_type": "public_record", "fact_pattern": {
            "facts": "PRIVATE-TO-EVALUATION facts about a supply agreement",
            "question": "Was the supply agreement binding?",
        }, "holdout": True, "pool_doc_id": "case1",
        "element_findings": [{"element_id": "written", "finding": "met"}],
        "outcome": "met",
    })
    pool, model = Pool(region), Model()
    assert await link_card(pool, ladder, model, row, region=region)
    assert row["rule_card_ids"]
    assert row["area"] == "contracts"
    assert len(model.calls) == 1
    assert model.calls[0][0] == "zenas.rule_card"
    assert "legal elements for supply agreement" in str(model.calls)
    assert "PRIVATE-TO-EVALUATION" not in str(model.calls)
    assert all(item["jurisdiction"] == jurisdiction for item in pool.queries)
    assert await link_card(pool, ladder, model, row, region=region)
    assert len(model.calls) == 1
    scores = await run_selftest(ladder, region=region)
    assert "no rule card" not in str(scores)
    assert ladder.rule_cards[0]["status"] == "draft"


@pytest.mark.asyncio
async def test_private_criminal_and_other_region_never_build():
    ladder, model = LadderMemory(), Model()
    row = {
        "id": "case", "region": "za", "jurisdiction": "za", "source": "case",
        "tenant_id": None, "material_type": "public_record",
        "fact_pattern": {"facts": "criminal prosecution of a supply agreement"},
    }
    assert not await link_card(Pool("za"), ladder, model, row, region="za")
    row["fact_pattern"] = {"facts": "supply agreement"}
    assert not await link_card(Pool("us-east"), ladder, model, row, region="za")
    row["tenant_id"] = "private"
    assert not await link_card(Pool("za"), ladder, model, row, region="za")
    assert model.calls == []
