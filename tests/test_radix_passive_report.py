"""Recorded upstream rule texts; invented target, never live-site fixtures."""
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from test_radix_passive import database as database, no_external_network as no_external_network, tools, store, A, B, TARGET, ARTIFACT

FIXTURES = Path(__file__).parent / 'fixtures/radix-passive'


def recorded(monkeypatch):
    template = FIXTURES / 'http-missing-security-headers.yaml'
    assert hashlib.sha256(template.read_bytes()).hexdigest() == '7f45803f73ac6810b9b302df6be2c472a82d9164a7807328614efa83e6eac275'
    monkeypatch.setattr(tools, 'TEMPLATE', str(template))
    return (tools.zap_findings(json.loads((FIXTURES / 'zap.json').read_text()), TARGET)
            + tools.nuclei_findings((FIXTURES / 'nuclei.jsonl').read_text(), TARGET))


def test_report_uses_recorded_rules_and_pinned_template_only(monkeypatch):
    findings = recorded(monkeypatch)
    assert len(findings) > 10
    zap = next(f for f in findings if f['rule'] == '10038')
    text = json.loads(zap['fix'])['10038']
    assert text['explanation'].startswith('<p>Content Security Policy (CSP)')
    assert text['remediation'] == '<p>Ensure that your web server, application server, load balancer, etc. is configured to set the Content-Security-Policy header.</p>'
    report = store.report_finding(zap)
    assert report['explanation'].startswith('Content Security Policy (CSP)')
    assert '<p>' not in report['explanation']
    nuclei = next(f for f in findings if f['tool'] == 'nuclei')
    report = store.report_finding(nuclei)
    assert report['explanation'] == 'This template searches for missing HTTP security headers. The impact of these missing headers can vary.'
    assert report['remediation'] == 'No rule text for http-missing-security-headers.'
    missing = store.report_finding(tools.finding('zap', 'info', '999999', TARGET))
    assert missing['explanation'] == missing['remediation'] == 'No rule text for 999999.'


@pytest.mark.asyncio
async def test_recorded_report_roundtrip_persists_no_raw_target_content(database, monkeypatch):
    from chassis import events
    monkeypatch.setattr(events, 'publish', AsyncMock(return_value=True))
    findings = recorded(monkeypatch)
    # Poison every target-dependent field, including fields that resemble rule text.
    zap = json.loads((FIXTURES / 'zap.json').read_text())
    for site in zap['site']:
        site['response'] = 'RAW_RESPONSE_MARKER'
        for alert in site['alerts']:
            alert.update(evidence='RAW_EVIDENCE_MARKER', responseHeader='RAW_HEADER_MARKER',
                         instances=[{'responseBody': 'RAW_BODY_MARKER'}])
    nuclei = [json.loads(line) for line in (FIXTURES / 'nuclei.jsonl').read_text().splitlines()]
    for row in nuclei:
        row.update(response='RAW_RESPONSE_MARKER', request='RAW_REQUEST_MARKER',
                   extracted_results=['RAW_EVIDENCE_MARKER'])
        row['info'].update(description='UNTRUSTED_ROW_DESCRIPTION', remediation='UNTRUSTED_ROW_FIX')
    sanitized = tools.zap_findings(zap, TARGET) + tools.nuclei_findings('\n'.join(map(json.dumps, nuclei)), TARGET)
    assert sanitized == findings
    await database.issue(A, 'owned.example')
    ident = await database.create(A, TARGET, ARTIFACT)
    assert await database.running(A, ident)
    await database.complete(A, ident, sanitized)
    saved = await database.findings(A, ident)
    assert len(saved) == len(findings) and await database.findings(B, ident) == []
    async with database.pool.acquire() as conn:
        rows = await conn.fetch('SELECT to_jsonb(f) AS data FROM agent_radix.findings f WHERE tenant_id=$1 AND scan_id=$2', A, ident)
    persisted = json.dumps([row['data'] for row in rows], default=str)
    for marker in ('RAW_RESPONSE_MARKER', 'RAW_EVIDENCE_MARKER', 'RAW_HEADER_MARKER', 'RAW_BODY_MARKER', 'RAW_REQUEST_MARKER', 'UNTRUSTED_ROW_DESCRIPTION', 'UNTRUSTED_ROW_FIX'):
        assert marker not in persisted
    for finding in findings:
        assert set(finding) <= {'tool', 'severity', 'rule', 'file', 'line', 'fix'}
        if finding.get('fix'):
            assert list(json.loads(finding['fix'])) == [finding['rule']]
    assert any('Content Security Policy' in row['explanation'] for row in saved)
