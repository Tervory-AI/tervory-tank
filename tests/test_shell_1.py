"""SHELL-1: Squad is one sidebar item and the member list opens beside it."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_squad_popout_opens_closes_and_keeps_skala_for_founders() -> None:
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests" / "shell_1.test.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
