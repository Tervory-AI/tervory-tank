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
    assert list(json.loads(encoded)) == ['notice', 'facts', 'links', 'contact_details', 'text']
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
    async def allow(*args): pass
    monkeypatch.setattr(browser, 'require_allowed', allow)
    result = await browser.read_pdf(SimpleNamespace(request=Request()), 'https://shop.example/a.pdf', 1000)
    report = read_page(result['url'], text=result['text'], links=result['links'], title=result['title'])
    assert report['facts']['title'] == 'Shop document'
    assert report['links'][0]['url'] == 'https://shop.example/contact'


@pytest.mark.asyncio
async def test_rendered_css_visibility_and_pilot(real_chromium):
    """Required real-browser fixture; no network or model calls."""
    html = '<html><head><style>.concealed {display:none}.invisible {visibility:hidden}.transparent {opacity:0}</style><script>' + 'setup();' * 2000 + '</script></head><body><h1>Shop</h1><div style="display:contents"><p>Visible contents</p></div><p class="invisible">css-invisible</p><p class="transparent">css-transparent</p><p class="concealed">hidden@example.com</p><div aria-hidden="true">hidden aria</div><a href="https://shop.example/contact">Contact</a><p>555-123-4567 visible@example.com</p></body></html>'
    page = await real_chromium.new_page()
    await page.set_content(html)
    source = await browser.rendered_source(page)
    report = read_page('https://shop.example', source)
    before = json.dumps({'html': html, 'links': [{'text': 'Contact', 'url': 'https://shop.example/contact'}]})[:7000]
    after = model_page(report)
    assert 'visible@example.com' not in before and '/contact' not in before
    assert 'visible@example.com' in after and '/contact' in after
    assert 'hidden@example.com' not in after and 'hidden aria' not in after
    assert 'css-invisible' not in after and 'css-transparent' not in after
    assert 'Visible contents' in after
    assert len(after) <= 8000
    assert report['extraction_ms'] >= 0


@pytest.mark.parametrize("missing_unresolved", [False, True])
def test_runner_records_reading_counters_and_extraction_receipts(tmp_path, monkeypatch, missing_unresolved):
    import sys
    import types
    import uuid
    tenant, task, record, second_record = (str(uuid.uuid4()) for _ in range(4))
    (tmp_path / 'request.json').write_text(json.dumps({'tenant_id': tenant, 'task_id': task, 'batch': 'pilot', 'count': 1, 'memories': []}))
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('TANK_KEY', uuid.uuid4().hex)
    handlers = {}
    registry = types.ModuleType('tools.registry')
    registry.registry = SimpleNamespace(register=lambda **kw: handlers.update({kw['name']: kw['handler']}))
    monkeypatch.setitem(sys.modules, 'tools.registry', registry)
    state = types.ModuleType('hermes_state')
    state.SessionDB = lambda *a: None
    monkeypatch.setitem(sys.modules, 'hermes_state', state)
    pipeline_calls = []
    retries = []
    uploads = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def request(self, method, url, **kwargs):
            if url.endswith('/skills'):
                value = {'tenant_id': tenant, 'room': 'base', 'region': 'us-east', 'skills': []}
            elif url.endswith('/render'):
                report = read_page(kwargs['json']['url'], '<a href="/contact">Contact</a><p>info@example.com</p>')
                value = {'page': report, 'evidence': {'id': 'a' * 64, 'status': 'pending_upload'}}
            elif url.endswith('/evidence'):
                uploads.append(kwargs['json'])
                value = {'status': 'uploaded', 'bucket': 'tervory-base', 'keys': ['evidence/' + tenant + '/date/hash.html']}
            elif url.endswith('/pipeline'):
                pipeline_calls.append(kwargs['json']['finish'])
                value = {'pipeline_status': 'done', 'unresolved': [{'id': record}, {'id': second_record}]}
            elif url.endswith('/retry'):
                retries.append(kwargs['json']['record_id'])
                value = {'pipeline_status': 'done'}
                if len(retries) == 2:
                    value['unresolved'] = []
                elif not missing_unresolved:
                    value['unresolved'] = [{'id': second_record}]
            elif url.endswith('/receipts'):
                value = {'receipts': []}
            else:
                raise AssertionError(url)
            return SimpleNamespace(status_code=200, json=lambda: value)
    monkeypatch.setattr(runner.httpx, 'Client', Client)
    agent_module = types.ModuleType('run_agent')
    class Agent:
        def __init__(self, **kwargs): pass
        def run_conversation(self, *args, **kwargs):
            handlers['pipeline_run']({})
            first = handlers['browser']({'url': 'https://shop.example/'})
            assert list(json.loads(first)) == ['notice', 'facts', 'links', 'contact_details', 'text']
            handlers['browser']({'url': 'https://shop.example/contact'})
            handlers['retry_record']({'record_id': record, 'website': 'https://shop.example/'})
            handlers['retry_record']({'record_id': second_record, 'website': 'https://shop.example/'})
            return {'final_response': 'Finished'}
    agent_module.AIAgent = Agent
    monkeypatch.setitem(sys.modules, 'run_agent', agent_module)
    runner.run(tmp_path)
    receipt = json.loads((tmp_path / 'receipt.json').read_text())
    assert receipt['reading'] == {'pages_read': 2, 'links_followed': 1, 'contact_details_per_page': [1, 1], 'sites_resolved': 1 if missing_unresolved else 2}
    pages = [step for step in receipt['steps'] if step['action'] == 'browser']
    assert all(step['extraction_ms'] >= 0 and step['evidence']['id'] == 'a' * 64 for step in pages)
    assert pipeline_calls == [False, True]
    assert len(uploads) == 2 and all(item['tenant_id'] == tenant for item in uploads)
    assert all(step['evidence']['status'] == 'uploaded' and step['evidence']['keys'][0].startswith('evidence/' + tenant + '/') for step in pages)



def test_local_business_precedes_organization_and_contact_budget():
    html = '<script type="application/ld+json">{"@graph":[{"@type":"Organization","name":"Parent"},{"@type":"LocalBusiness","name":"Branch"}]}</script><p>info@example.com</p>'
    html += ''.join(f'<a href="https://shop.example/contact/{i}/' + 'x' * 1500 + '">Contact</a>' for i in range(30))
    report = read_page('https://shop.example', html)
    assert report['contact_details'][0]['value'] == 'Branch'
    encoded = model_page(report)
    assert len(json.loads(encoded)['links']) == 30
    assert json.loads(encoded)['facts']['budget_exceeded_by_links']
    assert all(len(item['url']) > 1500 for item in json.loads(encoded)['links'])



def test_malformed_markup_is_ignored_without_losing_the_page():
    report = read_page('https://shop.example', '<script type="application/ld+json">{"@type":null}</script><script type="application/ld+json">{"@type":[{}]}</script><a href="http://[broken">Bad URL</a><div style>Call +27 21 555 1234</div>')
    assert report['links'] == []
    assert any(detail['value'] == '+27 21 555 1234' for detail in report['contact_details'])
