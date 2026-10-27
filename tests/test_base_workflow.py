"""Offline tests for the real Base upload/status/export handlers and tenant boundary."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_base_upload_status_download_and_two_tenants() -> None:
    result = subprocess.run(["node", "tests/base_works.cjs"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
