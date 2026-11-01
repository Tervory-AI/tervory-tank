"""Run the actual-source offline Tank admission regression in hosted pytest CI."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tank_founder_boundary():
    result = subprocess.run(
        ["node", str(ROOT / "tests/tank_founder_boundary.cjs")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
