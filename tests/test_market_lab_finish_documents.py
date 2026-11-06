"""Promised Word ingestion uses the existing private evidence and guard paths."""
import io
import sys
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/market_lab'))
from core.document_read import extract, ReadError
from core.documents import accept, forget
from core.evidence import answer, document_page
from core.ledger import MemoryLedger


def word(*, value='110'):
    from docx import Document
    document = Document()
    document.add_paragraph('Warehouse inventory was counted in September 2026.')
    table = document.add_table(rows=3, cols=4)
    for row, values in zip(table.rows, [('date','value','unit','series'),
                                       ('2026-09-01','100','cartons','inventory'),
                                       ('2026-09-08',value,'cartons','inventory')]):
        for cell, text in zip(row.cells, values): cell.text = text
    stream = io.BytesIO();document.save(stream)
    return stream.getvalue()


@pytest.mark.asyncio
async def test_word_sources_tables_guard_and_forget():
    tenant, other, ident = (str(uuid4()) for _ in range(3))
    ledger = MemoryLedger()
    parsed = extract('history.docx', word())
    assert parsed['pages'] is None  # DOCX does not supply reliable pagination.
    assert parsed['rows'] == 2 and len(parsed['tables']) == 2
    record = await accept(ledger, tenant, ident, 'history.docx', parsed, region='us-east')
    assert record['status'] == 'learned'
    assert len(ledger.points_for(tenant)) == 2
    response = await answer(ledger, tenant, 'warehouse inventory')
    assert response['facts'] and response['facts'][0]['name'] == 'history.docx · Paragraph 1'
    assert (await document_page(ledger, tenant, ident, row=0))['passages'][0]['page'] is None
    assert await document_page(ledger, other, ident) is None
    await forget(ledger, tenant, ident)
    assert not ledger.points_for(tenant)
    assert not (await answer(ledger, tenant, 'warehouse inventory'))['facts']
    await accept(ledger, tenant, str(uuid4()), 'spike.docx', extract('spike.docx', word(value='10000')), region='us-east')
    assert not ledger.points_for(tenant)


@pytest.mark.parametrize('raw', [b'not a document', b'<!DOCTYPE x>'])
def test_invalid_word_reports_existing_safe_reason(raw):
    with pytest.raises(ReadError, match='This file could not be read'):
        extract('bad.docx', raw)


def test_word_never_resolves_external_relationships_and_rejects_entities():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('word/document.xml', '<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x/>')
    with pytest.raises(ReadError, match='This file could not be read'):
        extract('external.docx', data.getvalue())


@pytest.mark.asyncio
async def test_room_upload_replay_failure_and_immutable_original(monkeypatch):
    from contextlib import asynccontextmanager
    import json
    from unittest.mock import AsyncMock
    import httpx
    from fastapi import FastAPI
    from core import document_http

    saved, objects, puts = {}, {}, []
    class Connection:
        @asynccontextmanager
        async def transaction(self): yield
        async def execute(self, query, *args):
            if 'INSERT INTO agent_market_lab.uploaded_files' in query:
                saved[(str(args[0]), str(args[1]))] = json.loads(args[2])
        async def fetch(self, query, *args):
            return [{'content': doc} for (owner, ident), doc in saved.items()
                    if owner == str(args[0]) and (args[1] is None or ident == str(args[1]))]
    class Ledger:
        conn = Connection()
    @asynccontextmanager
    async def ledger(): yield Ledger()
    class Storage:
        region = 'us-east'
        async def put(self, tenant, category, ident, body):
            objects[(tenant, ident)] = body; puts.append((tenant, ident))
        async def close(self): pass
    async def accepted(ledger, tenant, ident, name, parsed, **kwargs):
        return {'id': ident, 'name': name, 'status': 'learned', 'reason': '', 'rows': parsed['rows'],
                'pages': parsed['pages'], 'passages': parsed['passages']}
    monkeypatch.setattr(document_http, 'Storage', lambda room: Storage())
    monkeypatch.setattr(document_http, 'accept', AsyncMock(side_effect=accepted))
    app = FastAPI(); app.include_router(document_http.build_router(key_ok=lambda key:key=='placeholder-room', ledger_context=ledger))
    tenant, ident, other = (str(uuid4()) for _ in range(3))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://room') as client:
        url = f'/market/files/{ident}?tenant_id={tenant}&name=history.docx'
        original = word()
        assert (await client.put(url, content=original)).status_code == 401
        headers = {'X-Tank-Key':'placeholder-room'}
        for _ in range(2):
            response = await client.put(url, content=original, headers=headers)
            assert response.status_code == 200 and response.json()['status'] == 'learned'
        assert puts == [(tenant, ident)]
        assert (await client.put(url, content=b'corrupt replacement', headers=headers)).status_code == 409
        assert objects[(tenant, ident)] == original
        assert saved[(tenant,ident)]['status'] == 'learned'
        failed = await client.put(f'/market/files/{ident}?tenant_id={other}&name=bad.docx', content=b'bad', headers=headers)
        assert failed.status_code == 200 and failed.json()['status'] == 'failed'
        assert saved[(other,ident)]['passages'] == []
        assert saved[(tenant,ident)]['passages']
