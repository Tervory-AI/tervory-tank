"""Real loopback HTTP refusal cancellation preserves the upstream status."""
from pathlib import Path
import subprocess


def test_request_cancellation_preserves_refusal_and_real_errors():
    subprocess.run(
        ["node", "tests/workspace_request_cancel.cjs"],
        cwd=Path(__file__).resolve().parents[1], check=True, timeout=30,
    )
