"""GitHub is a manual validation tool; Tank owns both recurring jobs."""
from pathlib import Path

import yaml


def test_workflow_is_manual_validation_without_tank_access_or_issue_writes():
    text = (Path(__file__).resolve().parents[1] / '.github/workflows/retest.yml').read_text()
    workflow = yaml.safe_load(text)
    assert workflow.get('on', workflow.get(True)) == {'workflow_dispatch': None}
    assert workflow['permissions'] == {'contents': 'read'}
    assert set(workflow['jobs']) == {'validate'}
    assert 'if' not in workflow['jobs']['validate']
    for forbidden in ('TRAINING_TANK_URL', 'TRAINING_JOB_KEY', 'issues:', 'github-script'):
        assert forbidden not in text
