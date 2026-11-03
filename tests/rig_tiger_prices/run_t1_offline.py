"""Run Tiger/Rig suites on a disposable, trust-authenticated loopback PostgreSQL.

Uses the existing free postgres:16 image (including pg_trgm). No production DSN
or password is read. pytest-socket prohibits outside network access.
"""
from pathlib import Path
import os
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
name = 'codex-tiger-t1-offline-' + uuid4().hex
subprocess.run(['docker','run','--detach','--rm','--name',name,
    '--memory','512m','--cpus','1','-e','POSTGRES_HOST_AUTH_METHOD=trust',
    '-p','127.0.0.1::5432','postgres:16'], check=True, capture_output=True)
try:
    for attempt in range(100):
        ready = subprocess.run(['docker','exec',name,'pg_isready','-U','postgres','-d','postgres'], capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(.3)
    else:
        raise RuntimeError('Disposable PostgreSQL did not become ready')
    address = subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip()
    assert address.startswith('127.0.0.1:')
    uri = f'postgresql://postgres@{address}/postgres'
    env = {**os.environ,'POOL_SCHEMA_DATABASE_URL':uri,'TIGER_MAIL_TEST_DATABASE_URL':uri}
    selection = sys.argv[1:] or [*map(str,sorted((ROOT/'tests').glob('test_tiger*.py'))),
        'tests/rig_tiger_prices','tests/test_command.py','tests/test_personal_tokens.py']
    # Match the normal offline CI timeout; database fixture setup is included.
    command = [sys.executable,'-m','pytest',*selection,'-q','--tb=short','--timeout=300','--disable-socket',
        '--allow-unix-socket','--allow-hosts=127.0.0.1,::1']
    result = subprocess.run(command,cwd=ROOT,env=env)
finally:
    subprocess.run(['docker','rm','--force',name],check=True,capture_output=True)
sys.exit(result.returncode)
