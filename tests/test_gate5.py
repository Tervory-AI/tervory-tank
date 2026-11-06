import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_security_and_failures():
    result = subprocess.run(['node', 'tests/gate5_contract.cjs'], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_chat_journeys_and_recovery(tmp_path):
    result = subprocess.run(['node', 'tests/command_1b_browser.cjs'], cwd=ROOT,
                            env={**os.environ, 'COMMAND_TEST_OUTPUT': str(tmp_path)},
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


def test_client_launch_journeys():
    result = subprocess.run(['node', 'tests/gate5_browser.cjs'], cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
