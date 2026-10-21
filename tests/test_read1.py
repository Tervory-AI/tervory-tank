"""Deterministic public-page fixtures; no model or network required."""
import json
import io
import pytest
from types import SimpleNamespace
from test_agent1_isolation import browser, runner
from brain.reader import read_page, model_page


def test_long_head_structured_first_ranked_links_and_hidden_text():
    html = '''<html lang="en"><head><title>Shop</title><style>secret-style</style>''' + ' ' * 30000 + '''
    <script type="application/ld+json">{"@type":"LocalBusiness","name":"Shop","telephone":"555-111-2222","address":{"streetAddress":"10 Main St"},"geo":{"latitude":1,"longitude":2}}</script>
    </head><body><nav><a href="/news">News</a><a href="https://other.example/contact">Contact elsewhere</a><a href="/contact">Contact us</a></nav>
    <h1>Welcome</h1><p>Call 555-222-3333 or office@example.com</p>
    <div hidden>secret-hidden</div><div style="display: none">secret-css</div><script>secret-script</script>
    <a href="mailto:hello@example.com">Email</a></body></html>'''
    page = read_page('https://shop.example', html)
    assert page['facts']['title'] == 'Shop'
    assert page['facts']['language'] == 'en'
    assert page['links'][0]['url'] == 'https://shop.example/contact'
    assert page['contact_details'][0]['source'] == 'json-ld'
    assert any(d['value'] == 'hello@example.com' for d in page['contact_details'])
    assert '# Welcome' in page['text']
    assert 'secret-' not in model_page(page)
    assert '<html' not in runner.tool_result({'html': html, 'url': 'https://shop.example'})


def test_budget_and_sections():
    page = read_page('https://shop.example', '<p>' + 'word ' * 10000 + '</p>' + ''.join(f'<a href="/{i}">Contact {i}</a>' for i in range(100)))
    encoded = model_page(page)
    assert len(encoded) <= 8000
    assert list(json.loads(encoded)) == ['facts', 'links', 'contact_details', 'text']
    assert len(page['links']) == 30
    assert len(page['text']) <= 5000


def test_microdata_and_page_walls():
    page = read_page('https://shop.example', '<div itemscope itemtype="https://schema.org/Store"><span itemprop="telephone">555-123-4567</span><p>Other text</p></div><p>Verify your age. Sign in to continue</p>', status=403, challenge=True)
    assert page['contact_details'][0] == {'kind': 'telephone', 'value': '555-123-4567', 'source': 'microdata'}
    assert all(page['facts'][key] for key in ['human_check', 'age_gate', 'login_wall', 'error_page'])


def test_pdf_shape_and_links():
    page = read_page('https://shop.example/menu.pdf', text='Contact\n555-123-4567\ninfo@example.com', links=[{'text': 'Contact', 'url': 'https://shop.example/contact'}])
    value = json.loads(model_page(page))
    assert value['links'][0]['text'] == 'Contact'
    assert len(value['contact_details']) == 2
    assert value['text'].startswith('Contact')


@pytest.mark.asyncio
async def test_pdf_reader_extracts_annotations(monkeypatch):
    from pypdf import PdfWriter
    from pypdf.annotations import Link
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": "Shop document"})
    writer.add_annotation(0, Link(rect=(0, 0, 100, 100), url="https://shop.example/contact"))
    data = io.BytesIO()
    writer.write(data)
    class Response:
        status = 200
        headers = {}
        async def body(self):
            return data.getvalue()
    class Request:
        async def get(self, *args, **kwargs):
            return Response()
    monkeypatch.setattr(browser, 'public_url', lambda url: ('shop.example', 443))
    result = await browser.read_pdf(SimpleNamespace(request=Request()), 'https://shop.example/a.pdf', 1000)
    report = read_page(result['url'], text=result['text'], links=result['links'], title=result['title'])
    assert report['facts']['title'] == 'Shop document'
    assert report['links'][0]['url'] == 'https://shop.example/contact'
