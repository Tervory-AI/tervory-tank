"""Explicit Auto selections for legacy offline provider-transport fixtures.

The Ask/Auto integration tests start with an empty settings table. These fixtures
exercise existing routing/accounting with synthetic, already-authorized calls.
"""
from pathlib import Path
from uuid import UUID

import yaml


async def auto(conn, *extra_models):
    from paid_steps import FIXED, model_step
    names = set(extra_models)
    root = Path(__file__).resolve().parents[1]
    for path in ('litellm/config.yaml','litellm/config.za.yaml'):
        names.update(row['model_name'] for row in yaml.safe_load((root/path).read_text())['model_list'])
    names.update(row['model'] for row in await conn.fetch('SELECT model FROM tank.policy'))
    steps = [*FIXED, *(model_step(model,rung) for model in names for rung in (1,2))]
    await conn.executemany('''INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by)
        VALUES($1,$2,'auto','offline-fixture') ON CONFLICT(tenant_id,step_id) DO NOTHING''',
        [(UUID('00000000-0000-0000-0000-000000000001'), step) for step in steps])
