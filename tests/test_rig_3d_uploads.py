"""Bounded photo streaming, real signatures and immutable R2 staging."""
import hashlib
import secrets
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from test_rig_3d_engine import job, TENANT
from rigbox.three_d.assets import ForgeFiles, PhotoInputError, StorageError
from rigbox.three_d import assets


class PhotoStream(httpx.AsyncByteStream):
    def __init__(self, prefix, size):
        self.prefix, self.size = prefix, size

    async def __aiter__(self):
        yield self.prefix
        remaining = self.size - len(self.prefix)
        while remaining > 0:
            length = min(remaining, 16_384)
            yield b'x' * length
            remaining -= length


class StorageTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, prefix=b'\xff\xd8\xff', size=100, declared=None, conflict=False):
        self.prefix, self.size, self.declared = prefix, size, declared
        self.conflict = conflict
        self.gets, self.puts = [], []
        self.max_chunk = 0
        self.mismatch = False

    async def handle_async_request(self, request):
        if request.method == 'GET':
            self.gets.append(request.url.path)
            headers = {} if self.declared is None else {'Content-Length': str(self.declared)}
            prefix = self.prefix + (b'changed' if self.mismatch and '/forge/' in request.url.path else b'')
            return httpx.Response(200, stream=PhotoStream(prefix, self.size), headers=headers)
        assert request.method == 'PUT'
        size, digest = 0, hashlib.sha256()
        async for chunk in request.stream:
            size += len(chunk)
            digest.update(chunk)
            self.max_chunk = max(self.max_chunk, len(chunk))
        assert size == int(request.headers['content-length'])
        assert digest.hexdigest() == request.headers['x-amz-content-sha256']
        assert request.headers['if-none-match'] == '*'
        self.puts.append(request.url.path)
        return httpx.Response(412 if self.conflict else 200, stream=PhotoStream(b'', 0))


def files(transport):
    return ForgeFiles('rig', environ={'R2_ACCOUNT_ID': uuid4().hex,
        'R2_ACCESS_KEY_ID_RIG': secrets.token_hex(20), 'R2_SECRET_ACCESS_KEY_RIG': secrets.token_hex(32)},
        transport=transport)


@pytest.mark.asyncio
@pytest.mark.parametrize('suffix,prefix', [('jpg', b'\xff\xd8\xff'), ('jpeg', b'\xff\xd8\xff'), ('png', b'\x89PNG\r\n\x1a\n')])
async def test_photos_stream_in_bounded_chunks_with_signed_hashes(suffix, prefix):
    transport = StorageTransport(prefix=prefix, size=200_000)
    storage = files(transport)
    request = job(source='ai', inputs=[f'{TENANT}/uploads/photo.{suffix}'])
    try:
        await storage.stage(request)
        assert transport.gets == [f'/tervory-rig/us-east/{TENANT}/uploads/photo.{suffix}']
        assert transport.puts == [f'/tervory-rig/forge/{TENANT}/{request.id}/inputs/photo.{suffix}']
        assert transport.max_chunk <= assets.CHUNK_BYTES < transport.size
        # Streaming signatures agree with the existing signer for the same bytes.
        data = b'photo fixture'
        path = transport.puts[0]
        assert storage._signed_digest(path, hashlib.sha256(data).hexdigest()) == storage._sign('PUT', path, '', data)
        storage.region = 'za'
        with pytest.raises(StorageError):
            await storage.stage(request)
        assert len(transport.puts) == 1
    finally:
        await storage.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('suffix,prefix', [('png', b'\xff\xd8\xff'), ('jpg', b'\x89PNG\r\n\x1a\n'), ('jpg', b'<html>'), ('png', b'')])
async def test_extension_alone_never_admits_a_file(suffix, prefix):
    transport = StorageTransport(prefix=prefix, size=max(len(prefix), 8))
    storage = files(transport)
    try:
        with pytest.raises(PhotoInputError, match='JPEG or PNG'):
            await storage.stage(job(source='ai', inputs=[f'{TENANT}/uploads/photo.{suffix}']))
        assert not transport.puts
    finally:
        await storage.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('declared', [None, 10, 20_000_001])
async def test_per_photo_limit_counts_streamed_bytes_and_rejects_oversized_headers(declared):
    transport = StorageTransport(size=20_000_001, declared=declared)
    storage = files(transport)
    try:
        assert assets.PHOTO_MAX_BYTES == 20_000_000
        with pytest.raises(PhotoInputError, match='20 MB'):
            await storage.stage(job(source='ai', inputs=[f'{TENANT}/uploads/photo.jpg']))
        assert not transport.puts
    finally:
        await storage.close()


@pytest.mark.asyncio
async def test_whole_job_limit_is_checked_before_any_write_and_scratch_is_removed(monkeypatch, tmp_path):
    assert assets.JOB_INPUT_MAX_BYTES == 1_000_000_000
    # Exercise accumulation at small sizes without writing a gigabyte in a test.
    monkeypatch.setattr(assets, 'JOB_INPUT_MAX_BYTES', 249)
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    transport = StorageTransport(size=100)
    storage = files(transport)
    try:
        with pytest.raises(PhotoInputError, match='1 GB'):
            await storage.stage(job())
        assert len(transport.gets) == 3 and not transport.puts
        assert list(tmp_path.iterdir()) == []
        with pytest.raises(ValidationError):
            job(inputs=[f'{TENANT}/uploads/{n}.jpg' for n in range(71)])
    finally:
        await storage.close()


@pytest.mark.asyncio
async def test_existing_job_inputs_are_compared_without_overwriting():
    transport = StorageTransport(conflict=True)
    storage = files(transport)
    request = job(source='ai', inputs=[f'{TENANT}/uploads/photo.jpg'])
    try:
        await storage.stage(request)
        transport.mismatch = True
        with pytest.raises(StorageError, match='different input'):
            await storage.stage(request)
    finally:
        await storage.close()
