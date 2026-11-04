"""Run actual Workspace identity resolution without Clerk or network access."""
import subprocess
from pathlib import Path


def test_identity_role_and_organization_matrix():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "tests/acceptance_identity_matrix.cjs"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
