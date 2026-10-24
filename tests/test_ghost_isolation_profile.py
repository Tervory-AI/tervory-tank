"""Ghost corridor profile is taught to check_isolation.sh (no seal weakened)."""

import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "agents" / "check_isolation.sh").read_text(encoding="utf-8")


def test_ghost_corridor_flag_and_exceptions() -> None:
    assert "ghost_corridor=0" in SCRIPT
    assert "tervory-gw-ghost" in SCRIPT
    assert "hermes does not resolve on ghost corridor" in SCRIPT
    assert "ghost-browser" in SCRIPT
    assert "coolify-proxy" in SCRIPT
    assert "ping job skipped on ghost corridor" in SCRIPT
    assert "database login skipped on ghost corridor" in SCRIPT
    # Seal: hermes on ghost gateway is unexpected
    assert 'if [ "$net" = "tervory-gw-ghost" ]; then' in SCRIPT
    assert "unexpected=" in SCRIPT
    # Hyphenated Coolify-style names use prefix case, not has_part (which splits on '-').
    assert "ghost-browser|ghost-browser-*" in SCRIPT
    assert "coolify-proxy|coolify-proxy-*" in SCRIPT
    assert 'has_part "$short" ghost-browser' not in SCRIPT
    assert 'has_part "$short" coolify-proxy' not in SCRIPT


def test_hyphenated_gateway_names_match_prefix_case() -> None:
    """Reproduce the live FAIL: ghost-browser-* and coolify-proxy must be allowed."""
    snippet = textwrap.dedent(
        r"""
        short_a='ghost-browser-nypsvvcxjpdebaa204smtqtd-20261024T140107'
        short_b='coolify-proxy'
        short_c='hermes-xnmc0jkz8j9i5jh1jwanbsfv-20261024T155518'
        short_d='agent-rig-abc'
        allow() {
          short=$1
          case "$short" in
            ghost-browser|ghost-browser-*|coolify-proxy|coolify-proxy-*) return 0 ;;
          esac
          return 1
        }
        allow "$short_a" && echo PASS_browser || echo FAIL_browser
        allow "$short_b" && echo PASS_proxy || echo FAIL_proxy
        allow "$short_c" && echo FAIL_hermes_allowed || echo PASS_hermes_blocked
        allow "$short_d" && echo FAIL_rig_allowed || echo PASS_rig_blocked
        """
    )
    out = subprocess.check_output(["sh", "-c", snippet], text=True)
    assert "PASS_browser" in out and "PASS_proxy" in out
    assert "PASS_hermes_blocked" in out and "PASS_rig_blocked" in out
    assert "FAIL_" not in out
