"""DC campaign -> recorded worker evidence -> human audit -> report, offline only."""
from trigger_signin_fakes import set_founders
import csv
from datetime import datetime
import io
import json
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import command
import httpx
import pytest
from fastapi import FastAPI
import base_campaign_commands as campaigns
import base_audit_commands as audits
from base_evidence import observe, observations, row_fields
from base_metrics import export_records, verified_contacts
from base_repository import BaseStore, encoded
from base_product_fixtures import AT, TENANT, OTHER, raw, finished
from agents.base.engines.ffl.reference import project
from test_base_audit import audit_db, checked  # noqa: F401
from trigger_commands import CONFIRMED


def social_proof(site):
    pages = [(site + 'contact', '2026-10-25T09:00:00+00:00', [
        'https://facebook.com/placeholder', 'https://pinterest.com/placeholder']),
        (site + 'about', AT, ['https://facebook.com/placeholder-two', 'https://yelp.com/biz/placeholder'])]
    proof = []
    for source, at, links in pages:
        token = observations.set(proof)
        try:
            observe(source, ''.join(f'<a href="{link}">Profile</a>' for link in links))
        finally:
            observations.reset(token)
        proof[-1]['checked_at'] = at
    return proof


def test_social_links_from_html_keep_each_page_and_date_in_records_and_csv():
    proof = social_proof('https://placeholder.example/')
    fields = row_fields({'status': 'done', 'profile': {'website': {'value': 'https://placeholder.example/'}},
                         'passes': {'2b': {'field_observations': proof}}})
    links = verified_contacts(fields['socials'])
    expected = [(link, page['source_url'], page['checked_at']) for page in proof for link in page['socials']]
    assert [(item['value'], item['source_url'], item['checked_at']) for item in links] == expected
    row = {'record_id': str(uuid4()), 'fields': fields}
    text = export_records([row])
    cells = next(csv.DictReader(io.StringIO(text.lstrip('\ufeff'))))
    for column, item in zip(['facebook', 'other_socials', 'other_facebook'], links[:3]):
        if column == 'other_socials':
            continue
        assert (cells[column], cells[column+'_source_url'], cells[column+'_checked_at']) == (item['value'], item['source_url'], item['checked_at'])
    for item in (links[1], links[3]):
        assert item['value'] in cells['other_socials']
        assert item['source_url'] in cells['other_socials_source_url']
        assert item['checked_at'] in cells['other_socials_checked_at']


