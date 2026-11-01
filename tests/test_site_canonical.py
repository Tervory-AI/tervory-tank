"""Exercise the actual Node marketing server offline, with isolated signup storage."""
from pathlib import Path
import subprocess


def test_marketing_alias_redirect_and_existing_apex_routes():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", str(root / "tests/test_site_canonical.mjs")],
        cwd=root, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
