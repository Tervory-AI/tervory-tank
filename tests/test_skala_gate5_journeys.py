import json
from pathlib import Path
import subprocess


def run_node(name):
    from finish_proposals import SOURCES
    result = subprocess.run(['node', name], input=json.dumps(SOURCES), text=True,
        capture_output=True, cwd=Path.cwd(), timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_request_boundaries_and_identity_journeys():
    assert '# pass 5' in run_node('tests/skala_gate5_transport.cjs')


def test_browser_client_journeys_phone_accessibility_and_slow_loading():
    assert 'Skala browser journeys passed' in run_node('tests/skala_gate5_browser.cjs')
