"""Wave 4 runs entirely on uploaded/recorded evidence, without services."""
import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import command
import httpx
import pytest
from fastapi import FastAPI
import base_compare
from base_lists import field
from agents.base.engines.scaffold import scaffold
from test_base_lists import Pool, TENANT, OTHER, record

ROOT = Path(__file__).resolve().parents[1]


def load_contacts():
    spec = importlib.util.spec_from_file_location('contacts_wave4', ROOT / 'tank/skills/base.contacts/1.4.0/run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('number,country,valid,line,region', [
    ('+12025550123', 'US', True, 'fixed-or-mobile', 'US'),
    ('+12025550123', 'FR', True, 'fixed-or-mobile', 'US'),
    ('123', 'US', False, 'unknown', None),
    ('not-a-phone', 'US', False, 'unknown', None),
    ('+12025550123', '', True, 'fixed-or-mobile', 'US'),
])
def test_phone_metadata_preserves_evidence(number, country, valid, line, region):
    item = {'value': number, 'source_url': 'https://placeholder.example/', 'checked_at': '2026-11-03'}
    result = load_contacts().phone_quality(item, country)
    for key, value in [('phone_valid', valid), ('phone_line_type', line), ('phone_region', region)]:
        assert result[key]['value'] == value
        assert result[key]['source_url'] == item['source_url']
        assert result[key]['checked_at'] == item['checked_at']
        assert result[key]['method'] == 'libphonenumber'


@pytest.mark.asyncio
async def test_contacts_candidate_evals_offline():
    from skala import score_case
    module = load_contacts()
    cases = [json.loads(line) for line in (ROOT / 'tank/skills/base.contacts/1.4.0/evals/cases.jsonl').read_text().splitlines()]
    assert len(cases) >= 5 and any(case.get('must_refuse') for case in cases)
    for case in cases:
        actual = await module.run(case['input'], None)
        ok, reason = score_case(case['expected'], actual, case.get('tolerance', 'exact'))
        assert ok, (case['name'], reason)


def businesses():
    first, second = record(), record()
    second['record_id'] = str(uuid4())
    second['licence_key'] = 'placeholder-base-only'
    return [first, second]


def test_apollo_counts_field_agreement_and_unmatched_rows():
    rows = businesses()
    rows[0]['fields']['website'] = field('https://placeholder.example', 'https://placeholder.example', '2026-11-03')
    rows[0]['fields']['phone'] = field('+12025550123', 'https://placeholder.example', '2026-11-03')
    rows[0]['fields']['email'] = field(['info@placeholder.example'], 'https://placeholder.example', '2026-11-03')
    csv = f'Licence Key,Company Website,Company Phone,Email\n{rows[0]["licence_key"]},https://www.placeholder.example/,2025550123,other@placeholder.example\nplaceholder-apollo-only,https://other.example,,\n'
    result = base_compare.compare(rows, csv)
    assert (result['matched'], result['base_only'], result['apollo_only']) == (1, 1, 1)
    assert result['field_agreement']['website']['matches'] == 1
    assert result['field_agreement']['phone']['matches'] == 1
    assert result['field_agreement']['email']['disagreements'] == 1
    assert len(result['records']) == result['total'] == 3
    assert json.loads(result['summary'])['matched'] == 1


def test_apollo_ambiguous_domains_and_unverified_evidence_do_not_match():
    rows = businesses()
    for row in rows:
        row['fields']['website'] = field('https://placeholder.example', 'https://placeholder.example', '2026-11-03')
    text = 'Company Website\nhttps://placeholder.example\n'
    assert base_compare.compare(rows, text)['matched'] == 0
    assert base_compare.compare(rows[:1], text + 'https://placeholder.example\n')['matched'] == 0
    rows[0]['fields']['website']['verified'] = False
    assert base_compare.compare(rows[:1], text)['matched'] == 0


@pytest.mark.parametrize('text', ['', 'a,a\n1,2', 'a,b\n1', 'a\n1,2', 'Website,Company Website\na,b'])
def test_invalid_apollo_csv(text):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        base_compare.compare([], text)


