"""Include the actual WhatsApp Workspace transport/card contract in offline CI."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_actual_whatsapp_workspace_contract():
    result = subprocess.run(['node', str(Path(__file__).with_name('public_contract.cjs'))], cwd=ROOT,
        env={**os.environ, 'COMMAND_TEST_TOOLS': str(ROOT / 'workspace/node_modules'),
             'CLERK_TELEMETRY_DISABLED': '1'}, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
