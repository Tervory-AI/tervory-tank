"""Kill and reap expensive untrusted parsers; no sockets, shell or file extraction."""
import asyncio
import json
import os
from pathlib import Path
import sys

from core.document_read import ReadError

TIMEOUT = 90
UNREADABLE = 'This file could not be read. Check that it opens and is not password protected.'


async def extract(name, data):
    env = {'PYTHONPATH': str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get('PYTHONPATH', ''),
           'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'core.document_process', '--worker', name,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env)
    try:
        raw, _ = await asyncio.wait_for(process.communicate(data), timeout=TIMEOUT)
    except BaseException:
        if process.returncode is None:
            process.kill()
        # Drain pipes after killing: waiting alone can deadlock on a full stdout
        # buffer. Cleanup has its own deadline, including on caller cancellation.
        try:
            await asyncio.wait_for(process.communicate(), timeout=5)
        except Exception:
            pass
        await asyncio.wait_for(process.wait(), timeout=5)
        raise
    if process.returncode:
        raise ReadError(UNREADABLE)
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        raise ReadError(UNREADABLE) from None
    if not isinstance(value, dict):
        raise ReadError(UNREADABLE)
    if 'error' in value:
        raise ReadError(value['error'])
    return value


if __name__ == '__main__':
    import resource
    # Existing input/text/page limits still apply. These bound parser resources,
    # without changing the product's file, page, row or text allowances.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    def no_network(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'}:
            raise RuntimeError('Document parsers cannot open external connections')
    sys.addaudithook(no_network)
    from core.document_read import extract as read
    try:
        print(json.dumps(read(sys.argv[2], sys.stdin.buffer.read())))
    except ReadError as exc:
        print(json.dumps({'error': str(exc)}))
