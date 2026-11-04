"""Render actual account menu consumers with disposable props, without a server."""
import subprocess
from pathlib import Path


def test_remaining_account_menu_destinations():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "tests/remaining_menu_nav.cjs"], cwd=root,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
