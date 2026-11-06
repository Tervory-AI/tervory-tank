import ast
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID
import sys

import pytest
import trigger_bot_api
import trigger_learning
import trigger_whatsapp
import trigger_google
import trigger_meta
import trigger_crm
import vault
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'trigger_finish'))
from patch_runtime import proposed_text


def function(module, name):
    relative = 'tank/' + module.__name__ + '.py'
    tree = ast.parse(proposed_text(relative, Path(module.__file__).read_text(), 'gate4'))
    namespace = dict(vars(module))
    exec(compile(ast.Module(body=[n for n in tree.body if getattr(n, 'name', '') == name], type_ignores=[]), relative, 'exec'), namespace)
    return namespace


@pytest.mark.asyncio
@pytest.mark.parametrize('populated', [False, True])
async def test_weekly_chart_has_real_zero_shape_and_preserves_counts(monkeypatch, populated):
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    monday = now - timedelta(days=now.weekday())
    stored = [{'week': monday, 'answered_from_sources': 0, 'faq_answers': 3, 'handovers': 0, 'bad_answers': 0}] if populated else []
    pool = SimpleNamespace(fetch=AsyncMock(return_value=stored))
    namespace = function(trigger_bot_api, 'execute')
    namespace['make_bot'] = lambda: SimpleNamespace(pool=pool)
    monkeypatch.setattr(trigger_whatsapp, 'reply_count', AsyncMock(return_value=0))
    result = await namespace['execute']('stats', None, SimpleNamespace(tenant_id=UUID(int=11)), None)
    assert len(result['weeks']) == 52
    assert result['count'] == 0
    assert result['weeks'][0]['faq_answers'] == (3 if populated else 0)
    assert result['first_action'] is None if populated else bool(result['first_action'])
    assert all(row['week'].weekday() == 0 for row in result['weeks'])
    assert all(row['handovers'] == 0 for row in result['weeks'])
    assert pool.fetch.await_args.args[1] == UUID(int=11)


@pytest.mark.asyncio
async def test_empty_scorecard_names_first_action_without_inventing_work(monkeypatch):
    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(fetch=AsyncMock(return_value=[]))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: SimpleNamespace(acquire=acquire)))
    namespace = function(trigger_learning, 'scorecard')
    data = await namespace['scorecard'](SimpleNamespace(tenant_id=UUID(int=11)))
    assert data['first_action']
    for period in ('last_30_days', 'prior_30_days'):
        assert len(data[period]) == 10
        assert all(item['drafts'] == 0 and item['drafts_using_accepted_examples'] == 0 for item in data[period].values())


@pytest.mark.asyncio
async def test_failed_read_does_not_turn_into_fabricated_zero(monkeypatch):
    namespace = function(trigger_bot_api, 'execute')
    namespace['make_bot'] = lambda: SimpleNamespace(pool=SimpleNamespace(fetch=AsyncMock(side_effect=RuntimeError('placeholder unavailable'))))
    with pytest.raises(RuntimeError):
        await namespace['execute']('stats', None, SimpleNamespace(tenant_id=UUID(int=11)), None)


@pytest.mark.parametrize('module,name,keys', [
    (trigger_google, 'settings', ['TRIGGER_GOOGLE_OAUTH_CLIENT_ID', 'TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET']),
    (trigger_meta, 'settings', ['TRIGGER_META_APP_ID', 'TRIGGER_META_APP_SECRET']),
    (trigger_crm, 'binding', ['TRIGGER_CRM_URL', 'TRIGGER_CRM_TENANT_BINDINGS']),
    (vault, 'key', ['TANK_VAULT_KEY']),
])
def test_each_missing_connector_setting_is_named_and_fails_closed(monkeypatch, module, name, keys):
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    namespace = function(module, name)
    with pytest.raises(HTTPException) as failure:
        namespace[name](SimpleNamespace(tenant_id=UUID(int=11))) if name == 'binding' else namespace[name]()
    assert failure.value.status_code == 503
    assert set(failure.value.detail['missing_settings']) == set(keys)
