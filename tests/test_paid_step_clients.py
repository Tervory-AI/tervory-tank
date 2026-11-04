import json
import uuid

import pytest

def test_payment_setting_arguments_cannot_supply_identity_or_dispatch():
    from pydantic import ValidationError
    from paid_steps import Setting
    for extra in ({'tenant_id':str(uuid.uuid4())},{'by':'founder'},{'url':'https://provider.invalid'}):
        with pytest.raises(ValidationError):
            Setting.model_validate({'step_id':'vendor.brave','mode':'auto',**extra})
    assert json.loads(Setting(step_id='vendor.brave',mode='ask').model_dump_json()) == {'step_id':'vendor.brave','mode':'ask'}


def test_finished_implicit_run_is_removed_before_its_loop_can_close():
    import asyncio
    import paid_steps
    loop = asyncio.new_event_loop()
    async def free_operation():
        run = paid_steps.current()
        assert run.task is asyncio.current_task()
    work = loop.create_task(free_operation())
    try:
        loop.run_until_complete(work)
        assert work not in paid_steps.RUNS
        assert not asyncio.all_tasks(loop)
    finally:
        paid_steps.RUNS.pop(work, None)
        loop.close()
