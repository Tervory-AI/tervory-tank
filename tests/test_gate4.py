import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_saturday_dry_run_and_day_zero():
    result = subprocess.run(['bash', 'scripts/workspace-saturday.sh', '--dry-run'], cwd=ROOT,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'no work was submitted' in result.stdout
    assert 'Gate 3:' in result.stdout
    assert 'one task submission' in result.stdout


def test_saturday_refuses_a_live_launch():
    result = subprocess.run(['bash', 'scripts/workspace-saturday.sh'], cwd=ROOT,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 2
    assert 'Use --dry-run' in result.stderr
