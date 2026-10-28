"""No services or model: actual parsers, guard, answer matching and deletion."""
import io
import sys
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from core.document_read import extract, ReadError
from core.documents import accept, forget
from core.evidence import answer, document_page
from core.ledger import MemoryLedger


def report_pdf():
    from reportlab.pdfgen import canvas
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(72, 750, 'Harbor market report')
    pdf.showPage()
    pdf.drawString(72, 750, 'Warehouse inventory fell to 14474 cartons in September 2026.')
    pdf.save()
    return stream.getvalue()


def spreadsheet(rows):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        cells = ''.join('<row>' + ''.join(f'<c r="{chr(65+j)}{i+1}" t="inlineStr"><is><t>{escape(value)}</t></is></c>' for j, value in enumerate(row)) + '</row>' for i, row in enumerate(rows))
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + cells + '</sheetData></worksheet>')
    return out.getvalue()


@pytest.mark.asyncio
async def test_pdf_answer_page_and_forget_isolated():
    ledger = MemoryLedger()
    owner, other, ident = (str(uuid.uuid4()) for _ in range(3))
    parsed = extract('report.pdf', report_pdf())
    assert parsed['pages'] == 2
    await accept(ledger, owner, ident, 'report.pdf', parsed, region='us-east')
    response = await answer(ledger, owner, 'What was warehouse inventory?')
    assert len(response['facts']) == 1
    fact = response['facts'][0]
    assert '14474' in fact['text'] and fact['name'] == 'report.pdf · Page 2'
    page = await document_page(ledger, owner, ident, row=1)
    assert page['passages'][1]['page'] == 2
    assert await document_page(ledger, other, ident) is None
    assert not (await answer(ledger, other, 'warehouse inventory'))['facts']
    await forget(ledger, other, ident)
    assert (await answer(ledger, owner, 'warehouse inventory'))['facts']
    await forget(ledger, owner, ident)
    assert not (await answer(ledger, owner, 'warehouse inventory'))['facts']
    assert await document_page(ledger, owner, ident) is None


@pytest.mark.parametrize('kind', ['csv', 'xlsx'])
@pytest.mark.asyncio
async def test_tables_go_through_guard_and_delete(kind):
    rows = [['date', 'value', 'unit', 'series'], ['2026-09-01', '100', 'cartons', 'inventory'], ['2026-09-08', '110', 'cartons', 'inventory']]
    data = ('\n'.join(','.join(row) for row in rows)).encode() if kind == 'csv' else spreadsheet(rows)
    parsed = extract('history.' + kind, data)
    assert len(parsed['tables']) == 2
    ledger, tenant, ident = MemoryLedger(), str(uuid.uuid4()), str(uuid.uuid4())
    await accept(ledger, tenant, ident, 'history.' + kind, parsed, region='us-east')
    assert len(ledger.points_for(tenant)) == 2
    assert (await answer(ledger, tenant, 'inventory'))['facts']
    await forget(ledger, tenant, ident)
    assert not ledger.points_for(tenant)
    assert not (await answer(ledger, tenant, 'inventory'))['facts']
    rows[-1][1] = '10000'
    data = ('\n'.join(','.join(row) for row in rows)).encode() if kind == 'csv' else spreadsheet(rows)
    record = await accept(ledger, tenant, str(uuid.uuid4()), 'spike.' + kind, extract('spike.' + kind, data), region='us-east')
    assert record['reason']
    assert not ledger.points_for(tenant)
    assert not (await answer(ledger, tenant, 'inventory'))['facts']


@pytest.mark.parametrize('name,data', [('bad.pdf', b'not a PDF'), ('empty.csv', b'column\n'), ('bad.xlsx', b'not a zip'), ('notes.txt', b'hello')])
def test_bad_files_have_safe_reasons(name, data):
    with pytest.raises(ReadError) as exc:
        extract(name, data)
    assert data.decode() not in str(exc.value)


@pytest.mark.asyncio
async def test_no_topic_or_unrelated_question_uses_uploaded_text():
    ledger, tenant = MemoryLedger(), str(uuid.uuid4())
    await accept(ledger, tenant, str(uuid.uuid4()), 'report.pdf', extract('report.pdf', report_pdf()), region='us-east')
    for question in ['What is the weather on Mars?', 'Tell me about lunar mining', 'How is it?', 'What is the price of bananas?', 'Who won the tennis match?']:
        assert (await answer(ledger, tenant, question))['facts'] == []


def test_spreadsheet_serial_dates_keep_source_rows():
    raw = spreadsheet([['date', 'value', 'unit'], ['46266', '100', 'cartons']])
    result = extract('inventory.xlsx', raw)
    assert result['tables'][0]['date'] == '2026-09-01'
    assert result['passages'][0]['label'] == 'Worksheet 1, row 2'


def test_workbook_rejects_huge_column_before_allocating_cells():
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as z:
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="ZZZZZZZZ1"><v>1</v></c></row></sheetData></worksheet>')
    with pytest.raises(ReadError, match='invalid cell address'):
        extract('huge.xlsx', raw.getvalue())
