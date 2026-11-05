"""Run actual public corridor and existing Command rendering contracts in CI."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('script', ['public_contract.cjs', 'middleware_contract.cjs', 'card_contract.cjs'])
def test_workspace_bot_contract(script):
    result = subprocess.run(
        ['node', str(Path(__file__).with_name(script))], cwd=ROOT,
        env={**os.environ, 'COMMAND_TEST_TOOLS': str(ROOT / 'workspace/node_modules'),
             'TRIGGER_SIGNIN_TELEMETRY_DISABLED': '1'},
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
