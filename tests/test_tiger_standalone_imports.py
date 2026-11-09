"""Import the actual flat Docker entrypoints without another product on the path."""
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def test_tiger_docker_copy_layout_owns_memory_and_brain_imports(tmp_path):
    root = Path(__file__).resolve().parents[1]
    runtime = tmp_path/'app'
    runtime.mkdir()
    dockerfile = root/'agents/tiger/Dockerfile'
    for line in dockerfile.read_text().splitlines():
        if not line.startswith('COPY '):
            continue
        _, source, destination = shlex.split(line)
        src = root/'agents'/source
        dst = runtime/src.name if destination == '.' else runtime/Path(destination).relative_to('/app')
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    program = '''
from pathlib import Path
from uvicorn.importer import import_from_string
room = import_from_string('app:app')
brain = import_from_string('gates_brain_service:app')
import gates_api, gates_brain, gates_memory
assert room is not brain
assert Path(gates_memory.__file__).parent == Path.cwd()
assert gates_api.Memory is gates_memory.Memory
assert gates_brain.Memory is gates_memory.Memory
assert 'get' in room.openapi()['paths']['/memory']
assert 'post' in brain.openapi()['paths']['/tasks']
'''
    env = dict(os.environ, PYTHONPATH=str(runtime), AGENT_NAME='tiger', PYTHONDONTWRITEBYTECODE='1')
    checked = subprocess.run([sys.executable, '-c', program], cwd=runtime, env=env,
                             capture_output=True, text=True, timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
