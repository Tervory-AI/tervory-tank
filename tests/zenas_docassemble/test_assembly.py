"""Word-for-word parity against main, with Docassemble's API stubbed offline."""
from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import AsyncMock
from xml.etree import ElementTree
from zipfile import ZipFile

import httpx
import pytest
import yaml

from agents.zenas.core.docassemble import AssemblyUnavailable, DocassembleClient
from agents.zenas.core.drafting import TEMPLATES
from agents.zenas.core.docx_redline import docx_bytes
from agents.zenas.core.ladder_store import LadderMemory
from agents.zenas.core.service import _LEGAL_NOTICE, _with_legal_notice, draft_contract
from agents.zenas.core.store import MemoryStore
from . import legacy_drafting
from .api_stub import API, PACKAGE, assembly, install

ROOT = Path(__file__).resolve().parents[2]
TENANT = "00000000-0000-0000-0000-000000000011"


@pytest.fixture
def api(monkeypatch):
    return install(monkeypatch)


def clauses_for(region, template):
    # Offline clause inputs only. No test clause is installed or shipped to a room.
    jurisdiction = "za" if region == "za" else "us"
    return [{"id": slot, "region": region, "jurisdiction": jurisdiction,
             "status": "lawyer_approved", "template": template, "kind": slot,
             "text": slot + ": {party} agrees {term} for {amount}. {party}"}
            for slot in TEMPLATES[template]]


def word_text(data):
    with ZipFile(BytesIO(data)) as package:
        xml = ElementTree.fromstring(package.read("word/document.xml"))
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in xml.iter(ns + "p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == ns + "t":
                parts.append(node.text or "")
            elif node.tag == ns + "br":
                parts.append("\n")
            elif node.tag == ns + "tab":
                parts.append("\t")
        paragraphs.append("".join(parts))
    return "\n\n".join(paragraphs)


@pytest.mark.asyncio
@pytest.mark.parametrize("region", ["us-east", "za"])
@pytest.mark.parametrize("template", list(TEMPLATES))
@pytest.mark.parametrize("variant", ["complete", "missing", "empty", "literal_template_syntax", "no_clause"])
async def test_every_template_matches_main_word_for_word(api, region, template, variant):
    rows = clauses_for(region, template)
    terms = {"party": "A & B <Civil>", "term": "two years", "amount": 2500}
    if variant == "missing":
        del terms["amount"]
    elif variant == "empty":
        terms["party"] = ""
    elif variant == "literal_template_syntax":
        terms["party"] = "${7 * 7} {{7 * 7}} <% raise Exception() %>"
        rows[0]["text"] += " ${7 * 7} {{7 * 7}} <% raise Exception() %>"
    elif variant == "no_clause":
        rows.pop()
    expected = legacy_drafting.assemble_draft(template=template, clauses=rows, terms=terms)
    jurisdiction = "za" if region == "za" else "us"
    store, ladder = MemoryStore(), LadderMemory()
    await store.register_tenant(TENANT, region)
    await ladder.register_tenant(TENANT, region)
    for row in rows:
        await store.add_clause(row)
    model = AsyncMock()
    result = await draft_contract(store, ladder, model, tenant_id=TENANT, home_region=region,
                                  box_region=region, jurisdiction=jurisdiction, template=template,
                                  narrative="A civil contract.", terms=terms)
    assert result["text"] == _with_legal_notice(expected["text"])
    for key in ("library", "review", "reused"):
        assert result[key] == expected[key]
    # IDs are assigned by the store. All wording, slot order and review metadata match.
    for actual, old in zip(result["sentences"], expected["sentences"], strict=True):
        assert {k: v for k, v in actual.items() if k != "clause_id"} == {k: v for k, v in old.items() if k != "clause_id"}
    blocks = [[{"kind": "ins" if row["review"] else "plain", "text": row["text"]}]
              for row in expected["sentences"]] + [[{"kind": "plain", "text": _LEGAL_NOTICE}]]
    assert word_text(base64.b64decode(result["docx_base64"])) == word_text(docx_bytes(blocks))
    assert result["model_calls"] == 0
    model.model.assert_not_awaited()
    assert [r.url.path for r in api[0].requests] == [
        "/api/session/new", "/api/session", "/api/session/new", "/api/session", "/api/file/1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("region,jurisdiction", [("us-east", "za"), ("za", "us")])
async def test_cross_region_refused_before_docassemble_or_model(api, region, jurisdiction):
    store = MemoryStore()
    await store.register_tenant(TENANT, region)
    model = AsyncMock()
    result = await draft_contract(store, None, model, tenant_id=TENANT, home_region=region,
                                  box_region=region, jurisdiction=jurisdiction, template="nda",
                                  narrative="A civil NDA.")
    assert not result["ok"]
    assert api == []
    model.model.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["Draft a plea bargain for criminal charges.",
                                      "Prepare a bail application under the Criminal Procedure Act 51 of 1977."])
async def test_criminal_refusal_unchanged_before_assembly(api, question):
    store = MemoryStore()
    await store.register_tenant(TENANT, "za")
    result = await draft_contract(store, None, AsyncMock(), tenant_id=TENANT, home_region="za",
                                  box_region="za", jurisdiction="za", template="nda", narrative=question)
    assert not result["ok"]
    assert result["reason"] == "Refused. Zenas does not do criminal law. Ask a criminal lawyer in that jurisdiction."
    assert not api and not store.documents


@pytest.mark.asyncio
async def test_foreign_clause_and_remote_host_rejected_before_http(monkeypatch):
    install(monkeypatch)
    api = API("us-east")
    client = DocassembleClient("us-east", transport=httpx.MockTransport(api.handle))
    args = {"template": "nda", "jurisdiction": "us", "terms": {}, "prior": None}
    with pytest.raises(AssemblyUnavailable):
        await client.assemble(**args, clauses=clauses_for("za", "nda"))
    assert not api.requests
    monkeypatch.setenv("DOCASSEMBLE_URL", "https://example.org")
    with pytest.raises(AssemblyUnavailable):
        await client.assemble(**args, clauses=[])
    assert not api.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 401, 500])
