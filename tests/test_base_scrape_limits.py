"""Large recorded pages exercise the real candidate and shared observation path."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from base_evidence import observe, observations
from test_b3b_base_wiring import ABOUT, SITE, Ctx, Site

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'tank/skills/base.scrape_site/1.3.1'
CASES = json.loads((PACKAGE / 'evals/large_pages.json').read_text())


def candidate():
    spec = importlib.util.spec_from_file_location('scrape_limits_candidate', PACKAGE / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.timeout(15)
@pytest.mark.parametrize('case', CASES, ids=lambda case: case['name'])
def test_large_page_keeps_own_contacts_and_later_page(case):
    module = candidate()
    token = case.get('prefix', '') + case['repeat'] * (module.HTML_CAP + 80) + case['suffix']
    home = "<html><body><a href='/about'>About</a> HOME-MARKER " + token + '</body></html>'
    about = '<html><body>ABOUT-MARKER <a href="mailto:tail@placeholder.example">Contact</a></body></html>'
    result = asyncio.run(module.run({'website': SITE}, Ctx(Site({SITE: home, ABOUT: about}))))
    assert result['pages'] == [SITE, ABOUT]
    assert sorted(result['emails']) == sorted([*case['emails'], 'tail@placeholder.example'])
    assert 'HOME-MARKER' in result['html'] and 'ABOUT-MARKER' not in result['html']
    assert len(result['html'].encode()) <= module.HTML_CAP
    proof = []
    context = observations.set(proof)
    try:
        observe(SITE, home)
        observe(ABOUT, about)
    finally:
        observations.reset(context)
    assert proof[0]['emails'] == case['emails']
    assert proof[1]['emails'] == ['tail@placeholder.example']
    assert [item['source_url'] for item in proof] == [SITE + '/', ABOUT]
    assert all(item['checked_at'] for item in proof)


def test_candidate_preserves_existing_evals_and_approved_package():
    assert (PACKAGE / 'evals/cases.jsonl').read_bytes() == (PACKAGE.with_name('1.3.0') / 'evals/cases.jsonl').read_bytes()
    cases = [json.loads(line) for line in (PACKAGE / 'evals/cases.jsonl').read_text().splitlines()]
    assert len(cases) >= 5 and any(case.get('must_refuse') for case in cases)