@pytest.mark.asyncio
@pytest.mark.parametrize('population', [3, 200])
async def test_dc_campaign_through_confirmed_cards_collection_audit_and_download(audit_db, monkeypatch, population):  # noqa: F811 -- shared pytest fixture
    pool, rt, product_client = audit_db
    rt.BASE_AGENT_URL = 'http://fixture-room'
    store = BaseStore(rt)
    # DC is deliberately the smallest fixture group; no live population count is claimed.
    entries = [project(raw(i+1, 'DC')) for i in range(population)] + [project(raw(population+i+1, 'CA')) for i in range(population+1)]
    await store.install({'published_on': '2026-09-01', 'source_url': 'https://www.atf.gov/placeholder-reference',
        'checked_at': AT, 'sha256': 'placeholder-dc-reference', 'rows': entries})
    tasks = []
    async def room(request):
        assert request.url.path == '/v1/base/run'
        body = json.loads(request.content)
        assert {row['_base_reference']['state'] for row in body['records']} == {'DC'}
        task = uuid4()
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO agent_base.tasks(id,tenant_id,title,input,status) VALUES($1,$2,'Placeholder DC',$3::jsonb,'queued')", task, TENANT, encoded(body))
        tasks.append((task, body))
        return httpx.Response(202, json={'task': {'id': str(task)}})
    actor = command.Actor(TENANT, 'fixture-founder', True, frozenset({'base'}))
    monkeypatch.setattr(command, 'db', lambda: pool)
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    app = FastAPI()
    app.include_router(campaigns.build_router(rt))
    app.include_router(audits.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async def post(client, tool, path, args):
        binding = CONFIRMED.set((TENANT, actor.user_id, uuid4(), tool, args))
        try:
            return await client.post(path, json=args)
        finally:
            CONFIRMED.reset(binding)
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as transport:
        rt._http = transport
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture',
                headers={'x-tank-key': 'local-fixture', 'x-tervory-admin': actor.user_id}) as client:
            start = {'name': 'Placeholder DC', 'states': ['DC'], 'types': [], 'include_collectors': False}
            assert (await client.post('/v1/command/base/campaigns/start', json=start)).status_code == 409
            response = await post(client, 'base.campaign.start', '/v1/command/base/campaigns/start', start)
            assert response.status_code == 200, response.text
            campaign = UUID(response.json()['campaign_id'])
            task, body = tasks[0]
            async with pool.acquire() as conn:
                for entry in body['records']:
                    row = finished({**entry['_base_reference'], 'raw': {key: value for key, value in entry.items() if not key.startswith('_base_')}})
                    site = row['profile']['website']['value']
                    row['passes']['2b']['field_observations'] += social_proof(site)
                    await conn.execute("""INSERT INTO agent_base.records(id,tenant_id,task_id,batch,raw,profile,passes,confidence,status,created_at,updated_at)
                        VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,80,'done',$8,$8)""", row['id'], TENANT, task, body['batch'], encoded(entry), encoded(row['profile']), encoded(row['passes']), datetime.fromisoformat(AT))
                await conn.execute("UPDATE agent_base.tasks SET status='done' WHERE tenant_id=$1 AND id=$2", TENANT, task)
            assert await store.collect(TENANT) == population
            await store.dispatch(TENANT)
            records_json = await product_client.get('/v1/base-product/records', params={'tenant_id': str(TENANT), 'states': 'DC'})
            assert records_json.status_code == 200, records_json.text
            assert records_json.json()['total'] == population
            for record in records_json.json()['rows']:
                found = verified_contacts(record['fields']['socials'])
                from urllib.parse import urlparse
                assert any((urlparse(item['value']).hostname or '').removeprefix('www.') == 'pinterest.com' for item in found)
                assert all(item['source_url'] and item['checked_at'] for item in found)
            args = {'campaign_id': str(campaign)}
            show = await client.get('/v1/command/base/campaigns/show', params=args)
            assert show.json()['total'] == population
            assert json.loads(show.json()['summary'])['states'][0]['status'] == 'done'
            drawn = await post(client, 'base.audit.start', '/v1/command/base/audits/start', {**args, 'seed': 42})
            if population < 200:
                assert drawn.status_code == 409 and '200 verified' in drawn.text
            else:
                assert drawn.status_code == 200, drawn.text
                audit_id = drawn.json()['audit_id']
                query = {**args, 'audit_id': audit_id}
                csv_response = await client.get('/v1/command/base/audits/csv', params=query)
                upload = uuid4()
                reviewed = checked(csv_response.text, ['correct']*180 + ['wrong']*20)
                reader = csv.DictReader(io.StringIO(reviewed))
                cells = list(reader)
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=[*reader.fieldnames, 'website_verdict', 'phone_verdict', 'email_verdict', 'socials_verdict'])
                writer.writeheader()
                for i, cell in enumerate(cells):
                    writer.writerow({**cell, 'website_verdict': 'correct', 'phone_verdict': 'correct' if i < 180 else 'wrong', 'email_verdict': 'correct', 'socials_verdict': 'correct'})
                reviewed = output.getvalue()
                async with pool.acquire() as conn:
                    thread = uuid4()
                    await conn.execute("INSERT INTO tank.command_threads(thread_id,tenant_id,user_id,title,state) VALUES($1,$2,$3,'Placeholder','{}'::jsonb)", thread, TENANT, actor.user_id)
                    await conn.execute("INSERT INTO tank.command_attachments(attachment_id,thread_id,tenant_id,user_id,name,sha256,content) VALUES($1,$2,$3,$4,'placeholder.csv','placeholder',$5)", upload, thread, TENANT, actor.user_id, reviewed.encode())
                response = await post(client, 'base.audit.review', '/v1/command/base/audits/review', {**query, 'attachment_id': str(upload)})
                assert response.status_code == 200, response.text
                assert response.json()['measurement']['accuracy'] == .9
            download = await client.get('/v1/command/base/campaigns/csv', params=args)
            assert download.status_code == 200
            rows = list(csv.DictReader(io.StringIO(download.text.lstrip('\ufeff'))))
            assert len(rows) == population
            for row in rows:
                assert row['state'] == 'DC'
                for field in ('website', 'phone', 'email', 'facebook', 'other_socials', 'name', 'licence_key', 'state', 'licence_type'):
                    assert row[field] and row[field+'_source_url'] and row[field+'_checked_at']
                assert bool(row['audit_accuracy']) is (population >= 200)
                if population >= 200:
                    assert float(row['audit_accuracy']) == .9
                    assert .85 < float(row['audit_interval_lower']) < .86
                    assert .93 < float(row['audit_interval_upper']) < .94
                    assert any(score['source'] == 'own_site' and score['field'] == 'phone' and score['checked'] == 200 and float(score['accuracy']) == .9 for score in json.loads(row['source_scores']))
                else:
                    assert row['source_scores'] == '[]' and row['audit_interval_lower'] == ''
            export = await client.get('/v1/command/base/campaigns/export', params=args)
            assert export.json()['url'].endswith('campaign_id='+str(campaign))
            actor = command.Actor(OTHER, 'fixture-founder', True, frozenset({'base'}))
            for path in ('show', 'export', 'csv'):
                assert (await client.get('/v1/command/base/campaigns/'+path, params=args)).status_code == 404
    assert len(tasks) == 1


