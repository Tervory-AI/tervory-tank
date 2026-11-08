"""The packaged coordinator uses private storage, not shared DB credentials."""
import os
from pathlib import Path
import subprocess
import sys

import yaml


def test_private_coordinator_lifespan_uses_existing_volume(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / 'agents/radix/docker-compose.yml').read_text())
    brain = config['services']['radix-brain']
    assert not any('DATABASE' in name for name in brain['environment'])
    assert brain['profiles'] == ['brain']
    env = dict(os.environ, DATA_DIR=str(tmp_path / 'data'), RADIX_BRAIN_ENABLED='true',
        TANK_KEY='placeholder-radix-key',
        PYTHONPATH=os.pathsep.join(map(str, (root / 'agents/radix', root / 'agents/_chassis'))))
    env.pop('DATABASE_URL', None)
    code = '''
import asyncio
import time
from radix_brain_service import app, lifespan
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
