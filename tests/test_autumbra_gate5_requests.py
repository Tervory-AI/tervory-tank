from pathlib import Path
import subprocess


def test_actual_frontend_requests_with_offline_failure_injection():
    subprocess.run(['node', 'tests/autumbra_gate5_requests.cjs'],
                   cwd=Path(__file__).resolve().parents[1], check=True, timeout=60)
