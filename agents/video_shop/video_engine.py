"""Bounded FFmpeg vision and Rig search; uncertain matches stay in review."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from rigbox.rank import search

MAX_BYTES = 32 * 1024 * 1024


async def command(*args, timeout=45):
    if args[0] == 'ffmpeg':
        args = list(args)
        args[1:1] = ['-threads', '1', '-filter_threads', '1', '-filter_complex_threads', '1']
        args[-1:-1] = ['-threads', '1']
    process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.DEVNULL)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise ValueError('media_decode')
    return output


async def frames(path: Path):
    # Disable network protocols inside the decoder. At most 120 samples / 10 minutes.
    raw = await command('ffmpeg', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                        '-format_whitelist', 'mov,matroska,webm,avi',
                        '-i', str(path), '-t', '600', '-vf', 'fps=1/5:start_time=0:round=up,scale=32:32',
                        '-frames:v', '120', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1')
    return [raw[i:i + 3072] for i in range(0, len(raw), 3072) if len(raw[i:i + 3072]) == 3072]


def similarity(left: bytes, right: bytes) -> float:
    return 1 - sum(abs(a - b) for a, b in zip(left, right)) / (3072 * 255)


class Repository:
    """Tenant-qualified durable media and revision-controlled reviews."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS videos (tenant TEXT, id TEXT, body TEXT, '
                       'PRIMARY KEY(tenant,id))')

    def db(self):
        return sqlite3.connect(self.root / 'video-shop.sqlite', timeout=10)

    def directory(self, tenant):
        path = self.root / hashlib.sha256(tenant.encode()).hexdigest()
        path.mkdir(exist_ok=True)
        return path

    def get(self, tenant, identifier):
        with self.db() as db:
            row = db.execute('SELECT body FROM videos WHERE tenant=? AND id=?', (tenant, identifier)).fetchone()
        if not row:
            raise KeyError(identifier)
        return json.loads(row[0])

    def list(self, tenant):
        with self.db() as db:
            rows = db.execute('SELECT body FROM videos WHERE tenant=? ORDER BY rowid DESC LIMIT 100',
                              (tenant,)).fetchall()
        return [{key: value for key, value in json.loads(row[0]).items()
                 if key in {'id', 'status', 'duration', 'revision'}} for row in rows]

    def save(self, tenant, body, expected=None):
        with self.db() as db:
            if expected is None:
                db.execute('INSERT INTO videos VALUES (?,?,?)', (tenant, body['id'], json.dumps(body)))
            else:
                result = db.execute('UPDATE videos SET body=? WHERE tenant=? AND id=? '
                                    "AND json_extract(body,'$.revision')=?",
                                    (json.dumps(body), tenant, body['id'], expected))
                if result.rowcount != 1:
                    raise ValueError('review_conflict')


