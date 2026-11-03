"""Exercise the existing /chats presenter without introducing UI wording or layout."""
import subprocess
from pathlib import Path


def test_existing_build_card_shows_quality_results():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', '--test', 'tests/tisan_quality_card.test.cjs'], cwd=root,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
