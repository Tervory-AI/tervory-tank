import os
from pathlib import Path
import subprocess


def test_real_chromium_client_journeys(tmp_path):
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(Path(__file__).with_name('journeys.cjs'))],cwd=root,
        env={**os.environ,'TRIGGER_LAUNCH_EVIDENCE_DIR':str(tmp_path)},capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'PASS launch journeys:' in result.stdout


def test_request_deadlines_role_binding_and_safe_errors():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(Path(__file__).with_name('requests.cjs'))],cwd=root,
        env={**os.environ,'COMMAND_TEST_TOOLS':str(root/'workspace/node_modules')},capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'PASS bounded headers/body' in result.stdout
