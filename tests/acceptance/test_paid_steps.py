"""One actual HTTP router fixture path for each product's paid-step sheet row."""
from pathlib import Path
import re

import pytest

from test_paid_steps import exercise_model_router
from test_paid_steps import router_database as router_database
from test_paid_steps import routing_pool as routing_pool

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = ('base','tiger','market_lab','rig','tisan','radix','zenas','trigger','autumbra','model')


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.parametrize('owner',PRODUCTS)
async def test_paid_step_sheet_row(router_database,monkeypatch,owner):
    await exercise_model_router(router_database,monkeypatch,owner,via_http=True)


def test_every_paid_sheet_row_has_one_offline_case():
    rows = []
    for owner in PRODUCTS:
        sheet_owner = 'tank' if owner == 'model' else owner
        text = (ROOT/f'docs/acceptance/{sheet_owner}.md').read_text()
        found = re.findall(r'^\| (PAID-[A-Z_]+) \|',text,flags=re.M)
        assert found == ['PAID-'+sheet_owner.upper()]
        rows.extend(found)
    assert len(rows) == len(set(rows)) == len(PRODUCTS)
