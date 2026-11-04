"""Actual service worker policy, install metadata and exact-brand icon dimensions."""
from pathlib import Path
import subprocess


def test_installable_shell_never_caches_client_data():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', '--test', 'tests/mobile/pwa.test.cjs'], cwd=root,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
