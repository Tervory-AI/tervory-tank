"""Run the offline client-workspace reconcile test (fake Clerk, fake Tank) in the full suite."""
import subprocess
from pathlib import Path


def test_client_workspaces_reconcile_offline():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "tests/client_workspaces/reconcile.cjs"],
        cwd=root, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
