"""Offline regression checks for PR #361: real routes/parsers, no model or network."""
from __future__ import annotations

import asyncio
import json
import re
import time
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import httpx
import pytest
from fastapi import FastAPI

from test_rig_cn_archon import _archon, TENANT
from rigbox import api, cn, page_route, recall
from rigbox.service import Service
from rigbox.store import MemoryStore


@pytest.mark.asyncio
@pytest.mark.parametrize('skin,expected', [('rig', 'rig'), ('cn', 'cn'), ('CN', 'rig'), ('" onload="alert(1)', 'rig'), ('<script>alert(1)</script>', 'rig')])
async def test_skin_is_selected_from_fixed_strings_and_json_escaping_is_kept(monkeypatch, skin, expected):
    # The publishable value is empty; the adversarial shop label is offline input only.
    shop = '</script><script>alert("offline")</script>'
    monkeypatch.setattr(page_route, '_published_page', AsyncMock(return_value=('', shop)))
    app = FastAPI()
    page_route.mount_page(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        result = await client.get('/v5', params={'skin': skin})
    assert result.status_code == 200
    assert f'data-skin="{expected}"' in result.text
    assert shop not in result.text
    assert 'window.RIG_KEY = "";' in result.text
    assigned = re.search(r'window\.RIG_SHOP = (.*);', result.text).group(1)
    assert '\\u003c' in assigned
    assert json.loads(assigned) == shop


@pytest.mark.asyncio
async def test_shared_search_entry_caps_before_dispatch_and_storing_misses(monkeypatch):
    service = Service(MemoryStore())
    dispatch = AsyncMock(return_value={'results': []})
    record = AsyncMock()
    monkeypatch.setattr(service, '_search', dispatch)
    monkeypatch.setattr(service.store, 'training_event', record)
    query = '  ' + 'type b ' * 100 + '  '
    expected = ' '.join(query.split())[:200]
    await service.search(TENANT, query, 12)
    assert dispatch.await_args.args == (TENANT, expected, 12, None)
    assert record.await_args.args[3]['query'] == expected.strip()
    assert len(expected) == 200


@pytest.mark.asyncio
async def test_100000_space_searches_finish_under_one_second_through_the_real_route(monkeypatch):
    service = await _archon()
    app = FastAPI()
    app.state.rig = service
    api.mount(app)

    async def offline_identity(request):
        request.state.tenant_id = TENANT
        return {}

    monkeypatch.setattr(api, '_auth', offline_identity)
    spaces = ' ' * 100_000
    cases = [
        (spaces, ''),
        ('under' + spaces + 'R25000', 'under R25000'),
        ('does the rmr' + spaces + 'fit the type b?', 'does the rmr fit the type b?'),
        ('type b' + spaces + 'and rmr', 'type b and rmr'),
        ('type b' + spaces + 'with rmr', 'type b with rmr'),
    ]
    for adversarial, normal in cases:
        expected = await service.search(TENANT, normal, 24)
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": "/v1/rig/search",
            "root_path": "", "headers": [], "server": ("test", 80),
            "query_string": urlencode({"q": adversarial, "limit": 24}).encode(),
        }
        # Direct ASGI avoids the test client's URL-length cap, without bypassing the route.
        start = time.perf_counter()
        await asyncio.wait_for(app(scope, receive, send), timeout=1)
        elapsed = time.perf_counter() - start
        assert elapsed < 1, f"search took {elapsed:.3f}s"
        assert messages[0]["status"] == 200
        body = b"".join(message.get("body", b"") for message in messages)
        assert json.loads(body) == expected
        print(f"100,000-space route search: {elapsed:.6f}s")


def test_parsers_collapse_spaces_before_the_reported_expressions():
    spaces = ' ' * 100_000
    start = time.perf_counter()
    assert cn._parse_constraints('under' + spaces + 'R25000') == cn._parse_constraints('under R25000')
    assert cn._rewrite_fit_question('does the optic' + spaces + 'fit the type b?') == 'optic for type b'
    assert cn._fit_answer('does optic' + spaces + 'fit type b?', [], [], {}, 12) is None
    assert cn._split_clauses('type b' + spaces + '+ rmr', []) == ['type b', 'rmr']
    assert cn._meaningful('9x19', set()) is False
    assert recall.parts_of('optic' + spaces + 'and light for type b') == recall.parts_of('optic and light for type b')
    assert time.perf_counter() - start < 1
