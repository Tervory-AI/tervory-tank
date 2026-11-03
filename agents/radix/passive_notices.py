"""One proxied root response: existing saved-HTML notices and cookie flag rules.

No interaction, scripts, subresources, redirects, cookie values or page bodies
are persisted. This HTTP-only check does not assert browser cookie coverage.
"""
from __future__ import annotations

import httpx

from live import _cookie_findings
from passive_store import target_url
from passive_tools import PROXY, rule_text
from scanlib.comply import scan_html


async def collect(target, directory, *, transport=None):
    _, domain = target_url(target)
    async with httpx.AsyncClient(proxy=PROXY if transport is None else None,
            transport=transport, trust_env=False, timeout=20, follow_redirects=False) as client:
        async with client.stream('GET', target, headers={'Accept': 'text/html'}) as response:
            response.raise_for_status()
            if response.status_code != 200 or 'text/html' not in response.headers.get('content-type', '').lower():
                raise ValueError('notice response incomplete')
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 1_000_000:
                    raise ValueError('notice response limit')
            result = scan_html(body.decode(response.encoding or 'utf-8', errors='replace'),
                               name='page.html', page_host=domain)
            findings = result['findings'] + _cookie_findings(response, target)
    # Preserve the existing rule's own wording in the passive card's text format.
    for item in findings:
        text = item.pop('fix')
        item['file'] = target
        rule_text(item, text, text)
    return findings
