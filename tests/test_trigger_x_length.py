"""Official twitter-text conformance data; offline, no parser package or network."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents'))
from trigger.formats import _x_length, check_limit, length

FIXTURE = json.loads((ROOT / 'tests/trigger_w1/twitter-text-weighted.json').read_text())
CURRENT = FIXTURE['tests']['WeightedTweetsWithDiscountedEmojiCounterTest']
LEGACY = FIXTURE['tests']['WeightedTweetsCounterTest']


@pytest.mark.parametrize('case', CURRENT, ids=[c['description'] for c in CURRENT])
def test_official_current_weighted_length(case):
    expected = case['expected']['weightedLength']
    assert length(case['text'], 'X post') == expected
    report = check_limit({'issues': [], 'issue_count': 0, 'truncated': False}, case['text'], 'X post')
    assert report['length']['count'] == expected
    assert bool(report['issues']) == (expected > 280)
    if expected > 280:
        assert report['issues'][0]['rule'] == 'over_limit'
        assert report['issues'][0]['count'] == expected


@pytest.mark.parametrize('case', LEGACY, ids=[c['description'] for c in LEGACY])
def test_official_legacy_weight_ranges_and_normalization(case):
    # These official v2 expectations predate emoji discounting. Keep them intact;
    # the public X format always uses the v3 rules exercised above.
    assert _x_length(case['text'], discount_emoji=False) == case['expected']['weightedLength']


@pytest.mark.parametrize(('point', 'expected'), [
    (0x10FF, 1), (0x1100, 2), (0x1FFF, 2), (0x2000, 1), (0x200D, 1),
    (0x200E, 2), (0x200F, 2), (0x2010, 1), (0x201F, 1), (0x2020, 2),
    (0x2031, 2), (0x2032, 1), (0x2037, 1), (0x2038, 2),
])
def test_published_weight_range_boundaries(point, expected):
    assert length(chr(point), 'X post') == expected


@pytest.mark.parametrize(('text', 'expected'), [
    ('cafe\u0301', 4),
    ('Read https://example.com/a_(b).', 29),
    ('example.com', 23),
    ('person@example.com', 18),
    ('http://-example.com', 19),
    ('https://domain_with_underscore.com', 34),
    ('https://example.com/👨‍👩‍👧‍👦', 23),
    ('https://' + 'ß' * 50 + '.de', 23),
    ('🇿🇦', 2),
    ('1️⃣', 2),
    ('🐱\u200d🐱', 5),
])
def test_url_boundaries_and_emoji_sequences(text, expected):
    assert length(text, 'X post') == expected


def test_no_parser_or_setuptools_runtime_dependency():
    requirements = (ROOT / 'agents/trigger/requirements.txt').read_text()
    assert 'twitter-text-parser' not in requirements and 'setuptools' not in requirements
    # -S disables site packages, proving an already-installed old parser cannot
    # accidentally make these conformance tests pass.
    script = '''
import json
from pathlib import Path
from trigger.formats import _x_length
rows = json.loads(Path('tests/trigger_w1/twitter-text-weighted.json').read_text())['tests']
for group, cases in rows.items():
    for case in cases:
        assert _x_length(case['text'], discount_emoji='DiscountedEmoji' in group) == case['expected']['weightedLength']
'''
    result = subprocess.run([sys.executable, '-S', '-c', script], cwd=ROOT,
                            env={'PYTHONPATH': str(ROOT / 'agents')}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
