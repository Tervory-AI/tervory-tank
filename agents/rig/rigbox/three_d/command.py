"""Resumable operator command using the existing room/Forge/review corridor."""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .assets import ForgeFiles, PHOTO_MAX_BYTES, JOB_INPUT_MAX_BYTES
from .contracts import Job, Review


class CommandError(RuntimeError):
    pass


def read_file(path, maximum):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise CommandError('Choose a regular file within the size limit.')
    with path.open('rb') as source:
        value = source.read(maximum + 1)
    if len(value) > maximum:
        raise CommandError('The file exceeds the size limit.')
    return value


def write_file(directory, name, data):
    target = directory / name
    # Never follow a symlink or overwrite a different product under a retry.
    with tempfile.NamedTemporaryFile(dir=directory, prefix='.forge-', delete=True) as output:
        output.write(data); output.flush(); os.fsync(output.fileno())
        try:
            os.link(output.name, target)
        except FileExistsError:
            if target.is_symlink() or read_file(target, max(len(data), 1)) != data:
                raise CommandError('The output already exists with different contents.') from None


def prepare(manifest, photos):
    body = dict(manifest)
    uploads, total = [], 0
    for index, path in enumerate(photos):
        data = read_file(path, PHOTO_MAX_BYTES); total += len(data)
        suffix = path.suffix.lower()
        if not ((suffix in {'.jpg', '.jpeg'} and data.startswith(b'\xff\xd8\xff')) or
                (suffix == '.png' and data.startswith(b'\x89PNG\r\n\x1a\n'))):
            raise CommandError('Each photo must contain a JPEG or PNG matching its extension.')
        name = f"{body['id']}-{index}-{hashlib.sha256(data).hexdigest()[:16]}{suffix}"
        uploads.append((name, data))
    if total > JOB_INPUT_MAX_BYTES:
        raise CommandError('Photos must be at most 1 GB per job.')
    body['inputs'] = [f"{body['tenant_id']}/uploads/{name}" for name, _ in uploads]
    return Job.model_validate(body), uploads


class Corridor:
    def __init__(self, client, job, actor):
        self.client, self.job, self.actor = client, job, actor

    async def call(self, operation, payload=None, *, binary=False):
        try:
            async with asyncio.timeout(35):
                response = await self.client.post('/v1/rig/internal/3d/workspace/' + operation,
                    json={'tenant_id': str(self.job.tenant_id), 'actor': self.actor, 'payload': payload or {}}, timeout=30)
            if response.status_code != 200:
                if response.status_code in {401, 403}:
                    raise CommandError('Room authorization or 3D entitlement is missing.')
                raise CommandError('Forge could not complete this action. Retry with the same job identifier.')
            if len(response.content) > (self.job.max_bytes if binary else 200_000):
                raise CommandError('The product response exceeds its size limit.')
            return response.content if binary else response.json()
        except (httpx.HTTPError, TimeoutError, ValueError):
            raise CommandError('The product service is not connected. Retry with the same job identifier.') from None


