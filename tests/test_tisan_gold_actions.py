"""Execute the actual server actions with Clerk/Tank boundary stubs."""
from pathlib import Path
import subprocess


def test_founder_server_actions():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["node", "--test", "tests/tisan_gold_actions.test.cjs"], cwd=root,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
