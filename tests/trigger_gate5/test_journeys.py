import os
import signal
import subprocess
from pathlib import Path


def test_real_chromium_client_journeys(tmp_path):
    """Run the Chromium launch journeys and always reap the process group.

    Under shared-box load a stuck or timed-out node/Chromium child used to be
    left behind when pytest-timeout interrupted communicate(), which then made
    the next journey run even slower. Kill the session on timeout so orphans
    cannot accumulate. Assertions are unchanged.
    """
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        ["node", str(Path(__file__).with_name("journeys.cjs"))],
        cwd=root,
        env={**os.environ, "TRIGGER_LAUNCH_EVIDENCE_DIR": str(tmp_path)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        # Stay under the shared pytest --timeout=90 so we can reap cleanly
        # instead of leaving Chromium orphans after a mid-select interrupt.
        stdout, stderr = proc.communicate(timeout=85)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        raise AssertionError(
            "Chromium journeys exceeded 85s; killed process group to avoid orphans.\n"
            + (stdout or "")
            + (stderr or "")
        )
    assert proc.returncode == 0, (stdout or "") + (stderr or "")
    assert "PASS launch journeys:" in (stdout or "")


def test_request_deadlines_role_binding_and_safe_errors():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("requests.cjs"))],
        cwd=root,
        env={**os.environ, "COMMAND_TEST_TOOLS": str(root / "workspace/node_modules")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS bounded headers/body" in result.stdout
