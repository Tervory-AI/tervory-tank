"""Import the actual room entry point from only its Docker COPY payload."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def test_room_image_copies_every_memory_dependency(tmp_path):
    root = Path(__file__).resolve().parents[1]
    image = tmp_path / 'image'
    image.mkdir()
    for line in (root / 'agents/rig/Dockerfile').read_text().splitlines():
        if not line.startswith('COPY '):
            continue
        *sources, destination = shlex.split(line)[1:]
        target = image if destination in {'.', '/app/'} else image / destination.removeprefix('/app/')
        for source in sources:
            original = root / 'agents' / source
            if original.is_dir():
                shutil.copytree(original, target, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                shutil.copyfile(original, target / original.name if target.is_dir() else target)
    env = {name: os.environ[name] for name in ('PATH', 'HOME', 'LANG') if name in os.environ}
    env.update(PYTHONPATH=str(image), PYTHONDONTWRITEBYTECODE='1', DATA_DIR=str(tmp_path / 'data'))
    code = '''
from rigbox.three_d.asgi import app
import rig_memory, rig_memory_api, rig_actor_context, rig_brain_client
assert not rig_memory.memory_enabled()
assert not rig_brain_client.brain_enabled()
assert app is not None
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=image, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
