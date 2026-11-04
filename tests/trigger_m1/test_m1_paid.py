"""Model-capable marketing routes use the existing confirm-time paid guard."""
from unittest.mock import AsyncMock

import command
import pytest
from fastapi import HTTPException
from test_marketing import card_for
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_second import confirm
from trigger_marketing_contract import TOOLS


def test_only_model_capable_marketing_tools_are_paid_runs():
    for name in TOOLS:
        adapter = command.ADAPTERS['trigger.'+name]
        paid = name in {'post.create', 'gbp.reply.draft'}
        assert adapter.paid is paid
        assert adapter.kind == ('paid_run' if paid else 'other')


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,args', [
    ('trigger.post.create', {'channel': 'gbp', 'text': 'placeholder brief'}),
    ('trigger.gbp.reply.draft', {'review_id': 'placeholder-review'}),
])
async def test_confirm_checks_paid_guard_before_any_marketing_draft(m1, monkeypatch, tool, args):
    refuse = AsyncMock(side_effect=HTTPException(503))
    monkeypatch.setattr('controls.refuse_paid', refuse)
    _, card = await card_for(m1.env, tool, args, user='founder')
    result = await confirm(m1.env, card, user='founder')
    assert result['status'] == 'failed' and result['retry_safe']
    refuse.assert_awaited_once_with(task=tool, path='command.confirm')
    m1.env.model.assert_not_awaited()
    m1.google.request.assert_not_awaited()
