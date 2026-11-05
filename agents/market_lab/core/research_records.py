"""Durable source-backed research and its original Tank receipts."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from core.documents import call

log = logging.getLogger('agent')


async def save(ledger, tenant: str, question: str, research: dict) -> dict:
    facts = research.get('facts') or []
    if not facts:
        raise ValueError('Research needs source evidence')
    citations = []
    for fact in facts:
        text, url = fact.get('text'), fact.get('href')
        parsed = urlsplit(url or '')
        local = bool(url and url.startswith('/market-lab/sources/'))
        if (not isinstance(text, str) or not text.strip() or
                not (local or parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password)):
            raise ValueError('Research needs source evidence')
        citation = {'claim': text, 'url': url, 'source': fact.get('name') or url}
        for key in ('fetched_at', 'quote'):
            if fact.get(key) is not None:
                citation[key] = fact[key]
        citations.append(citation)
    receipts = []
    for original in research.get('receipts') or []:
        receipt = {key: original[key] for key in ('ledger_id','tokens_in','tokens_out','cost_usd')}
        receipt['ledger_id'] = str(UUID(str(receipt['ledger_id'])))
        if any(type(receipt[key]) is not int or receipt[key] < 0 for key in ('tokens_in','tokens_out')):
            raise ValueError('Invalid research receipt')
        cost = receipt['cost_usd']
        if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost < 0):
            raise ValueError('Invalid research receipt')
        receipts.append(receipt)
    report = {'id': str(uuid4()), 'tenant_id': str(UUID(tenant)), 'made_at': datetime.now(timezone.utc),
              'question': question, 'answer': '\n'.join(fact['text'] for fact in facts),
              'citations': citations, 'receipts': receipts}
    await call(ledger.save_report, report)
    return report


async def remember(memory, report: dict) -> None:
    if memory is None:
        return
    try:
        await memory.remember(report['tenant_id'], report['answer'], 'report', report['citations'][0]['url'])
    except Exception as exc:
        # Reporting remains durable if the independent memory service is down.
        log.warning('report memory unavailable (%s)', type(exc).__name__)
