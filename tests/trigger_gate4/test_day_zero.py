import os
from pathlib import Path
import subprocess


def test_all_client_zero_states_and_missing_setting():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['node', str(Path(__file__).with_name('day_zero.cjs'))], cwd=root,
        env={**os.environ, 'COMMAND_TEST_TOOLS': str(root/'workspace/node_modules')},
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS:' in result.stdout