def test_campaign_download_and_confirmed_start_adapter(monkeypatch):
    import subprocess
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'us-east'))
    set_founders(monkeypatch, 'fixture-founder')
    actor = command.Actor(TENANT, 'fixture-founder', True, frozenset({'base'}))
    action = command.validate_action(command.PlannedAction(tool='base.campaign.start', arguments={'name': 'Placeholder DC', 'states': ['DC']}), actor)
    method, path, params, body = command.adapter_request(action, actor)
    assert method == 'POST' and path == '/v1/command/base/campaigns/start' and params == {}
    assert 'tenant_id' not in body and 'created_by' not in body
    assert command.ADAPTERS[action.tool].paid
    for tool in ('base.campaign.show', 'base.campaign.csv'):
        assert command.ADAPTERS[tool].method == 'GET' and not command.ADAPTERS[tool].paid
    result = subprocess.run(['node', 'tests/base_campaign_download.cjs'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('text', ['record_id,verdict,phone_verdict\nplaceholder,correct,maybe',
    'record_id,verdict,phone_verdict,phone_verdict\nplaceholder,correct,correct,wrong',
    'record_id,verdict,phone_verdict\nplaceholder,correct'])
def test_invalid_field_verdict_columns_are_refused(text):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        audits.field_checks_csv(text)


def test_field_verdict_import_keeps_original_evidence_and_no_inferred_scores():
    text = 'record_id,name,verdict,phone_verdict,email_verdict\nplaceholder,unchanged,correct,wrong,\n'
    original, fields = audits.field_checks_csv(text)
    assert fields == {'placeholder': {'phone': 'wrong'}}
    assert list(csv.DictReader(io.StringIO(original))) == [{'record_id': 'placeholder', 'name': 'unchanged', 'verdict': 'correct'}]
    assert audits.field_checks_csv(original) == (original, None)
