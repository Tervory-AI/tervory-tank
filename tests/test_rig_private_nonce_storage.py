"""The shipped private worker protects replay without shared DB credentials."""
import os
from pathlib import Path
import subprocess
import sys

import yaml


def test_private_worker_lifespan_uses_its_existing_volume(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / 'agents/rig/docker-compose.yml').read_text())
    brain = config['services']['rig-brain']
    assert not any('DATABASE' in name for name in brain['environment'])
    assert brain['profiles'] == ['brain']
    packages = tmp_path / 'packages'
    packages.mkdir()
    (packages / 'brain').symlink_to(root / 'agents/_brain', target_is_directory=True)
    env = dict(os.environ, DATA_DIR=str(tmp_path / 'data'),
        TANK_KEY='placeholder-rig-key',
        PYTHONPATH=os.pathsep.join(map(str, (packages, root / 'agents/rig', root / 'agents/_chassis'))))
    env.pop('DATABASE_URL', None)
    code = '''
import asyncio
import time
from rig_brain.service import app, lifespan
from chassis.sqlite_nonces import SQLiteNonces
async def check():
    async with lifespan(app):
        assert not hasattr(app.state, 'pool')
        store = app.state.assertion_nonces
        assert isinstance(store, SQLiteNonces)
        assert await store.claim('placeholder-tenant', 'placeholder-nonce', time.time()+60)
    async with lifespan(app):
        assert not await app.state.assertion_nonces.claim('placeholder-tenant', 'placeholder-nonce', time.time()+60)
asyncio.run(check())
'''
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
