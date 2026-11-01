"""Offline browser/server contract checks for COMMAND-1 lane B."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_command_window_contract():
    result = subprocess.run(
        ["node", str(ROOT / "tests/command_1b_contract.cjs")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_command_page_boundaries():
    result = subprocess.run(
        ["node", str(ROOT / "tests/command_1b_pages.cjs")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_command_window_header_hides_totals_without_a_selected_chat():
    result = subprocess.run(
        ["node", str(ROOT / "tests/command_window_header.cjs")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
