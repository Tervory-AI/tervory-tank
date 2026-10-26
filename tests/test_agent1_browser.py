"""Browser scheduling and redirects without a live website or model."""
import asyncio
import sys
import types
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

# The shared brain package is loaded by the room-boundary test harness.
from test_agent1_isolation import browser
from brain import robots


@pytest.fixture
def visitor(monkeypatch, tmp_path):
    h=SimpleNamespace(started=[], gate=asyncio.Event(), html='<p>Public business page</p>',
                      redirect=None, status=200, aborted=0, continued=0, scrolls=0, robots_text="User-agent: *\nAllow: /", robots_calls=[], request_options=[])
    key=uuid.uuid4().hex
    monkeypatch.setenv('TANK_KEY',key)
    monkeypatch.setenv('BROWSER_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('TANK_REGION','us-east')
    monkeypatch.setattr(browser,'site_locks',{})
    monkeypatch.setattr(robots, 'cache', {})
    monkeypatch.setattr(robots, 'stopped_hosts', set())
    monkeypatch.setattr(browser,'last_visit',{})
    monkeypatch.setattr(browser,'concurrency',asyncio.Semaphore(4))
    class Page:
        def __init__(self,context): self.context=context; self.handlers={}
        def on(self,event,handler): self.handlers[event]=handler
        async def goto(self,url,**kwargs):
            self.url=url;h.started.append(url)
            if h.redirect:
                class Route:
                    request=SimpleNamespace(url=h.redirect,method='GET',is_navigation_request=lambda:True)
                    async def abort(self): h.aborted+=1
                    async def continue_(self): h.continued+=1
                    async def fallback(self): h.continued+=1
                await self.context.handler(Route())
                if h.continued:
                    self.url=h.redirect
            await h.gate.wait()
            response=SimpleNamespace(status=h.status,url=self.url,headers={},request=SimpleNamespace(resource_type='document'))
            if 'response' in self.handlers: self.handlers['response'](response)
            return response
        async def content(self): return h.html
        async def evaluate(self,*args):
            if "({width: Math.max" in args[0]:
                return {"width": 1280, "height": 8000}
            h.scrolls+=1
            return h.html
        async def screenshot(self,**kwargs):
            if getattr(h, 'screenshot_failure', False):
                raise RuntimeError('Failed screenshot')
            h.screenshot_options = kwargs
            return b'screenshot'
        async def wait_for_timeout(self,*args): pass
        def get_by_role(self,*args,**kwargs): raise AssertionError('Unexpected click')
        def locator(self,*args):
            async def evaluate_all(*args): return []
            return SimpleNamespace(evaluate_all=evaluate_all)
    class Request:
        async def get(self, url, **kwargs):
            h.robots_calls.append(url)
            h.request_options.append(kwargs)
            async def body(): return h.robots_text.encode()
            return SimpleNamespace(status=h.status, headers={}, body=body)
    class Context:
        request = Request()
        async def route(self,pattern,handler): self.handler=handler; h.request_handler=handler
        async def new_page(self): return Page(self)
        async def storage_state(self,**kwargs): pass
    class Browser:
        async def new_context(self,**kwargs): h.context_options=kwargs; return Context()
        async def close(self): pass
    async def launch(**kwargs): return Browser()
    @asynccontextmanager
    async def playwright(): yield SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    package=types.ModuleType('playwright');api=types.ModuleType('playwright.async_api')
    api.async_playwright=playwright
    monkeypatch.setitem(sys.modules,'playwright',package)
    monkeypatch.setitem(sys.modules,'playwright.async_api',api)
    tenant=str(uuid.uuid4())
    async def visit(url, *, task=None, tenant_id=None):
        return await browser.render(browser.Page(url=url),key,tenant_id or tenant,'us-east',task or str(uuid.uuid4()))
    h.visit=visit
    return h


@pytest.mark.asyncio
async def test_different_sites_do_not_wait_behind_one_tenant(visitor):
    one=asyncio.create_task(visitor.visit('https://one.example'))
    two=asyncio.create_task(visitor.visit('https://two.example'))
    for _ in range(100):
        if len(visitor.started)==2: break
        await asyncio.sleep(.001)
    assert len(visitor.started)==2
    visitor.gate.set()
    assert all(result['ok'] for result in await asyncio.gather(one,two))


@pytest.mark.asyncio
async def test_same_site_waits_a_few_seconds(visitor,monkeypatch):
    visitor.gate.set()
    now=[100.0];waits=[]
    async def sleep(seconds): waits.append(seconds);now[0]+=seconds
    monkeypatch.setattr(browser,'time',SimpleNamespace(monotonic=lambda:now[0],time=lambda:100,time_ns=lambda:100,perf_counter=lambda:100))
    monkeypatch.setattr(browser,'asyncio',SimpleNamespace(sleep=sleep,Lock=asyncio.Lock,timeout=asyncio.timeout))
    await visitor.visit('https://www.business.example')
    await visitor.visit('https://business.example/about')
    assert waits[-1]>=3


@pytest.mark.asyncio
async def test_captcha_is_recorded_needs_a_person_without_click_or_scroll(visitor):
    visitor.gate.set()
    visitor.html='<div class="g-recaptcha">verify you are human</div><button>I am over 21</button>'
    result=await visitor.visit('https://business.example')
    assert result['challenge'] and result['needs_person']=='needs a person' and 'html' not in result and result['page']['facts']['human_check']
    assert visitor.scrolls==1  # extraction inspects the DOM without clicking or scrolling


@pytest.mark.asyncio
async def test_redirect_request_is_rechecked_and_private_target_aborted(visitor):
    visitor.gate.set();visitor.redirect='http://169.254.169.254'
    result=await visitor.visit('https://public-looking.example')
    assert visitor.aborted==1 and visitor.continued==0 and result['denied_requests']==1


@pytest.mark.asyncio
async def test_pdf_text_is_read_with_bounded_public_requests(monkeypatch):
    import io
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=200,height=200)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 100 Td (Public fixture PDF) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    buffer=io.BytesIO();writer.write(buffer);data=buffer.getvalue();calls=[]
    class Response:
        status=200
        headers={'content-length':str(len(data))}
        async def body(self):return data
    async def get(url,**kwargs):
        assert kwargs['max_redirects']==0;calls.append(url);return Response()
    async def allow(*args): pass
    monkeypatch.setattr(browser, 'require_allowed', allow)
    result=await browser.read_pdf(SimpleNamespace(request=SimpleNamespace(get=get)),'https://public.example/file.pdf',90000)
    assert 'Public fixture PDF' in result['text'] and result['content_type']=='application/pdf'
    assert calls==['https://public.example/file.pdf']


