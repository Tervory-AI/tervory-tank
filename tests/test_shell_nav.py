"""Shared sidebar: one shell, Squad pop-out, no sideways scroll at 375px."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_order_squad_popout_and_escape() -> None:
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "shell_nav.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar() -> None:
    env = os.environ.copy()
    result = subprocess.run(
        ["node", "--experimental-strip-types", str(ROOT / "tests" / "shell_browser.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
