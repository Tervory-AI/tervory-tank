"""Exercise the actual Control tile and server actions with offline service fixtures."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_founder_squad_actions_and_tile():
    if not shutil.which('node') or not (ROOT / 'workspace/node_modules/typescript').exists():
        pytest.skip('Workspace packages are installed by full CI')
    result = subprocess.run(['node', 'tests/command-squads-ui.cjs'], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
