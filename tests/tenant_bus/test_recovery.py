"""Recovery must examine pending work beyond Redis's first scan page."""
from uuid import uuid4

import pytest

from test_bus import EVENT, facts, scope


@pytest.mark.asyncio
async def test_reclaims_stale_work_after_a_full_page_of_busy_pending_deliveries(bus):
    bus.maxlen, bus.retry_ms = 250, 60000
    key = scope().stream(EVENT)
    payload = facts()
    for _ in range(201):
        await bus.publish(scope(agent='tiger'), EVENT, uuid4(), payload)
    await bus.redis.xgroup_create(key, 'rig', id='0-0')
    batch = await bus.redis.xreadgroup('rig', 'old-worker', {key: '>'}, count=201)
    ids = [item[0] for item in batch[0][1]]
    # The first 200 deliveries are still busy; the last worker has died.
    # XAUTOCLAIM COUNT 20 scans only 200 pending entries at a time.
    await bus.redis.xclaim(key, 'rig', 'old-worker', 0, [ids[-1]], idle=120000, justid=True)
    await bus.redis.xclaim(key, 'rig', 'busy-worker', 0, ids[:-1], idle=0, justid=True)
    recovered = await bus.receive(scope(), EVENT, str(uuid4()))
    assert [message['id'] for message in recovered] == [ids[-1]]
    assert recovered[0]['attempt'] == 2
