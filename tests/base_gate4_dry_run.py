"""Explicit offline rehearsal; every external boundary is a recorded response."""
import gzip
import importlib.util
import json
import tempfile
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import httpx
import pytest
from pgserver import get_server


async def run(directory):
    from configuration import missing_settings
    missing = missing_settings(('DATABASE_URL', 'TANK_KEY'))
    from test_base_finish_training import RecordedSkills, TODAY, ROOT
    from test_base_finish_training import test_real_small_state_runs_through_worker_and_resume_never_replays_completed_records
    from engines.ffl.reference import parse_file
    from base_gold import build, observations
    import hashlib
    content = gzip.open(ROOT / 'tests/fixtures/base-atf/0925-ffl-list-complete.txt.gz', 'rb').read()
    source = {'rows': parse_file(content), 'sha256': hashlib.sha256(content).hexdigest(),
              'source_url': 'https://www.atf.gov/resource-center/docs/0925-ffl-list-complete.txt',
              'published_on': '2025-09-01'}

    class RecordedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    class RecordedTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2025, 9, 20, 12, tzinfo=timezone.utc)

    requests = []

    def respond(request):
        assert request.url.host == 'www.atf.gov', 'No non-recorded external destination is permitted'
        requests.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        if str(request.url) == source['source_url']:
            return httpx.Response(200, content=content)
        if request.url.path.endswith('/complete'):
            return httpx.Response(200, text=f'<a href="{source["source_url"]}">September 2025 complete list</a>')
        raise AssertionError('Unrecorded request')

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='base-gate4-') as scratch, pytest.MonkeyPatch.context() as patch:
        patch.setenv('DATA_DIR', str(directory / 'scheduled-data'))
        patch.setenv('TANK_REGION', 'us-east')
        patch.setattr(build, 'date', RecordedDate)
        patch.setattr(observations, 'datetime', RecordedTime)
        server = get_server(Path(scratch) / 'pg', cleanup_mode='delete')
        pool = await asyncpg.create_pool(server.get_uri(), min_size=1, max_size=4)
        try:
            await test_real_small_state_runs_through_worker_and_resume_never_replays_completed_records(
                pool, source, directory, patch)
            spec = importlib.util.spec_from_file_location('base_gate4_scheduled_app', ROOT / 'agents/base/app.py')
            app = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = app
            spec.loader.exec_module(app)
            skills = RecordedSkills()
            skills.approved = AsyncMock(return_value='1.0.1')
            patch.setattr(app, '_skills', lambda: skills)
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
                app.app.state.pool = pool
                app.app.state.http = http
                context = SimpleNamespace(tenant_id=app.HEARTBEAT_TENANT, agent='base', input={'heartbeat': True},
                                          memory=SimpleNamespace(remember=AsyncMock(return_value={'seen': 1})))
                jobs = {}
                for schedule in app.app.state.schedules:
                    jobs[schedule['kind']] = await app.app.state.handlers[schedule['kind']](context)
            assert set(jobs) == {'ping', 'gold.nightly'}
            assert jobs['ping']['pong'] is True and jobs['gold.nightly']['status'] == 'done'
            from training_day import plan
            identity = plan(source, today=TODAY)['id']
            result = json.loads((directory / identity / 'result.json').read_text())
            summary = {'mode': 'dry_run', 'source': 'recorded ATF September 2025', 'source_records': 77611,
                       'smallest_state': 'DC', 'records': result['records'], 'resumed': True,
                       'model_spend': result['model_spend'], 'scheduled_jobs': jobs,
                       'external_requests': 0, 'recorded_requests': len(requests), 'missing_settings': missing}
            from training_day import write_receipt
            write_receipt(directory / 'dry-run.json', summary)
            return summary
        finally:
            await pool.close()
            server.cleanup()