@pytest.mark.asyncio
async def test_apollo_read_owned_upload_saved_list_and_zero_receipt(monkeypatch):
    own, foreign, attachment, ledger_id = uuid4(), uuid4(), uuid4(), uuid4()
    receipts = []
    class UploadPool(Pool):
        async def fetchrow(self, sql, *args):
            if 'command_attachments' in sql:
                assert 'tenant_id=$2 AND user_id=$3' in sql
                assert args == (attachment, TENANT, 'placeholder-user')
                return self.upload
            return await super().fetchrow(sql, *args)
        async def fetchval(self, sql, *args):
            assert "'code',0,0,0" in sql
            assert args == (TENANT, 'us-east', 'base.compare.apollo')
            receipts.append(args)
            return ledger_id
    pool = UploadPool()
    pool.upload = {'content': b'Company Website\nhttps://placeholder.example\n'}
    for tenant, identity in [(TENANT, own), (OTHER, foreign)]:
        pool.saved[tenant, identity] = {'records': json.dumps(businesses()), 'filters': '{}', 'name': 'placeholder'}
    actor = command.Actor(TENANT, 'placeholder-user', False, frozenset({'base'}))
    monkeypatch.setattr(command, 'db', lambda: pool)
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    app = FastAPI()
    app.include_router(base_compare.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        params = {'list_id': str(own), 'attachment_id': str(attachment)}
        response = await client.get('/v1/command/base/compare/apollo', params=params)
        assert response.status_code == 200
        assert response.json()['cost_usd'] == 0
        assert response.json()['ledger_id'] == str(ledger_id)
        assert len(receipts) == 1
        response = await client.get('/v1/command/base/compare/apollo', params={**params, 'list_id': str(foreign)})
        assert response.status_code == 404
        pool.upload = None
        response = await client.get('/v1/command/base/compare/apollo', params=params)
        assert response.status_code == 404
        assert len(receipts) == 1
    assert 'base.compare.apollo' in command.TOOLS['base']
    assert command.ADAPTERS['base.compare.apollo'].method == 'GET'


def test_ffl_manifest_preserves_every_existing_asset_byte_for_byte():
    manifest = json.loads((ROOT / 'agents/base/engines/ffl/manifest.json').read_text())
    assert manifest['sot'] == manifest['compliance_flags'] == []
    assert manifest['skills'] == ['ffl.ingest', 'ffl.profile']
    assert manifest['entrypoints']['project'].endswith('reference:project')
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    assert 'agents/base/engines/ffl/reference.py' in manifest['files']
    assert any(name.startswith('tank/skills/ffl.profile/') for name in manifest['files'])


def test_new_vertical_scaffold_is_empty_and_never_overwrites(tmp_path):
    package = scaffold('placeholder_vertical', tmp_path)
    manifest = json.loads((package / 'manifest.json').read_text())
    assert manifest['id'] == 'placeholder_vertical'
    assert manifest['sot'] == manifest['compliance_flags'] == manifest['skills'] == []
    assert manifest['entrypoints'] == {}
    with pytest.raises(FileExistsError):
        scaffold('placeholder_vertical', tmp_path)
    for name in ['../bad', 'ffl', 'bad-name']:
        with pytest.raises(ValueError):
            scaffold(name, tmp_path)


def test_apollo_card_labels_and_read_adapter(monkeypatch):
    import ast
    import subprocess
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'us-east'))
    actor = command.Actor(TENANT, 'placeholder-user', False, frozenset({'base'}))
    action = command.validate_action(command.PlannedAction(tool='base.compare.apollo', arguments={
        'list_id': str(uuid4()), 'attachment_id': str(uuid4())}), actor)
    method, path, params, body = command.adapter_request(action, actor)
    assert method == 'GET' and path == '/v1/command/base/compare/apollo' and body is None
    assert not command.ADAPTERS[action.tool].paid
    sets = [node for node in ast.walk(ast.parse((ROOT / 'tank/command.py').read_text())) if isinstance(node, ast.Set)]
    assert all('base.compare.apollo' not in [item.value for item in node.elts if isinstance(item, ast.Constant)] for node in sets)
    result = subprocess.run(['node', 'tests/base_compare_apollo.cjs'], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
