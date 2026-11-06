import json
from pathlib import Path
import subprocess

import pytest
import gold
import skala
from test_skala_approval_safety import database as _database
from test_skala_finish_jobs import room_runtime

database = _database


def test_rendered_day_zero_and_unconfigured_pages():
    from skala_integrated_sources import SOURCES
    sources = {name: text for name, text in SOURCES.items() if '/workspace/app/skala/' in name}
    result = subprocess.run(['node', 'tests/skala_gate4_render.cjs'], input=json.dumps(sources),
        text=True, capture_output=True, cwd=Path.cwd(), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '# pass 8' in result.stdout


@pytest.mark.asyncio
async def test_new_workspace_has_no_counts_examples_approvals_or_receipts(database, monkeypatch):
    from uuid import uuid4
    import httpx
    room_runtime(database, monkeypatch, lambda request: httpx.Response(500))
    actor = gold.Reviewer('founder', uuid4(), True)
    assert await gold.summary(actor) == {'skills': [], 'pairs': {}, 'region': 'us-east'}
    assert await gold.next_example('base', 'base.offline', actor=actor) is None
    preview = await skala.bulk_preview(database, {}, 'founder', region='us-east')
    assert preview['items'] == []
    assert await database.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', actor.tenant) == 0
    assert await database.fetchval('SELECT count(*) FROM tank.skill_approvals') == 0


@pytest.mark.asyncio
async def test_other_workspace_examples_do_not_populate_day_zero(database, monkeypatch):
    from uuid import uuid4
    import httpx
    room_runtime(database, monkeypatch, lambda request: httpx.Response(500))
    actor = gold.Reviewer('founder', uuid4(), True)
    await gold.add_candidate(database, tenant=uuid4(), skill='base.offline', agent='base',
        value={'id': 'offline'}, expected={'ok': True}, source='offline', ref='one')
    assert await gold.summary(actor) == {'skills': [], 'pairs': {}, 'region': 'us-east'}
    assert await gold.next_example('base', 'base.offline', actor=actor) is None