async def test_api_failure_never_falls_back_to_local_assembly(monkeypatch, status):
    install(monkeypatch)
    requests = []
    def reject(request):
        requests.append(request)
        return httpx.Response(status, headers={"location": "https://example.org"})
    client = DocassembleClient("za", transport=httpx.MockTransport(reject))
    with pytest.raises(AssemblyUnavailable):
        await client.assemble(template="nda", jurisdiction="za", clauses=[], terms={}, prior=None)
    assert len(requests) == 1


def test_server_independently_rejects_za_on_boston(monkeypatch):
    monkeypatch.setenv("TANK_REGION", "us-east")
    request = {"region": "za", "jurisdiction": "za", "template": "nda", "clauses": clauses_for("za", "nda")}
    with pytest.raises(ValueError):
        assembly.prepare(request, "za", "nda")


def test_interviews_have_explicit_jurisdiction_and_no_new_copy():
    for jurisdiction in ("us", "za"):
        for template, slots in TEMPLATES.items():
            path = ROOT / "agents/zenas/docassemble" / jurisdiction / (template + ".yml")
            blocks = list(yaml.safe_load_all(path.read_text()))
            assert blocks[0] == {"initial": True, "code": f'assembly_jurisdiction = "{jurisdiction}"\nassembly_template = "{template}"\n'}
            assert blocks[1] == {"include": ["docassemble.zenas:data/questions/assembly.yml"]}
            markdown = (PACKAGE / "data/templates" / (template + ".md")).read_text()
            assert markdown == "\n\n".join('${ paragraphs[' + repr(slot) + '] }' for slot in slots)


@pytest.mark.asyncio
async def test_trigger_legal_handoff_reaches_docassemble_with_notice(api, monkeypatch):
    import command
    import sys
    from types import SimpleNamespace
    import trigger_routes
    from fastapi import FastAPI
    from uuid import UUID
    store, ladder = MemoryStore(), LadderMemory()
    await store.register_tenant(TENANT, "za")
    await ladder.register_tenant(TENANT, "za")
    for row in clauses_for("za", "nda"):
        await store.add_clause(row)
    app = FastAPI()
    @app.post("/v1/zenas/drafts", status_code=201)
    async def drafts(body: dict):
        return await draft_contract(store, ladder, None, box_region="za", **body)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(app=app, box_region=lambda: "za", TANK_API_KEY="TANK_API_KEY"))
    response = await trigger_routes.zenas_draft(
        {"template": "nda", "jurisdiction": "za", "text": "Draft a civil NDA.",
         "terms": {"party": "A", "term": "two years", "amount": 2500}},
        command.Actor(UUID(TENANT), "founder", True))
    result = json.loads(response.body)
    assert response.status_code == 201
    assert result["text"].endswith(_LEGAL_NOTICE)
    assert result["notice"] == "legal information, not legal advice"
    assert result["model_calls"] == 0 and result["review"] == []
    assert api and api[0].files


@pytest.mark.asyncio
async def test_postgres_prior_metadata_is_not_sent_and_reuse_stays_exact(monkeypatch):
    from datetime import datetime, timezone
    from uuid import UUID
    install(monkeypatch)
    stub = API("za")
    client = DocassembleClient("za", transport=httpx.MockTransport(stub.handle))
    prior = {"id": UUID(TENANT), "tenant_id": UUID(TENANT), "created_at": datetime.now(timezone.utc),
             "region": "za", "jurisdiction": "za", "source": "released",
             "fact_pattern": {"template": "nda", "features": {"term": "two years"},
                              "text": "Released NDA."}}
    result = await client.assemble(template="nda", jurisdiction="za", clauses=[],
                                   terms={"term": "two years"}, prior=prior)
    assert result["reused"] and result["text"] == "Released NDA."
    sent = json.loads(stub.requests[1].content)["variables"]["request"]["prior"]
    assert set(sent) == {"region", "jurisdiction", "source", "fact_pattern"}
    assert sent["fact_pattern"] == prior["fact_pattern"]


@pytest.mark.asyncio
async def test_missing_api_setting_stops_without_sending_or_storing_a_document(monkeypatch):
    install(monkeypatch)
    monkeypatch.delenv("DOCASSEMBLE_API_KEY")
    stub = API("za")
    client = DocassembleClient("za", transport=httpx.MockTransport(stub.handle))
    with pytest.raises(AssemblyUnavailable):
        await client.assemble(template="nda", jurisdiction="za", clauses=[], terms={}, prior=None)
    assert not stub.requests
