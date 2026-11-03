import asyncio, json, sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, '/repo/tank')
import httpx
import skala
import app as room

async def no_model(**kwargs):
    raise AssertionError('no model calls')

async def main():
    pkg = skala.load_packages(Path('/repo/tank/skills'))[('scan.iac', '1.0.0')]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room.app), base_url='http://radix') as client:
        async def execute(package, payload, ctx):
            response = await client.post('/evals/run', headers={'X-Tank-Key':'placeholder-room-key'}, json={
                'skill_id': package.id, 'version': package.version, 'tenant_id':str(ctx.tenant_id), 'input':payload})
            assert response.status_code == 200, response.text
            return response.json()
        def context():
            return skala.SkillContext(tenant_id=UUID(int=1),skill_ref=pkg.ref,agent='radix',task_id=None,_model=no_model,http=client)
        result = await skala.run_evals(pkg, context, execute=execute)
        print(json.dumps(result), flush=True)
        assert result['score'] == 1.0 and result['eligible'] is True
        assert result['cost_usd'] == 0 and not any(c['used_model'] for c in result['details'])
asyncio.run(main())
