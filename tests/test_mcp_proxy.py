"""Real TypeScript proxy checks, using the Workspace lockfile's TypeScript."""
import subprocess
from pathlib import Path


def test_public_mcp_proxy():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', str(root / 'tests/mcp_proxy.cjs')], cwd=root,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
