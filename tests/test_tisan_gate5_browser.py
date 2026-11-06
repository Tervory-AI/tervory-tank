"""Actual contact form on a slow phone, using the existing local check toolchain."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def test_approved_contact_keyboard_labels_contrast_error_retry_and_mobile_performance(tmp_path):
    root = Path(__file__).resolve().parents[1]
    template = root / 'agents/tisan/templates/next-site'
    for name in ('package.json', 'lighthouserc.cjs'):
        shutil.copy2(template / name, tmp_path / name)
    shutil.copytree(template / 'scripts', tmp_path / 'scripts')
    (tmp_path / 'sections').mkdir()
    shutil.copy2(template / 'sections/manifest.json', tmp_path / 'sections/manifest.json')
    (tmp_path / 'node_modules').symlink_to(template / 'node_modules', target_is_directory=True)
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED':'1', 'NPM_CONFIG_OFFLINE':'true'}
    result = subprocess.run(['node', str(root / 'tests/tisan_gate5_browser.cjs')], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    assert proof['keyboard'] and proof['labels'] and proof['contrast'] and proof['retry']
    assert proof['performance'] >= 0.9 and proof['externalRequests'] == 0
