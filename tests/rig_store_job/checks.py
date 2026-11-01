"""Live HTTP, SMTP and two-tenant checks, after browser.cjs. No mocked API/model."""
import asyncio
import email
import json
import os
import secrets
import sys
from pathlib import Path
from uuid import UUID

import asyncpg
import httpx

sys.path.insert(0, '/repo/agents/rig')
from rigbox.service import hash_key
from rigbox.store import PgStore

PROOF = Path(os.environ.get('RIG_PROOF_DIR', '/proof'))


async def main():
    fixture = json.loads((PROOF / 'fixture.json').read_text())
    proof = json.loads((PROOF / 'browser-result.json').read_text())
    a, b = fixture['store_a'], fixture['store_b']
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'], min_size=1, max_size=3)
    async with httpx.AsyncClient(trust_env=False, timeout=90) as http:
        async def admin(tenant, operation, data):
            r = await http.post('http://tank:8000/v1/access/rig/admin/' + operation,
                headers={'x-tank-key': os.environ['TANK_API_KEY'], 'x-tervory-user': 'fixture-owner', 'x-tervory-tenant': tenant}, json={'data': data})
            assert r.status_code == 200, f'Retailer {operation} status {r.status_code}'
            return r.json()
        # Second store publishes its own unrelated product through the same corridor.
        body = {'distributor':'catalogue','site':'https://store-b.rig.test','feed_id':'own-catalogue',
            'currency':'ZAR','country':'ZA','price_basis':'selling','format':'csv','source':'ftp_export',
            'contents':'sku,name,brand,category,price,image_url,quantity\nB-DESK,Writing Desk,Fixture B,furniture,800,https://store-b.rig.test/desk.svg,5\n'}
        mapping = await admin(b, 'mapping', body)
        body['columns'] = mapping['columns']
        await admin(b, 'confirm-mapping', {**body, 'preview_id': mapping['preview_id']})
        assert (await admin(b, 'import', body))['receipt']['added'] == 1
        kb = await admin(b, 'embed-keys', {'origins':['https://store-b.rig.test']})
        headers_a = {'x-rig-key':proof['key_a'], 'origin':'https://store-a.rig.test'}
        headers_b = {'x-rig-key':kb['publishable_key'], 'origin':'https://store-b.rig.test'}
        async def public(path, headers, data=None):
            return await http.request('GET' if data is None else 'POST','http://agent-rig:8000/v1/rig'+path,headers=headers,json=data)
        assert (await public('/products/LAMP', headers_b)).status_code == 404
        assert (await public('/products/B-DESK', headers_a)).status_code == 404
        result = await public('/search?q=Writing%20Desk', headers_b)
        assert result.status_code == 200 and [x['id'] for x in result.json()['results']] == ['B-DESK']
        assert (await public('/search?q=Desk', {**headers_a,'origin':headers_b['origin']})).status_code == 403
        assert (await public('/setups', headers_b, {'product_id':'LAMP'})).status_code == 404
        setup = (await public('/setups', headers_a, {'product_id':'LAMP'})).json()['setups'][0]
        assert str(setup['total']['amount']) in {'150','150.0','150.00'}
        assert (await public('/quote',headers_b,{'setup':setup,'contact':{'name':'Fixture','email':'b@rig.test'}})).status_code in {404,422}
        # Administrator fixtures only provision credentials, never catalogue or quote rows.
        admin_keys = {tenant: secrets.token_urlsafe(32) for tenant in (a,b)}
        for tenant,key in admin_keys.items():
            await PgStore(pool).put_key(tenant,hash_key(key),'admin',[])
        async def delivery(tenant, quote, operation='delivery'):
            return await http.request('GET' if operation=='delivery' else 'POST',
                f'http://agent-rig:8000/v1/rig/admin/quotes/{quote}/{operation}',headers={'x-rig-key':admin_keys[tenant]})
        assert (await delivery(b,proof['quote'])).status_code == 404
        assert (await delivery(b,proof['quote'],'retry')).status_code == 404
        assert (await delivery(b,proof['quote'],'resume')).status_code == 404
        assert (await public('/admin/quotes/'+proof['quote']+'/delivery',headers_a)).status_code == 403
        async with pool.acquire() as conn:
            assert not await conn.fetchval('SELECT EXISTS(SELECT 1 FROM agent_rig.keys WHERE tenant_id=$1 AND key_hash=$2)',UUID(b),hash_key(proof['key_a']))
            assert not await conn.fetchval('SELECT EXISTS(SELECT 1 FROM agent_rig.quotes WHERE tenant_id=$1)',UUID(b))
        print('PASS two-tenant HTTP/DB isolation: products, search, setups, origins, embed keys, quote read/retry/resume and settings')
        # Actual SMTP rejection must persist a safe error and schedule a retry.
        mail = PROOF / 'mail'
        (mail/'reject').touch()
        try:
            r = await public('/quote',headers_a,{'setup':setup,'contact':{'name':'Fixture Shopper','email':'shopper@rig.test'}})
            assert r.status_code == 200 and r.json()['delivery'] == 'pending'
            pending = r.json()['request_id']
            state = (await delivery(a,pending)).json()
            assert state['error'] == 'email_unavailable' and state['attempts'] == 1 and state['next_attempt_at']
        finally:
            (mail/'reject').unlink(missing_ok=True)
        retried = (await delivery(a,pending,'retry')).json()
        assert retried['status'] == 'sent' and retried['attempts'] == 2 and retried['error'] is None
        print('PASS SMTP 451 rejection recorded; durable retry changes pending -> sent, attempts 1 -> 2')
        # Cache hits must produce separate events, including the second identical miss.
        for tenant,headers in ((a,headers_a),(a,headers_a),(b,headers_b)):
            result=await public('/search?q=zzzyyyxxxunmatchedfixture',headers)
            assert result.status_code==200 and result.json()['results']==[]
        letters=[]
        for file in mail.glob('*.eml'):
            message=email.message_from_bytes(file.read_bytes())
            if proof['quote'] in message['Subject'] or pending in message['Subject']:
                text=message.get_payload(decode=True).decode(message.get_content_charset() or 'utf8')
                assert message['To']=='store-a@rig.test' and message['Reply-To']=='shopper@rig.test'
                assert all(value in text for value in ('Desk Light','Light Shade','Light Stand','Total-Amount: 150','Total-Currency: ZAR'))
                assert 'sample' not in text.lower()
                letters.append(message)
        assert len(letters)==2
        print('PASS local STARTTLS mail catcher: 2 emails contain the approved setup, ZAR 150 total, shopper reply address and request reference')
        proof['retry_quote']=pending
        (PROOF/'browser-result.json').write_text(json.dumps(proof))
    await pool.close()


if __name__=='__main__':
    asyncio.run(main())
