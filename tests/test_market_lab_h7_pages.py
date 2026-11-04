"""Production page views and server-only read loader on offline HTTP fixtures."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_h7_views_and_tenant_loaders_offline():
    result = subprocess.run(['node', '--experimental-strip-types', '--import',
        str(ROOT / 'tests/market_lab_h7_register.mjs'), '--test',
        str(ROOT / 'workspace/app/market-lab/h7.test.tsx')], cwd=ROOT,
        text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
