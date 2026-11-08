"""Contract/isolation proofs; no model runtimes or provider traffic."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from route_comparison import ArchAdapter, RouteLLMAdapter, dry_run, validate
from routellm_shadow import Configuration

FIXTURES = Path('tests/fixtures/route_comparison')
CONFIG = Configuration('placeholder-strong', 'placeholder-weak', .5)


@pytest.fixture
def corpus():
    return json.loads((FIXTURES / 'examples.json').read_text())


@pytest.mark.parametrize('raw', ['not-json', '{"route":"unregistered"}', '{"route":"weak","score":1}',
                                  '[]', '{"route":null}', 'x' * 513])
def test_arch_invalid_output_abstains_and_escalates(corpus, raw):
    result = ArchAdapter(lambda payload: raw, CONFIG, corpus['routes']).classify(corpus['examples'][0]['messages'])
    assert result.abstained and result.escalated and result.model == CONFIG.strong
    assert result.reason == 'invalid_or_unavailable'


@pytest.mark.parametrize('route', ['weak', 'strong', 'other'])
def test_arch_contract_excludes_private_labels(corpus, route):
    captured = []
    def generate(payload):
        captured.append(deepcopy(payload))
        return json.dumps({'route': route})
    row = corpus['examples'][0]
    result = ArchAdapter(generate, CONFIG, corpus['routes']).classify(row['messages'])
    assert captured == [{'routes': corpus['routes'], 'conversation': row['messages']}]
    assert 'reference_route' not in json.dumps(captured)
    assert result.model == (CONFIG.weak if route == 'weak' else CONFIG.strong)
    assert result.abstained == (route == 'other')
    assert result.escalated == (route != 'weak')


@pytest.mark.parametrize('score,route', [(.49, 'weak'), (.5, 'strong'), (1., 'strong'),
    (float('nan'), 'other'), (float('inf'), 'other'), (-.1, 'other'), (True, 'other')])
def test_routellm_matches_serving_threshold_and_latest_turn(score, route):
    received = []
    def classify(prompt):
        received.append(prompt)
        return score
    messages = [{'role':'user','content':'placeholder older turn'},
                {'role':'assistant','content':'placeholder response'},
                {'role':'user','content':'placeholder latest turn'}]
    result = RouteLLMAdapter(classify, CONFIG).classify(messages)
    assert received == ['placeholder latest turn'] and result.route == route
    assert result.abstained == (route == 'other')


def test_both_classifier_outages_abstain_without_exception_details(corpus):
    def unavailable(payload):
        raise RuntimeError('placeholder private transport details')
    for adapter in (ArchAdapter(unavailable, CONFIG, corpus['routes']), RouteLLMAdapter(unavailable, CONFIG)):
        result = adapter.classify(corpus['examples'][0]['messages'])
        assert result.abstained and result.escalated
        assert 'private' not in str(result)


@pytest.mark.parametrize('change', ['duplicate', 'duplicate_id', 'group', 'gold', 'unprovenanced', 'too_many', 'oversized'])
def test_leakage_and_bounds_are_rejected_before_selection(corpus, change):
    rows = corpus['examples']
    if change == 'duplicate':
        rows[1]['messages'] = deepcopy(rows[0]['messages'])
    elif change == 'duplicate_id':
        rows[1]['id'] = rows[0]['id']
    elif change == 'group':
        rows[1]['provenance']['source_id'] = rows[0]['provenance']['source_id']
    elif change == 'gold':
        rows[0]['provenance']['gold'] = True
    elif change == 'unprovenanced':
        rows[0]['provenance']['kind'] = 'live-tenant-export'
    elif change == 'too_many':
        rows.extend(deepcopy(rows) * 4)
    else:
        rows[0]['messages'][0]['content'] = 'x' * 16001
    with pytest.raises(ValueError):
        dry_run(corpus, tenant_id='placeholder-tenant-b', split='holdout')


def test_tenant_split_selection_and_no_benchmark_claims(corpus):
    validate(corpus['examples'])
    first = dry_run(corpus, tenant_id='placeholder-tenant-a', split='holdout')
    other = dry_run(corpus, tenant_id='placeholder-tenant-b', split='holdout')
    assert first['selected_examples_sha256'] != other['selected_examples_sha256']
    assert first['mode'] == 'fixture-only'
    assert all(item['examples'] == 2 for item in first['fixture_contract'].values())
    benchmark = first['model_comparison']
    assert benchmark['status'] == 'unrun' and benchmark['cost_status'] == 'unknown'
    assert all(benchmark[key] is None for key in ('route_quality','classifier_latency_ms',
        'inference_cost_usd','abstention_rate','escalation_rate','savings_usd'))
    assert 'messages' not in json.dumps(first) and 'Extract the date' not in json.dumps(first)
    with pytest.raises(ValueError, match='No examples'):
        dry_run(corpus, tenant_id='placeholder-foreign', split='holdout')


def test_single_opt_in_dry_run_command():
    result = subprocess.run([sys.executable, 'scripts/compare_route_classifiers.py', '--dry-run',
        '--tenant', 'placeholder-tenant-a', '--split', 'holdout'],
        capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(result.stdout)['model_comparison']['status'] == 'unrun'
    refused = subprocess.run([sys.executable, 'scripts/compare_route_classifiers.py'],
        capture_output=True, text=True, timeout=30, check=False)
    assert refused.returncode != 0


def test_report_binds_exact_upstream_and_route_descriptions(corpus):
    upstream = json.loads((FIXTURES / 'upstream.json').read_text())
    first = dry_run(corpus, tenant_id='placeholder-tenant-a', split='holdout')
    assert first['sources']['arch_revision'] == upstream['arch']['model_revision']
    assert first['sources']['routellm_revision'] == upstream['routellm']['model_revision']
    corpus['routes'][0]['description'] = 'placeholder changed preference'
    changed = dry_run(corpus, tenant_id='placeholder-tenant-a', split='holdout')
    assert changed['route_descriptions_sha256'] != first['route_descriptions_sha256']
