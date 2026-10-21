"""Inside the backup image: real age, synthetic pg_dump, public recipient only.

Run with --network none. Never uses a real database, R2 bucket or restore key.
"""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, '/app/jobs/train')
import backup

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    # Public example from https://github.com/FiloSottile/age#readme.
    # This fixture is never used by the backup worker itself.
    recipient = 'age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p'
    fixture = b'public synthetic database backup fixture\n'
    test_bin = root / 'bin'
    test_bin.mkdir()
    dump = test_bin / 'pg_dump'
    dump.write_text('#!/usr/local/bin/python\nimport sys\nsys.stdout.buffer.write(' + repr(fixture) + ')\n')
    dump.chmod(0o700)
    os.environ['PATH'] = str(test_bin) + ':' + os.environ['PATH']
    os.environ['DATABASE_URL'] = 'postgresql://fixture@unreachable.invalid:5432/fixture'
    os.environ['R2_BACKUP_RECIPIENT'] = recipient
    encrypted = root / 'dump.age'
    asyncio.run(backup.encrypted_dump(encrypted))
    cipher = encrypted.read_bytes()
    assert cipher.startswith(b'age-encryption.org/v1')
    assert fixture not in cipher
print('PASS: real age encryption of a synthetic dump; no private key; network disabled')
