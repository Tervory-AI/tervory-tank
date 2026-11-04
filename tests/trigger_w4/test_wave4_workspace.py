"""Run the real Workspace modules with named offline transport substitutes."""
import os
from pathlib import Path
import subprocess


def test_server_actions_and_public_transport():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(Path(__file__).with_name('workspace.cjs'))],cwd=root,
        env={**os.environ,'COMMAND_TEST_TOOLS':str(root/'workspace/node_modules')},
        capture_output=True,text=True,timeout=60,check=False)
    assert result.returncode==0,result.stdout+result.stderr


def test_tank_paths_reject_ssrf_inputs_before_any_fetch():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(Path(__file__).with_name('ssrf.cjs'))],cwd=root,
        env={**os.environ,'COMMAND_TEST_TOOLS':str(root/'workspace/node_modules')},
        capture_output=True,text=True,timeout=60,check=False)
    assert result.returncode==0,result.stdout+result.stderr
