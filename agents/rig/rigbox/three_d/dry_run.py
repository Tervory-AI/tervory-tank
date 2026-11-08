"""Explicit operator-only replay; never mounted on a live product route."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile

import httpx

from .command import CommandError, Corridor, prepare, run
from .contracts import Report, Review
from .engine import check_artifact

FIXTURES = Path(__file__).with_name('offline')


async def replay():
    """Exercise the real CLI workflow against recorded replies, entirely in process.

    The full database/CPU/provider-contract integration proofs remain in the
    check suite. This deployment smoke check needs only the room's runtime.
    """
    recording = json.loads((FIXTURES / 'response.json').read_text())
    artifact = (FIXTURES / 'approved.glb').read_bytes()
    report = Report.model_validate(recording['report'])
    if check_artifact(artifact, report):
        raise CommandError('The packaged Forge replay failed its integrity check.')

    results = []
    for photo_count in (1, 3):
        with tempfile.TemporaryDirectory(prefix='rig-forge-dry-') as folder:
            root = Path(folder)
            photos = []
            for index in range(photo_count):
                path = root / f'{index}.jpg'
                path.write_bytes(b'\xff\xd8\xffoffline-command-proof')
                photos.append(path)
            job, uploads = prepare(recording['job'], photos)
            if report.rejection(job):
                raise CommandError('The packaged Forge replay does not match its job.')
            objects, state = {}, {'status': 'queued', 'submissions': 0, 'polls': 0}

            class Files:
                async def put(self, tenant, area, name, data):
                    assert tenant == str(job.tenant_id) and area == 'uploads'
                    previous = objects.setdefault(name, data)
                    assert previous == data

            async def respond(request):
                body = json.loads(request.content)
                assert body['tenant_id'] == str(job.tenant_id) and body['actor'] == 'offline-reviewer'
                operation = request.url.path.rsplit('/', 1)[-1]
                payload = body['payload']
                if operation == 'capabilities':
                    return httpx.Response(200, json={'rig_3d': True, 'photo_sources': ['ai']})
                if operation == 'submit':
                    assert payload == job.model_dump(mode='json') and len(objects) == photo_count
                    if not state['submissions']:
                        state['submissions'] = 1
                elif operation == 'poll':
                    assert payload == {'id': str(job.id)}
                    state['polls'] += 1
                    if state['status'] in {'queued', 'running'}:
                        state['status'] = 'running' if state['polls'] == 1 else 'draft'
                elif operation == 'preview':
                    assert payload == {'id': str(job.id)} and state['status'] in {'draft', 'approved'}
                    return httpx.Response(200, content=artifact)
                elif operation == 'approve':
                    assert payload['id'] == str(job.id) and state['status'] == 'draft'
                    Review.model_validate(payload['review'])
                    state['status'] = 'approved'
                else:
                    raise AssertionError('Unexpected dry-run operation')
                return httpx.Response(200, json={'id': str(job.id), 'status': state['status'],
                    'report': report.model_dump(mode='json'), 'progress': []})

            async def wait(_):
                await asyncio.sleep(0)

            async with httpx.AsyncClient(base_url='https://offline.invalid', trust_env=False,
                    transport=httpx.MockTransport(respond)) as client:
                corridor = Corridor(client, job, 'offline-reviewer')
                output, review = root / 'output', root / 'review.json'
                args = (job, uploads, output, review, corridor, Files())
                pending = await run(*args, wait=wait)
                assert pending['status'] == 'awaiting_review' and not (output / 'approved.glb').exists()
                # This review is only for the packaged recording; never for a
                # client's uploads and never sent outside the mock transport.
                review.write_text(json.dumps({'job_id': str(job.id), 'sha256': report.sha256,
                    'review': {'scale': True, 'appearance': True, 'attachment_points': True}}))
                result = await run(*args, wait=wait)
                assert result['status'] == 'approved' and result['receipt_ids']
                assert hashlib.sha256((output / 'approved.glb').read_bytes()).hexdigest() == report.sha256
                assert await run(*args, wait=wait) == result and state['submissions'] == 1
                assert json.loads((output / 'receipt.json').read_text()) == result
                results.append({'photos': photo_count, 'status': result['status'],
                                'sha256': result['sha256'], 'receipts': len(result['receipt_ids'])})
    return {'dry_run': True, 'source': 'packaged Forge recording; no database or live services',
            'runs': results}