@pytest.mark.asyncio
async def test_pdf_redirect_cannot_fetch_a_private_target(monkeypatch):
    calls=[]
    async def get(url,**kwargs):
        calls.append(url);return SimpleNamespace(status=302,headers={'location':'http://169.254.169.254/latest/'})
    async def allow(*args): pass
    monkeypatch.setattr(browser, 'require_allowed', allow)
    with pytest.raises(ValueError):
        await browser.read_pdf(SimpleNamespace(request=SimpleNamespace(get=get)),'https://public.example/file.pdf',90000)
    assert calls==['https://public.example/file.pdf']


@pytest.mark.asyncio
async def test_busy_browser_queue_returns_before_upstream_timeout(visitor, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(browser, 'QUEUE_TIMEOUT', .02)
    lock = asyncio.Lock()
    await lock.acquire()
    browser.site_locks['busy.example'] = lock
    with pytest.raises(HTTPException, match='busy') as error:
        await asyncio.wait_for(visitor.visit('https://busy.example'), .5)
    assert error.value.status_code == 503 and lock.locked()
    assert browser.concurrency._value == 4


@pytest.mark.asyncio
async def test_page_evidence_is_saved_without_returning_html(visitor, tmp_path):
    visitor.gate.set()
    result = await visitor.visit('https://shop.example')
    assert 'html' not in result
    assert result['page']['text'] == 'Public business page'
    evidence = list(tmp_path.rglob('evidence/*'))
    assert {p.suffix for p in evidence} == {'.html', '.jpg'}
    assert next(p for p in evidence if p.suffix == '.html').read_text() == visitor.html


@pytest.mark.asyncio
async def test_screenshot_failure_does_not_fail_page_read(visitor):
    visitor.gate.set()
    visitor.screenshot_failure = True
    result = await visitor.visit('https://shop.example')
    assert result['ok'] and result['page']['text'] == 'Public business page'
    assert result['evidence']['screenshot_error']
