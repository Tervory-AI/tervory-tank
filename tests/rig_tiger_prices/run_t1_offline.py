"""Run Tiger's requested suites with disposable, trust-authenticated loopback PG.

No production DSN is read. pytest-socket prohibits outside network access.
"""
from pathlib import Path
import os
import socket
import subprocess
import sys
from urllib.parse import urlsplit

import pgserver

ROOT = Path(__file__).resolve().parents[2]
server = pgserver.get_server(ROOT / '.venv/tiger-t1-offline-postgres')
with socket.socket() as reservation:
    reservation.bind(('127.0.0.1', 0))
    port = reservation.getsockname()[1]

# pgserver initializes and owns this disposable cluster. Restart the same cluster
# with a loopback listener because the existing Rig suite requires a TCP DSN.
pgserver.pg_ctl(['restart', '-m', 'fast', '-l', str(server.log),
                 '-o', f'-h 127.0.0.1 -p {port}'], pgdata=server.pgdata,
                user=server.system_user, timeout=15)
user = urlsplit(server.get_uri()).username
# No password, API key, production address or credential lookup is involved.
env = {**os.environ, 'POOL_SCHEMA_DATABASE_URL': f'postgresql://{user}@127.0.0.1:{port}/postgres'}
command = [sys.executable, '-m', 'pytest', *map(str, sorted((ROOT / 'tests').glob('test_tiger*.py'))),
           'tests/rig_tiger_prices', '-q', '--tb=short', '--timeout=90', '--disable-socket',
           '--allow-unix-socket', '--allow-hosts=127.0.0.1,::1']
result = subprocess.run(command, cwd=ROOT, env=env)
sys.exit(result.returncode)
