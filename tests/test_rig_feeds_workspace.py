"""Execute the Workspace authorization and upload boundary tests with Node."""

import subprocess
from pathlib import Path


def test_retailer_workspace_route_and_server_identity():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["node", "tests/rig_feeds_admin_route.test.cjs"], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
