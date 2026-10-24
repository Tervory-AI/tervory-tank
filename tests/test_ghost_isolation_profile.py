"""Ghost corridor profile is taught to check_isolation.sh (no seal weakened)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "agents" / "check_isolation.sh").read_text(encoding="utf-8")


def test_ghost_corridor_flag_and_exceptions() -> None:
    assert "ghost_corridor=0" in SCRIPT
    assert 'tervory-gw-ghost' in SCRIPT
    assert "hermes does not resolve on ghost corridor" in SCRIPT
    assert "ghost-browser" in SCRIPT
    assert "coolify-proxy" in SCRIPT
    assert "ping job skipped on ghost corridor" in SCRIPT
    assert "database login skipped on ghost corridor" in SCRIPT
    # Seal: hermes on ghost gateway is unexpected
    assert 'if [ "$net" = "tervory-gw-ghost" ]; then' in SCRIPT
    assert "unexpected=" in SCRIPT
