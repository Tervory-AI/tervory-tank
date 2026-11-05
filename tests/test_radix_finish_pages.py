"""A missing navigation link is not evidence that a monitored page vanished."""
import hashlib

import httpx
import pytest

from radix_r6.test_checks import r6, tool, TARGET


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 404, 503])
async def test_unlinked_monitored_page_is_rechecked_before_gone(tmp_path, status):
    old = TARGET + 'placeholder-unlinked'
    content = b'<html><p>placeholder</p></html>'
    seen = []
    async def request(req):
        seen.append(str(req.url))
        return httpx.Response(200 if req.url.path == '/' else status,
                              headers={'content-type': 'text/html'}, content=content)
    result = await r6.collect(TARGET, tmp_path, run=tool, transport=httpx.MockTransport(request),
                              previous={old: hashlib.sha256(content).hexdigest()})
    assert seen == [TARGET, old]
    observations = [f for f in result['findings'] if f['tool'] == 'sha256' and f['file'] == old]
    if status == 404:
        assert len(observations) == 1 and observations[0]['rule'] == 'gone'
    else:
        assert not observations
    if status == 200:
        assert result['page_hashes'][old] == hashlib.sha256(content).hexdigest()
    elif status == 503:
        assert result['page_hashes'] is None and result['checks']['pages']['status'] == 'partial'


@pytest.mark.asyncio
async def test_previous_hashes_cannot_extend_origin_or_include_credentials(tmp_path):
    invalid = ['https://other-placeholder.example/page', TARGET + '?token=placeholder',
               'https://placeholder:placeholder@placeholder.example/page']
    seen = []
    async def request(req):
        seen.append(str(req.url))
        return httpx.Response(200, headers={'content-type': 'text/html'}, text='<html></html>')
    result = await r6.collect(TARGET, tmp_path, run=tool, transport=httpx.MockTransport(request),
                              previous={url: 'a'*64 for url in invalid})
    assert seen == [TARGET]
    assert not any(f['file'] in invalid for f in result['findings'])
