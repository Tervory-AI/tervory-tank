"""Run the new package through Skala with a context that forbids paid calls."""
import asyncio
import importlib.util
from pathlib import Path

import skala
import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'tank/skills/tiger.price_structured/1.0.0'


class NoCalls:
    def __getattr__(self, name):
        raise AssertionError('code skill tried to use context: ' + name)


def test_package_evals_without_calls():
    import json
    spec = importlib.util.spec_from_file_location('structured_skill', PACKAGE / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = [json.loads(line) for line in (PACKAGE / 'evals/cases.jsonl').read_text().splitlines()]
    assert len(cases) >= 16
    for case in cases:
        actual = asyncio.run(module.run(case['input'], NoCalls()))
        ok, reason = skala.score_case(case['expected'], actual, 'exact')
        assert ok, (case['name'], reason)
    assert module.canonical_price('1e3') is None
    assert module.canonical_price('123456789012345678901234567890') is None
    assert module.canonical_price(True) is None
    assert module.extract('<p>$7.00</p>')['items'] == []


def test_package_is_code_and_does_not_approve_itself():
    manifest = yaml.safe_load((PACKAGE / 'skill.yaml').read_text())
    assert manifest['id'] == 'tiger.price_structured'
    assert manifest['version'] == '1.0.0'
    assert manifest['rung'] == 3
    assert not manifest.get('task_type')
    assert manifest['eval_threshold'] == 1.0
    assert manifest.get('status') != 'approved'
    assert (PACKAGE / 'CHANGELOG.md').is_file()
