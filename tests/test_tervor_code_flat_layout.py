"""Real entrypoint in the deployed flat layout, with forbidden import/I/O guards."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from tank.training_jobs import coding

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('layout', ['flat', 'package'])
def test_opli_dry_run_without_tank_package_credentials_or_provider_access(tmp_path, layout):
    app = tmp_path / 'app'
    app.mkdir()
    if layout == 'flat':
        assert 'COPY training_jobs ./training_jobs' in (ROOT / 'tank/Dockerfile').read_text()
        # Match Dockerfile's flat *.py and training_jobs COPY destinations, with
        # no repository root, tests directory, installed Tank package or deps.
        for name in ('tervor_code.py', 'tervor_registry.py', 'tervor_dataset.py', 'tervor_gold.py'):
            shutil.copyfile(ROOT / 'tank' / name, app / name)
        shutil.copytree(ROOT / 'tank/training_jobs', app / 'training_jobs',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        module, search = 'training_jobs.run', str(app)
    else:
        module, search = 'tank.training_jobs.run', str(ROOT)
    script = '''
import importlib.abc
import json
import runpy
import socket
import sys

flat_layout = sys.argv[1] == 'flat'
class ForbiddenImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        denied = {'asyncpg', 'huggingface_hub', 'torch', 'transformers', 'datasets', 'trl', 'peft'}
        if flat_layout:
            denied.add('tank')
        if fullname.split('.')[0] in denied:
            raise AssertionError('Dry-run imported forbidden dependency: ' + fullname)
sys.meta_path.insert(0, ForbiddenImports())
real_socket = socket.socket
class NoNetwork(real_socket):
    def __new__(cls, family=-1, *args, **kwargs):
        if family != socket.AF_UNIX:
            raise AssertionError('Dry-run attempted a network socket')
        return super().__new__(cls, family, *args, **kwargs)
socket.socket = NoNetwork
def no_network(*args, **kwargs):
    raise AssertionError('Dry-run attempted network lookup/connection')
socket.getaddrinfo = no_network
socket.create_connection = no_network
sys.path.insert(0, sys.argv[2])
module = sys.argv[3]
sys.argv = [module, '--agent', 'opli', '--dry-run', '--json']
runpy.run_module(module, run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-I', '-S', '-c', script, layout, search, module],
        cwd=app, env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'TANK_REGION': 'us-east'},
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert manifest == coding.dry_run()
    assert manifest['status'] == 'blocked' and manifest['submitted'] is False
    assert manifest['paid_jobs'] == manifest['provider_requests'] == 0
    assert manifest['counts'] == {'training': 1, 'fit_validation': 1, 'gold': 5, 'evaluation_only': 2}
    assert all(item == {'status': 'missing', 'value': None} for item in manifest['selection'].values())
