from datetime import UTC, datetime, timedelta

import pytest
import skala_probation
from gold import PLATFORM_TENANT
from test_tank_tenant_boundaries import boundary  # noqa: F401


@pytest.mark.asyncio
async def test_requires_real_thirty_day_run_and_retains_rollback(boundary):  # noqa: F811
    b = boundary
    start = datetime(2026, 1, 1, tzinfo=UTC)
    async with b.pool.acquire() as conn:
        for version, state in [('1.0.0', 'staging'), ('2.0.0', 'approved')]:
            await conn.execute("""INSERT INTO tank.skills(id,version,agent,state,present,approved_at)
                VALUES('base.probation',$1,'base',$2,true,$3)""", version, state, start)
        assert not (await skala_probation.evidence(conn, 'base.probation', '1.0.0', now=start+timedelta(days=90)))['allowed']
        for stamp in (start+timedelta(days=5), start+timedelta(days=35)):
            await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,skill,task_type,rung,model,outcome,ts)
                VALUES($1,'base','base.probation@2.0.0','fixture',3,'skill:base.probation@2.0.0','delivered',$2)""", PLATFORM_TENANT, stamp)
        assert not (await skala_probation.evidence(conn, 'base.probation', '1.0.0', now=start+timedelta(days=34)))['allowed']
        assert (await skala_probation.evidence(conn, 'base.probation', '1.0.0', now=start+timedelta(days=35)))['allowed']
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,skill,task_type,rung,model,outcome,ts)
            VALUES($1,'base','base.probation@2.0.0','fixture',3,'skill:base.probation@2.0.0','failed',$2)""", PLATFORM_TENANT, start+timedelta(days=34))
        assert not (await skala_probation.evidence(conn, 'base.probation', '1.0.0', now=start+timedelta(days=35)))['allowed']
        assert await conn.fetchval("SELECT state FROM tank.skills WHERE id='base.probation' AND version='1.0.0'") == 'staging'