async def run(job, uploads, directory, review_file, corridor, storage, *, wait=asyncio.sleep, clock=time.monotonic,
              review_wait_seconds=0, notify=None):
    if not 0 <= review_wait_seconds <= 3600:
        raise CommandError('The review wait must be between 0 and 3600 seconds.')
    capabilities = await corridor.call('capabilities')
    if not capabilities.get('rig_3d'):
        raise CommandError('3D is not included for this shop.')
    if job.source not in capabilities.get('photo_sources', []):
        raise CommandError('RIG_FORGE_TRELLIS_ENABLED is required for this source.')
    if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents):
        raise CommandError('Choose an output directory without symlinks.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_file(directory, 'request.json', job.model_dump_json().encode())
    for name, data in uploads:
        async with asyncio.timeout(180):
            await storage.put(str(job.tenant_id), 'uploads', name, data)
    row = await corridor.call('submit', job.model_dump(mode='json'))
    end = clock() + job.timeout_seconds + 600  # CPU finishing budget after bounded GPU run.
    while row['status'] in {'queued', 'running'}:
        if clock() >= end:
            raise CommandError('The conversion is still running. Resume with the same command and job identifier.')
        await wait(2)
        row = await corridor.call('poll', {'id': str(job.id)})
    if row['status'] not in {'draft', 'approved'}:
        raise CommandError('The model conversion failed. No model was approved.')
    data = await corridor.call('preview', {'id': str(job.id)}, binary=True)
    digest = hashlib.sha256(data).hexdigest()
    if digest != row['report']['sha256'] or len(data) != row['report']['size_bytes']:
        raise CommandError('The product file does not match its check report.')
    write_file(directory, 'draft.glb', data)
    write_file(directory, 'report.json', json.dumps(row['report'], sort_keys=True).encode())
    if row['status'] != 'approved':
        # A reviewer checks the actual exported GLB and binds all three existing
        # review decisions to its checksum. Running this command never implies review.
        pending = {'status': 'awaiting_review', 'job_id': str(job.id), 'sha256': digest,
                   'draft': str(directory / 'draft.glb')}
        if not review_file or not review_file.exists():
            if notify: notify(pending)
            review_end = clock() + review_wait_seconds
            while review_file and not review_file.exists() and clock() < review_end:
                await wait(min(1, max(0, review_end - clock())))
            if not review_file or not review_file.exists():
                return pending
        review = json.loads(read_file(review_file, 4096))
        if set(review) != {'job_id', 'sha256', 'review'} or review['job_id'] != str(job.id) or review['sha256'] != digest:
            raise CommandError('The review must match this job and the checked GLB checksum.')
        checked = Review.model_validate(review['review'])
        await corridor.call('approve', {'id': str(job.id), 'review': checked.model_dump()})
        row = await corridor.call('poll', {'id': str(job.id)})
    if row['status'] != 'approved':
        raise CommandError('Approval was not confirmed. Resume with the same job identifier.')
    write_file(directory, 'approved.glb', data)
    receipt = {'status': 'approved', 'job_id': str(job.id), 'sha256': digest,
               'receipt_ids': row['report']['receipt_ids'], 'progress': row.get('progress', [])}
    write_file(directory, 'receipt.json', json.dumps(receipt, sort_keys=True).encode())
    return receipt


async def live(args):
    missing = [name for name in ('TANK_KEY', 'RIG_AGENT_URL') if not os.environ.get(name, '').strip()]
    if missing:
        raise CommandError('Missing settings: ' + ', '.join(missing))
    url = urlsplit(os.environ['RIG_AGENT_URL'])
    if (url.username or url.password or url.query or url.fragment or url.path not in {'', '/'}
            or not (url.scheme == 'https' or (url.scheme == 'http' and url.hostname in {'rig', 'localhost', '127.0.0.1', '::1'}))):
        raise CommandError('RIG_AGENT_URL must be the room HTTPS origin or its internal address.')
    if not args.job or not args.photos or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', args.actor):
        raise CommandError('Provide --job, --photos and the existing reviewer identity in --actor.')
    job, uploads = prepare(json.loads(read_file(args.job, 32_000)), args.photos)
    if job.source == 'ai' and os.environ.get('RIG_FORGE_TRELLIS_ENABLED', '').lower() != 'true':
        raise CommandError('Missing setting: RIG_FORGE_TRELLIS_ENABLED')
    storage = ForgeFiles('rig')
    try:
        async with httpx.AsyncClient(base_url=os.environ['RIG_AGENT_URL'], trust_env=False, follow_redirects=False,
                headers={'X-Tank-Key': os.environ['TANK_KEY']}, timeout=30) as client:
            return await run(job, uploads, args.output or Path('rig-forge-' + str(job.id)), args.review,
                             Corridor(client, job, args.actor), storage, review_wait_seconds=args.review_wait_seconds,
                             notify=lambda value: print(json.dumps(value), file=sys.stderr, flush=True))
    finally:
        await storage.close()


def main():
    parser = argparse.ArgumentParser(description='Rig photos → checked draft → checksum-bound human approval → GLB receipt.')
    parser.add_argument('--dry-run', action='store_true', help='Run the offline recorded HF response proof; no live services.')
    parser.add_argument('--job', type=Path, help='Existing Job JSON: id, tenant_id, product_id, source, dimensions_mm, anchors and cost_cap_usd.')
    parser.add_argument('--photos', type=Path, nargs='+'); parser.add_argument('--actor', default='')
    parser.add_argument('--review', type=Path, help='JSON containing job_id, sha256 and scale/appearance/attachment_points review.')
    parser.add_argument('--review-wait-seconds', type=int, default=900,
                        help='Wait for the checksum-bound human review in this command (0–3600 seconds; default 900).')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.dry_run:
            # Explicit test-only entry point; no fakes are reachable from live routes.
            import subprocess
            root = Path(__file__).resolve().parents[4]
            from rigbox.dry_run import local_database
            local_database(os.environ.get('RIG_TEST_DATABASE_URL', ''))
            env = dict(os.environ)
            env['PYTHONPATH'] = ':'.join([str(root), str(root / 'tests'), env.get('PYTHONPATH', '')])
            env['PATH'] = str(root / 'agents/rig/forge/node_modules/.bin') + ':' + env['PATH']
            return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-s',
                'tests/test_rig_r3d.py', '-k', 'r3d_recorded', '--disable-socket', '--allow-unix-socket',
                '--allow-hosts=127.0.0.1,localhost,::1', '--timeout=120'], cwd=root, env=env).returncode
        print(json.dumps(asyncio.run(live(args)), sort_keys=True))
        return 0
    except Exception as exc:
        from chassis.storage import StorageError
        message = str(exc) if isinstance(exc, (CommandError, StorageError)) else 'Check the job, photo files and review. No approval was confirmed.'
        print(json.dumps({'error': message}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
