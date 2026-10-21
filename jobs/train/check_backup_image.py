"""Inside the backup image: real age, synthetic pg_dump, throwaway test identity.

Run with --network none. Never uses a real database, R2 bucket or restore key.
"""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, '/app/jobs/train')
import backup

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    identity = root / 'test-only-identity'
    subprocess.run(['age-keygen', '-o', str(identity)], check=True, capture_output=True)
    recipient = subprocess.check_output(['age-keygen', '-y', str(identity)], text=True).strip()
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
    restored = subprocess.check_output(['age', '--decrypt', '--identity', str(identity), str(encrypted)])
    assert restored == fixture
print('PASS: real age encryption/decryption round trip with synthetic dump and network disabled')
