"""Real Workspace projection: complete Radix findings without widening other cards."""
import subprocess
from pathlib import Path


def test_radix_chat_allowlist_and_complete_findings():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", str(root / "tests/radix_chat_presentation.cjs")],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
