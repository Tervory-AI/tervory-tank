import json

import pytest

from agents.zenas.core.convert import convert_cases
from agents.zenas.core.ladder_store import LadderMemory
from agents.zenas.core.pointers import PointerError, judgment_text, resolve_pointer
from test_zenas_z8c import Answer, Doc, Pool


FACTS = (
    "The supplier delivered the goods to the buyer under their written agreement. "
    "The buyer accepted delivery and retained the goods without raising any objection. "
    "Payment remained outstanding despite repeated written demands from the supplier."
)


@pytest.mark.asyncio
async def test_pointers_extract_stored_passages_and_report_unresolved():
    text = f"[1] {FACTS}\nFootnote 1: An interleaved reference.\n\n[2] The buyer must pay."
    pool = Pool(Doc(text, doc_id="civil", citation="Civil 1", title="Supplier v Buyer", source_id="saflii"))
    for pointer, reason in (({"paragraphs": [1]}, ""), ({"paragraphs": [99]}, "pointer did not resolve"), ({"paragraphs": [2]}, "facts too short")):
        body = {
            "facts_pointer": pointer,
            "question": "Was payment due?",
            "holding": "Payment was due.",
            "elements": [{"element_id": "payment", "finding": "met", "quote_pointer": {"paragraphs": [2]}}],
        }
        ladder = LadderMemory()
        result = await convert_cases(pool, ladder, Answer(json.dumps(body)), region="za")
        if reason:
            assert result["failures"] == [{"reason": reason, "count": 1}]
        else:
            assert result["converted"] == 1
            assert "interleaved" not in str(ladder.worked)
            assert FACTS in str(ladder.worked)


def test_word_boundaries_ambiguity_and_reversed_pointers():
    words = FACTS.split()
    pointer = {"first": " ".join(words[:8]), "last": " ".join(words[-8:])}
    assert resolve_pointer(pointer, FACTS) == FACTS
    for source in (FACTS + FACTS, " ".join(words[-8:] + words[:8])):
        with pytest.raises(PointerError, match="pointer did not resolve"):
            resolve_pointer(pointer, source)
    with pytest.raises(PointerError):
        resolve_pointer({"paragraphs": [True]}, "[1] text")
    assert judgment_text("[1] Facts.\nFootnote 1: Reference.\n\n[2] Holding.") == "[1] Facts.\n\n\n[2] Holding."
