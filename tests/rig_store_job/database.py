"""Fixture-only database setup/assertions for the real Tank job. Run in its container."""
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

import asyncpg

PROOF = Path(os.environ.get('RIG_PROOF_DIR', '/proof'))


async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    try:
        fixtures = json.loads((PROOF / 'fixture.json').read_text())
        for tenant in fixtures.values():
            await conn.execute("INSERT INTO tank.tenant_squad (tenant_id,agent,enabled_by) VALUES ($1,'rig','fixture-owner') ON CONFLICT DO NOTHING", UUID(tenant))
        print('Two fixture stores enabled in real Tank; no catalogue, key, quote or settings seeded.')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
