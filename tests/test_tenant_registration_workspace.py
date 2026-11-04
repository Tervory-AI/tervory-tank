"""Exercise the actual tenant and report helpers with offline Clerk/Tank doubles."""
import subprocess
from pathlib import Path


def test_tenant_identity_survives_optional_report_outage():
    root = Path(__file__).resolve().parents[1]
    for script in ("registration.cjs", "workspace.cjs"):
        result = subprocess.run(
            ["node", f"tests/case_study_reports/{script}"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
