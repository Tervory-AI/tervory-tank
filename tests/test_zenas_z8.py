"""Z8: decided cases become worked matters, one region at a time.

Cite-check must pass. One stable fifth is held out. A US run does not read an
SA case, and the reverse.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.zenas.core.convert import convert_cases, convert_limit, conversion_report  # noqa: E402
from agents.zenas.core.ladder_store import LadderMemory  # noqa: E402
from agents.zenas.core.selftest import is_holdout  # noqa: E402

_QUOTE = re.compile(r"The court stated fact number \d+ for this sale of goods\.")


class Doc:
    def __init__(
        self,
        *,
        id: str,
        jurisdiction: str,
        citation: str,
        text: str,
        kind: str = "case",
        status: str = "in_force",
        effective_to: object = None,
        source_id: str = "cap",
    ) -> None:
        self.id = id
        self.jurisdiction = jurisdiction
        self.citation = citation
        self._text = text
        self.kind = kind
        self.status = status
        self.effective_to = effective_to
        self.source_id = source_id
        self.version_id = f"v-{id}"
        self.title = id
        self.text_reads = 0

    @property
    def text(self) -> str:
        self.text_reads += 1
        return self._text


class Pool:
    def __init__(self, docs: list[Doc], home_region: str | None = None) -> None:
        self.docs = {doc.id: doc for doc in docs}
        self.home_region = home_region


class Model:
    def __init__(self, mode: str = "good") -> None:
        self.mode = mode
        self.calls: list[dict[str, str]] = []
        self.prompts: list[str] = []

    async def complete(self, messages: list[dict[str, str]], *, task_type: str, provider: str) -> str:
        self.calls.append({"task_type": task_type, "provider": provider})
        text = messages[-1]["content"]
        self.prompts.append(text)
        citation = ""
        for line in text.splitlines():
            if line.startswith("Citation: "):
                citation = line[len("Citation: ") :]
                break
        if self.mode == "bad":
            quote = "This sentence is not in the judgment."
            # Keep this case's citation so the failure is the quote, not a foreign cite.
        else:
            found = _QUOTE.search(text)
            quote = found.group(0) if found else ""
        return json.dumps(
            {
                "facts": quote,
                "question": "Was the sale of goods complete?",
                "elements": [{"element_id": "sale", "finding": "met", "quote": quote}],
                "holding": "met",
                "citations": [{"citation": citation, "quote": quote}],
            }
        )


def _case(doc_id: str, jurisdiction: str, *, kind: str = "case") -> Doc:
    quote = f"The court stated fact number {doc_id[-4:]} for this sale of goods."
    prefix = "US" if jurisdiction == "us" else "SA"
    return Doc(
        id=doc_id,
        jurisdiction=jurisdiction,
        citation=f"{doc_id[-4:]} F.2d 1",
        text=f"Opinion. {quote} TAIL-{prefix}-NOT-STORED.",
        kind=kind,
        source_id="cap" if jurisdiction == "us" else "concourt",
    )


def _ids(n: int) -> list[str]:
    return [f"case-{i:04d}" for i in range(n)]


@pytest.mark.asyncio
async def test_fixture_cases_become_worked_matters_with_about_one_in_five_held_out() -> None:
    ids = _ids(100)
    docs = [_case(doc_id, "us") for doc_id in ids]
    pool = Pool(docs, home_region="us-east")
    ladder = LadderMemory()
    model = Model()
    report = await convert_cases(pool, ladder, model, region="us-east")
    assert report["ok"] is True
    assert report["decided"] == 100
    assert report["converted"] == 100
    assert report["failed"] == 0
    expected = sum(is_holdout(doc_id) for doc_id in ids)
    assert report["held_out"] == expected
    assert 0.15 <= expected / len(ids) <= 0.25
    assert all(call["task_type"] == "zenas.case_facts" for call in model.calls)
    assert len(model.calls) == 100
    for row in ladder.worked:
        assert row["holdout"] is is_holdout(row["pool_doc_id"])
        assert row["jurisdiction"] == "us"
        assert row["region"] == "us-east"
        assert row["material_type"] == "public_record"
        pattern = row["fact_pattern"]
        assert pattern["facts"].startswith("The court stated fact")
        assert pattern["question"]
        assert pattern["citation"].endswith("F.2d 1")
        assert "TAIL-US-NOT-STORED" not in json.dumps(row)
        pairs = [pair for pair in ladder.pairs if pair.get("worked_id") == row["id"]]
        if row["holdout"]:
            assert pairs == []
        else:
            assert len(pairs) == 1
            assert pairs[0]["memo"] == pattern["facts"]
            assert "TAIL-US-NOT-STORED" not in pairs[0]["memo"]
    again = Model()
    second = await convert_cases(pool, ladder, again, region="us-east")
    assert second["converted"] == 100
    assert again.calls == []
    assert all(doc.text_reads == 1 for doc in docs)


@pytest.mark.asyncio
async def test_a_failed_cite_check_is_not_stored_and_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENAS_CONVERT_MAX", "200")
    doc = _case("case-0007", "us")
    pool = Pool([doc], home_region="us-east")
    ladder = LadderMemory()
    bad = Model("bad")
    report = await convert_cases(pool, ladder, bad, region="us-east")
    assert report["converted"] == 0
    assert report["failed"] == 1
    assert ladder.worked == []
    assert ladder.failures[0]["reason"] == "quote is not in the judgment"
    assert "TAIL-US-NOT-STORED" not in ladder.failures[0]["reason"]
    good = Model()
    retried = await convert_cases(pool, ladder, good, region="us-east")
    assert retried["converted"] == 1
    assert retried["failed"] == 0
    assert len(good.calls) == 1
    assert ladder.worked[0]["pool_doc_id"] == "case-0007"


@pytest.mark.asyncio
async def test_us_conversion_never_reads_an_sa_case_and_the_reverse() -> None:
    us_docs = [_case(f"us-{i:04d}", "us") for i in range(3)]
    sa_docs = [_case(f"za-{i:04d}", "za") for i in range(3)]
    statute = _case("statute-0001", "us", kind="statute")
    us_pool = Pool(us_docs + sa_docs + [statute], home_region="us-east")
    us_ladder = LadderMemory()
    us_model = Model()
    us = await convert_cases(us_pool, us_ladder, us_model, region="us-east")
    assert us["decided"] == 3
    assert us["converted"] == 3
    assert {row["jurisdiction"] for row in us_ladder.worked} == {"us"}
    assert all(doc.text_reads == 0 for doc in sa_docs)
    assert statute.text_reads == 0
    assert us_model.prompts
    assert all("TAIL-SA-NOT-STORED" not in prompt for prompt in us_model.prompts)
    assert all(doc.text_reads == 1 for doc in us_docs)

    fresh_us = [_case(f"us-{i:04d}", "us") for i in range(1)]
    fresh_sa = [_case(f"za-{i:04d}", "za") for i in range(3)]
    za_pool = Pool(fresh_us + fresh_sa, home_region="za")
    za_ladder = LadderMemory()
    za_model = Model()
    za = await convert_cases(za_pool, za_ladder, za_model, region="za")
    assert za["decided"] == 3
    assert za["converted"] == 3
    assert {row["jurisdiction"] for row in za_ladder.worked} == {"za"}
    assert fresh_us[0].text_reads == 0
    assert all(doc.text_reads == 1 for doc in fresh_sa)
    assert all("TAIL-US-NOT-STORED" not in prompt for prompt in za_model.prompts)
    assert all("TAIL-US-NOT-STORED" not in json.dumps(row) for row in za_ladder.worked)

    crossed = Pool(us_docs + sa_docs, home_region="us-east")
    for doc in us_docs + sa_docs:
        doc.text_reads = 0
    refused = await convert_cases(crossed, LadderMemory(), Model(), region="za")
    assert refused["ok"] is False
    assert refused["reason"] == "wrong region"
    assert all(doc.text_reads == 0 for doc in us_docs + sa_docs)


@pytest.mark.asyncio
async def test_sql_list_asks_only_for_this_regions_jurisdiction() -> None:
    class Conn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[object, ...]]] = []

        async def fetch(self, sql: str, *args: object) -> list[dict[str, str]]:
            self.calls.append((sql, args))
            selected = sql.lower().split("from", 1)[0]
            assert "text" not in selected
            assert "kind = 'case'" in sql
            return []

        async def fetchrow(self, sql: str, *args: object) -> None:
            raise AssertionError(sql)

    class SqlPool:
        def __init__(self) -> None:
            self._conn = Conn()
            self.home_region = None

    us = SqlPool()
    await conversion_report(us, LadderMemory(), region="us-east")
    assert us._conn.calls[0][1] == ("us",)
    za = SqlPool()
    await conversion_report(za, LadderMemory(), region="za")
    assert za._conn.calls[0][1] == ("za",)


@pytest.mark.asyncio
async def test_criminal_case_is_not_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZENAS_CONVERT_MAX", raising=False)
    doc = Doc(
        id="crime-0001",
        jurisdiction="us",
        citation="9 F.2d 9",
        text="The accused faced a criminal charge. The court stated fact number 0001 for this sale of goods.",
    )
    report = await convert_cases(Pool([doc], home_region="us-east"), LadderMemory(), Model(), region="us-east")
    assert report["converted"] == 0
    assert report["failed"] == 1
    assert doc.text_reads == 1


def test_convert_limit_defaults_to_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZENAS_CONVERT_MAX", raising=False)
    assert convert_limit() == 200
    monkeypatch.setenv("ZENAS_CONVERT_MAX", "2")
    assert convert_limit() == 2
    monkeypatch.setenv("ZENAS_CONVERT_MAX", "nope")
    assert convert_limit() == 200


@pytest.mark.asyncio
async def test_cap_stops_at_n_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENAS_CONVERT_MAX", "2")
    docs = [_case(doc_id, "za") for doc_id in _ids(5)]
    report = await convert_cases(Pool(docs, home_region="za"), LadderMemory(), Model(), region="za")
    assert report["decided"] == 5
    assert report["converted"] == 2
    assert sum(doc.text_reads for doc in docs) == 2
    assert docs[0].text_reads == 1 and docs[1].text_reads == 1
    assert all(doc.text_reads == 0 for doc in docs[2:])


def test_nightly_converts_after_the_pool_load_and_before_the_self_test() -> None:
    text = (ROOT / "agents" / "zenas" / "pool" / "nightly.py").read_text(encoding="utf-8")
    main = text.split("async def _main", 1)[1]
    assert main.index("await run_nightly") < main.index("await convert_scheduled") < main.index("await run_scheduled")
    job = (ROOT / "agents" / "zenas" / "core" / "convert.py").read_text(encoding="utf-8")
    assert 'task_type="zenas.case_facts"' in job
    assert "os.nice(19)" in job
    assert "ZENAS_CONVERT_MAX" in job


def test_feeds_page_has_a_convert_button_per_region() -> None:
    board = (ROOT / "workspace" / "app" / "zenas" / "feeds" / "board.tsx").read_text(encoding="utf-8")
    route = (ROOT / "workspace" / "app" / "api" / "zenas" / "feeds" / "region" / "convert" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "Convert cases" in board
    assert "decided cases loaded" in board
    assert "held out" in board
    assert "failed" in board
    assert "zenasIn" in route
    assert "publicConvert" in route
    assert "matter_id" not in route
    assert "tenant_id" not in route
    assert "JUDGMENT" not in route
