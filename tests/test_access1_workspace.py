"""Server-side origin validation with the real access route."""
import subprocess
from pathlib import Path


def test_access_route_behind_tls_proxy():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["node", "tests/access1-route.cjs"], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
