"""US-only route guards; no fabricated legal answer or saved matter."""

import subprocess
from pathlib import Path


def test_real_workspace_helper_never_routes_to_za():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["node", "tests/zenas_backend_routes.mjs"], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
