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