class Engine:
    def __init__(self, rig, repository):
        self.rig, self.repository = rig, repository
        self.lock = asyncio.Semaphore(1)

    async def ingest(self, tenant, video: bytes, transcript: list, references: dict, *, permission=None):
        if not isinstance(transcript, list) or not isinstance(references, dict):
            raise ValueError('media_input')
        if not video or len(video) > MAX_BYTES or len(transcript) > 1000 or len(references) > 100:
            raise ValueError('media_limit')
        for segment in transcript:
            if not isinstance(segment, dict):
                raise ValueError('transcript')
            start, end = float(segment['start']), float(segment['end'])
            if not (0 <= start < end <= 600) or not isinstance(segment['text'], str) or len(segment['text']) > 10000:
                raise ValueError('transcript')
        identifier = uuid4().hex
        path = self.repository.directory(tenant) / (identifier + '.mp4')
        path.write_bytes(video)
        try:
            async with self.lock:
                metadata = json.loads(await command(
                    'ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                    '-format_whitelist', 'mov,matroska,webm,avi', '-show_entries', 'format=duration,format_name',
                    '-of', 'json', str(path)))
                duration = float(metadata['format']['duration'])
                if not (0 < duration <= 600):
                    raise ValueError('duration_limit')
                samples = await frames(path)
                if not samples:
                    raise ValueError('no_frames')
                products = await self.rig.store.products(tenant)
                catalogue = {str(p.get('sku') or p.get('id')): p for p in products if p.get('active', True)}
                # Reuse store catalogue images automatically. Explicit uploads can
                # replace inaccessible images without changing catalogue rows.
                from .video_media import download
                images = dict(references)
                image_errors = []
                slots = asyncio.Semaphore(4)

                async def fetch_reference(sku, product):
                    url = product.get('image_url') or product.get('image')
                    if sku in images or not url:
                        return
                    async with slots:
                        try:
                            images[sku] = await asyncio.to_thread(download, url, 2 * 1024 * 1024)
                        except (ValueError, OSError):
                            image_errors.append(sku)

                tasks = [asyncio.create_task(fetch_reference(sku, product))
                         for sku, product in list(catalogue.items())[:100]]
                if tasks:
                    _, pending = await asyncio.wait(tasks, timeout=45)
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    image_errors.extend(['fetch_timeout'] * len(pending))
                fingerprints = {}
                for sku, image in images.items():
                    if sku not in catalogue or len(image) > 2 * 1024 * 1024:
                        raise ValueError('reference_invalid')
                    reference = path.with_suffix('.reference')
                    reference.write_bytes(image)
                    try:
                        fingerprints[sku] = await command(
                            'ffmpeg', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                            '-format_whitelist', 'png_pipe,jpeg_pipe,ppm_pipe',
                            '-i', str(reference), '-vf', 'scale=32:32', '-frames:v', '1',
                            '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1')
                        if len(fingerprints[sku]) != 3072:
                            raise ValueError('reference_invalid')
                    except (ValueError, TimeoutError):
                        fingerprints.pop(sku, None)
                        if sku in references:
                            raise
                        image_errors.append(sku)
                    finally:
                        reference.unlink(missing_ok=True)
                moments = []
                for index, frame in enumerate(samples):
                    start, end = index * 5, min((index + 1) * 5, duration)
                    text = ' '.join(str(s['text']) for s in transcript
                                    if float(s['start']) < end and float(s['end']) > start)
                    ids = search({'tenant_id': tenant, 'products': products, 'q': text, 'limit': 5})['ids']
                    # Search proposes candidates; require a complete name or SKU in the
                    # transcript before claiming text evidence for that product.
                    normalized = ' ' + re.sub(r'[^\w]+', ' ', text.casefold()).strip() + ' '
                    evidence = {sku: {'transcript': True} for sku in ids if sku in catalogue
                                and any(' ' + re.sub(r'[^\w]+', ' ', str(term).casefold()).strip() + ' '
                                        in normalized for term in (sku, catalogue[sku].get('name', '')) if term)}
                    for sku, reference in fingerprints.items():
                        score = similarity(frame, reference)
                        if score >= .96:
                            evidence.setdefault(sku, {})['vision_score'] = round(score, 4)
                    for sku, proof in evidence.items():
                        moments.append({'start': start, 'end': end, 'product_id': sku,
                                        'evidence': proof, 'approved': False})
                body = {'id': identifier, 'duration': duration,
                        'media_type': 'video/webm' if 'webm' in metadata['format']['format_name'] else 'video/mp4',
                        'revision': 1, 'status': 'draft', 'moments': moments,
                        'permission': permission,
                        'receipt': {'route': 'code', 'model_calls': 0, 'media_sha256': hashlib.sha256(video).hexdigest(),
                                    'vision': 'ffmpeg-rgb-distance-v1', 'samples': len(samples),
                                    'reference_images': len(fingerprints), 'image_errors': image_errors,
                                    'catalogue_images_truncated': len(catalogue) > 100}}
                self.repository.save(tenant, body)
                return body
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    async def review(self, tenant, identifier, revision, moments):
        body = self.repository.get(tenant, identifier)
        products = {str(p.get('sku') or p.get('id')) for p in await self.rig.store.products(tenant)
                    if p.get('active', True)}
        if len(moments) > 1000:
            raise ValueError('moments_limit')
        cleaned = []
        for m in moments:
            start, end = float(m['start']), float(m['end'])
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= body['duration']):
                raise ValueError('timestamp')
            if m['product_id'] not in products or type(m['approved']) is not bool:
                raise ValueError('product')
            cleaned.append({'start': start, 'end': end, 'product_id': m['product_id'], 'approved': m['approved']})
        body.update(revision=revision + 1, moments=cleaned, status='reviewed')
        self.repository.save(tenant, body, expected=revision)
        return body
