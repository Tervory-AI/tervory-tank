"""Run the unchanged Enforce probe on disposable GitHub CI networks only."""
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.environ.get('AUTUMBRA_A2_CI_PROBE') != '1', reason='CI-only compose isolation proof')


def test_existing_probe_on_local_compose_networks():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Do not run this probe on a live host'
    project = 'autumbra-a2-placeholder-' + uuid.uuid4().hex[:10]
    command = ['docker', 'compose', '-p', project, '-f', str(ROOT / 'tests/autumbra_a2/docker-compose.probe.yml')]
    def run(args, *, check=True, timeout=600):
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        if check:
            assert result.returncode == 0, result.stdout + result.stderr
        return result
    try:
        run(command + ['up', '-d', '--build'])
        probe = run(command + ['exec', '-T', 'enforce', 'python', '-m', 'ghost.enforce_isolation_probe'], timeout=90)
        report = json.loads(probe.stdout)
        print(probe.stdout)
        assert report['report']['ok'] is True
        assert report['probe']['public_443'] is False
        assert not any(report['probe']['resolve'].values())
        # A deliberately shared synthetic hub must fail the very same probe.
        identity = run(command + ['ps', '-q', 'enforce']).stdout.strip()
        assert re.fullmatch(r'[0-9a-f]{12,64}', identity)
        run(['docker', 'network', 'connect', project + '_placeholder-hub', identity])
        leaked = run(command + ['exec', '-T', 'enforce', 'python', '-m', 'ghost.enforce_isolation_probe'],
                     check=False, timeout=90)
        print(leaked.stdout)
        assert leaked.returncode == 1
        assert json.loads(leaked.stdout)['report']['ok'] is False
        assert json.loads(leaked.stdout)['probe']['resolve']['tank'] is True
    finally:
        run(command + ['down', '-v', '--remove-orphans'], check=False)
