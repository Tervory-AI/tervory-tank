"""Optional per-room standby runtimes; fake Tank, Docker inspection and no network."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from unittest.mock import AsyncMock

import agent_skills
import httpx
import pytest
import yaml

from tiger_brain.test_tg3 import TENANT, corridor as corridor, load, topology
from test_room_seal import FIXTURES, leaks, network_flags, run_seal_check

ROOT = Path(__file__).resolve().parents[2]
ROOMS = json.loads((Path(__file__).parent / 'rooms.json').read_text())


def compose(room):
    return yaml.safe_load((ROOT / 'agents' / room / 'docker-compose.yml').read_text())


@pytest.mark.parametrize('room', ROOMS)
def test_off_by_default_hardened_and_no_shared_data(room):
    stem, upper = room.replace('_', '-'), room.upper()
    text = (ROOT / 'agents' / room / 'docker-compose.yml').read_text()
    config = compose(room)
    assert text.startswith('# coolify: raw compose\n') and leaks(text) == []
    services = config['services']
    assert services['agent-' + stem]['environment'][upper + '_BRAIN_ENABLED'] == '${' + upper + '_BRAIN_ENABLED:-false}'
    brain, sandbox = services[stem + '-brain'], services[stem + '-sandbox']
    assert brain['build']['dockerfile'] == 'agents/rig/Dockerfile.brain'
    assert brain['command'][1] == 'brain.standby:app'
    assert sandbox['build']['dockerfile'] == 'agents/base/Dockerfile.sandbox'
    assert brain['networks'] == ['gw', 'sandbox'] and sandbox['networks'] == ['sandbox']
    assert config['networks']['sandbox'] == {'internal': True}
    assert config['networks']['gw']['name'] == 'tervory-gw-' + room
    assert brain['volumes'] == [room + '_brain_data:/data'] and not sandbox.get('volumes')
    assert config['volumes'][room + '_brain_data'] == {'name': 'tervory-' + stem + '-brain-data'}
    assert (brain['mem_limit'], brain['cpus'], brain['pids_limit']) == ('2g', 1, 128)
    assert (sandbox['mem_limit'], sandbox['cpus'], sandbox['pids_limit']) == ('512m', .5, 64)
    assert any(value.startswith('/work:') for value in sandbox['tmpfs'])
    assert set(sandbox['environment']) == {'BRAIN_ROOM', 'SANDBOX_KEY'}
    assert brain['environment'][upper + '_URL'] == 'http://agent-' + stem + ':8000'
    assert brain['environment'][upper + '_SANDBOX_URL'] == 'http://' + stem + '-sandbox:8002'
    for spec in (brain, sandbox):
        assert spec['profiles'] == ['brain'] and spec['read_only'] and spec['tmpfs']
        assert all(value.startswith('/') for value in spec['tmpfs'])
        assert spec['cap_drop'] == ['ALL'] and spec['security_opt'] == ['no-new-privileges:true']
        assert spec['environment']['BRAIN_ROOM'] == room
        assert spec['environment']['SANDBOX_KEY'] == '${SANDBOX_KEY_' + upper + ':-}'
        assert not set(spec) & {'ports', 'env_file', 'privileged', 'cap_add', 'network_mode', 'devices', 'pid'}
        assert not any(part in key for key in spec['environment'] for part in ('COOLIFY', 'ENFORCE', 'R2_', 'DATABASE', 'OPENAI', 'ANTHROPIC', 'OPENROUTER', 'LITELLM', 'EDGE_', 'SMTP', 'UNDO'))
    assert brain['environment']['TANK_KEY'] == '${TANK_KEY_' + upper + ':-}'
    assert brain['environment']['TANK_URL'] == 'http://tank:8000'
    assert brain['environment']['HERMES_URL'] == 'http://hermes:8000'
    if room == 'ghost':
        assert brain['environment']['GHOST_BROWSER_URL'] == 'http://ghost-browser:8000'
    else:
        browser, gateway = services[stem + '-browser'], services[stem + '-browser-gateway']
        assert browser['networks'] == ['browser'] and gateway['networks'] == ['gw', 'browser']
        assert config['networks']['browser'] == {'internal': True}
        assert browser['volumes'] == [room + '_browser_data:/browser-data']
        assert config['volumes'][room + '_browser_data'] == {'name': 'tervory-' + stem + '-browser-data'}
        assert browser['build']['dockerfile'] == 'agents/base/Dockerfile.browser'
        assert gateway['build']['dockerfile'] == 'agents/base/Dockerfile.gateway'
        assert not gateway.get('volumes') and 'TANK_KEY' not in browser['environment']
        assert not any(key.startswith('ACCESS_BROWSER_KEY') for key in browser['environment'])
        assert brain['environment'][upper + '_BROWSER_URL'] == 'http://' + stem + '-browser-gateway:3000'
        for spec in (browser, gateway):
            assert spec['profiles'] == ['brain'] and spec['read_only'] and spec['tmpfs']
            assert spec['cap_drop'] == ['ALL'] and spec['security_opt'] == ['no-new-privileges:true']
            assert spec['pids_limit'] == 128 and spec['mem_limit'] and spec['cpus']
            assert not set(spec) & {'ports', 'env_file', 'privileged', 'cap_add', 'network_mode', 'devices'}


@pytest.mark.parametrize('room', ROOMS)
def test_existing_volumes_are_byte_for_byte_unchanged(room):
    saved = json.loads((Path(__file__).parent / 'snapshots' / (room + '.json')).read_text())
    text = (ROOT / 'agents' / room / 'docker-compose.yml').read_text()
    section = text.split('\nvolumes:\n', 1)[1].split('networks:\n', 1)[0]
    for kind in ('brain', 'browser'):
        section = re.sub(r'(?m)^  ' + room + '_' + kind + r'_data:\n(?:    .*\n)*', '', section)
    assert section == (saved['volumes'] if saved['volumes'] is not None else '\n')
    for name, mounts in saved['mounts'].items():
        assert compose(room)['services'][name].get('volumes') == mounts


@pytest.mark.parametrize('room', ROOMS)
@pytest.mark.parametrize('profile', [False, True])
def test_real_compose_profile_has_no_new_default_services(room, profile):
    binary = shutil.which('docker-compose')
    command = [binary] if binary else [shutil.which('docker'), 'compose']
    command += ['-f', str(ROOT / 'agents' / room / 'docker-compose.yml'), '--env-file', '/dev/null']
    if profile:
        command += ['--profile', 'brain']
    result = subprocess.run([*command, 'config', '--services'], capture_output=True, text=True, timeout=30,
                            env={'PATH': os.defpath, 'AGENT_DB_PASSWORD_' + room.upper(): 'placeholder-database'})
    assert result.returncode == 0, result.stderr
    saved = json.loads((Path(__file__).parent / 'snapshots' / (room + '.json')).read_text())
    expected = set(saved['mounts'])
    if profile:
        expected |= {name for name, spec in compose(room)['services'].items() if spec.get('profiles') == ['brain']}
    assert set(result.stdout.splitlines()) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('room', ROOMS)
async def test_health_only_standby_and_public_browser_no_vault_key(monkeypatch, room):
    monkeypatch.setenv('BRAIN_ROOM', room)
    app = load('placeholder_standby', ROOT / 'agents/_brain/standby.py').app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder.invalid') as client:
        assert (await client.get('/health')).json() == {'ok': True, 'room': room, 'hermes_version': '0.22.2'}
        assert (await client.post('/tasks', json={})).status_code == 404
    assert not any('POST' in getattr(route, 'methods', {}) for route in app.routes)
    if room != 'ghost':
        import sys
        import types
        package = types.ModuleType('brain')
        package.__path__ = [str(ROOT / 'agents/_brain')]
        monkeypatch.setitem(sys.modules, 'brain', package)
        monkeypatch.setenv('ACCESS_ROOM', room)
        monkeypatch.delenv('ACCESS_BROWSER_KEY_' + room.upper(), raising=False)
        # The shared browser requires its own gateway even for public requests.
        import importlib.util
        spec = importlib.util.spec_from_file_location('placeholder_browser_' + room, ROOT / 'agents/_brain/browser.py')
        browser = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, browser)
        spec.loader.exec_module(browser)
        assert browser.access_room() == room and not browser.access_configured()


@pytest.fixture
def owning(corridor, monkeypatch):
    for room in ROOMS:
        key = 'placeholder-' + room + '-key'
        monkeypatch.setenv('TANK_KEY_' + room.upper(), key)
        corridor.keys[room] = key
    return corridor


async def chat(env, room, key=None, region='us-east'):
    headers = {'X-Tank-Key': env.keys[room] if key is None else key, 'X-Tenant-ID': str(TENANT), 'X-Home-Region': region}
    async with env.client(transport=httpx.ASGITransport(app=env.app), base_url='http://placeholder.invalid') as client:
        return await client.post(env.app.url_path_for('chat', room=room), json={'messages': [{'role': 'user', 'content': 'placeholder request'}]}, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize('room', ROOMS)
async def test_owning_key_policy_pause_refusal_receipt_and_export(owning, room, monkeypatch):
    response = await chat(owning, room)
    assert response.status_code == 200, response.text
    owning.tank.load_policy.assert_awaited_once_with('agent.' + room + '.think', TENANT)
    assert owning.tank.model_call_refusal.call_args.kwargs['caller'] == room
    assert len(owning.sent) == 1 and len(owning.pool.rows) == 3
    assert owning.pool.rows[0][1][13:15] == (room, 'agent.' + room + '.think')
    assert all(row[1][1] == TENANT for row in owning.pool.rows)
    assert response.json()['receipt']['room'] == room
    owning.pool.paused = True
    assert (await chat(owning, room)).status_code == 503
    owning.pool.paused = False
    owning.tank.model_call_refusal.return_value = 'placeholder refusal'
    assert (await chat(owning, room)).status_code == 403
    assert (await chat(owning, room, region='za')).status_code == 403
    assert len(owning.sent) == 1
    export = AsyncMock(return_value={'skills': []})
    monkeypatch.setattr(agent_skills, 'export_skills', export)
    async with owning.client(transport=httpx.ASGITransport(app=owning.app), base_url='http://placeholder.invalid') as client:
        response = await client.get(owning.app.url_path_for('approved', room=room), params={'tenant_id': str(TENANT)}, headers={'X-Tank-Key': owning.keys[room]})
        assert response.status_code == 200
        export.assert_awaited_once_with(owning.tank, TENANT, 'us-east', room=room)
        candidate = {'tenant_id': str(TENANT), 'home_region': 'us-east', 'skill_id': 'base.learned.placeholder', 'version': '1.0.0', 'description': 'placeholder', 'instructions': 'placeholder', 'run_py': 'async def run(input, ctx): return input', 'cases': [{'input': {}, 'expected': {}}]}
        response = await client.post(owning.app.url_path_for('candidate', room=room), json=candidate, headers={'X-Tank-Key': owning.keys[room]})
        assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize('room', ROOMS)
async def test_all_foreign_room_keys_refused_before_any_work(owning, room):
    for foreign in ['', 'placeholder-workspace-key', *[key for name, key in owning.keys.items() if name != room]]:
        assert (await chat(owning, room, key=foreign)).status_code == 401
    assert not owning.pool.rows and not owning.sent


def placement(room):
    data = json.loads((FIXTURES / 'sealed.json').read_text())
    if room == 'tisan':
        sample = json.loads((FIXTURES / 'tisan.json').read_text())
        data['containers'].update(sample['containers'])
        data['networks'].update(sample['networks'])
    stem, project = room.replace('_', '-'), 'placeholder-' + room
    config = compose(room)
    flags = network_flags((ROOT / 'agents' / room / 'docker-compose.yml').read_text())
    # Retain historical required rooms and override this room's placement only.
    for name, spec in config['services'].items():
        if not spec.get('profiles'):
            continue
        declared = [config['networks'][net].get('name', project + '_' + net) for net in spec['networks']]
        for net, actual in zip(spec['networks'], declared):
            data['networks'][actual] = flags[net]
        data['containers'][name] = {'uuid': project, 'resource': 'agent-' + stem, 'project': project, 'service': name, 'name': 'placeholder-' + name, 'networks': declared}
    if room in {'market_lab', 'trigger'}:
        for name, spec in config['services'].items():
            if spec.get('profiles'):
                continue
            nets = []
            for net in spec['networks']:
                actual = config['networks'][net].get('name', project + '_' + net)
                data['networks'][actual] = flags[net]
                nets.append(actual)
            data['containers'][name] = {'uuid': project, 'resource': 'agent-' + stem, 'project': project, 'service': name, 'name': 'placeholder-' + name, 'networks': nets}
    else:
        # Move the new services into the historical room's project/UUID.
        existing = next(row for row in data['containers'].values() if row['service'] == 'agent-' + stem)
        for name, row in list(data['containers'].items()):
            if row['uuid'] != project:
                continue
            old_project = row['project']
            row.update(uuid=existing['uuid'], resource=existing['resource'], project=existing.get('project', existing['uuid']))
            row['networks'] = [net.replace(old_project + '_', row['project'] + '_') for net in row['networks']]
            for net in row['networks']:
                if net not in data['networks']:
                    data['networks'][net] = True
    return data


@pytest.mark.parametrize('room', ROOMS)
@pytest.mark.parametrize('fault', ['none', 'extra_internal', 'extra_outward', 'missing', 'outward_private'])
@pytest.mark.parametrize('kind', ['brain', 'sandbox', 'browser', 'browser-gateway'])
def test_seal_exact_networks_and_partial_optional_group(tmp_path, room, fault, kind):
    if room == 'ghost' and kind.startswith('browser'):
        pytest.skip('Watch keeps its existing browser; no new browser pair')
    data = placement(room)
    name = room.replace('_', '-') + '-' + kind
    if fault == 'missing':
        del data['containers'][name]
    elif fault.startswith('extra'):
        data['containers'][name]['networks'].append('placeholder-foreign')
        data['networks']['placeholder-foreign'] = fault == 'extra_internal'
    elif fault == 'outward_private':
        private = next(net for net in data['containers'][name]['networks'] if net.endswith(('_sandbox', '_browser')))
        data['networks'][private] = False
    path = tmp_path / 'placeholder-room.json'
    path.write_text(json.dumps(data))
    result = run_seal_check(tmp_path, str(path))
    assert result.returncode == (0 if fault == 'none' else 1), result.stdout + result.stderr
    if fault != 'none':
        assert any(word in result.stdout for word in ('LEAK:', 'NOT FOUND:', 'NOT SEALED:'))


@pytest.mark.parametrize('room', ROOMS)
@pytest.mark.parametrize('fault', ['none', 'foreign_sandbox', 'shared_volume', 'provider_key', 'control_plane', 'extra_private_member'])
def test_isolation_checker_with_own_fixture(monkeypatch, capsys, room, fault):
    stem = room.replace('_', '-')
    names, rows, networks = topology(room)
    for row in rows.values():
        row['Config']['Labels']['com.docker.compose.project'] = 'placeholder'
        row['Config']['Labels']['com.docker.compose.service'] = row['Config']['Labels']['com.docker.compose.service'].replace(room, stem)
    brain = rows[names[1]]
    brain['Mounts'] = [{'Type': 'volume', 'Destination': '/data', 'Name': 'tervory-' + stem + '-brain-data'}]
    brain['Config']['Env'] = ['BRAIN_ROOM=' + room]
    rows[names[3]]['Mounts'] = [{'Type': 'volume', 'Destination': '/browser-data', 'Name': 'tervory-' + stem + '-browser-data'}]
    extra = {'radix': 'proxy-link', 'tisan': 'figma_internal', 'trigger': 'checkers'}.get(room)
    if extra:
        rows[names[0]]['NetworkSettings']['Networks']['placeholder_' + extra] = {}
    if room == 'ghost':
        names.pop()
        rows[names[3]]['NetworkSettings']['Networks'] = {'tervory-gw-ghost': {}}
        networks['tervory-gw-ghost']['Containers'][names[3]] = {}
    if fault == 'foreign_sandbox':
        rows[names[2]]['Config']['Labels']['com.docker.compose.service'] = 'base-sandbox'
    elif fault == 'shared_volume':
        brain['Mounts'][0]['Name'] = 'placeholder-existing-room-data'
    elif fault == 'provider_key':
        brain['Config']['Env'].append('OPENAI_API_KEY=placeholder-value')
    elif fault == 'control_plane':
        brain['Config']['Env'].append('COOLIFY_TOKEN_GHOST=placeholder-value')
    elif fault == 'extra_private_member':
        networks['placeholder_sandbox']['Containers']['foreign'] = {}
    gate = load('placeholder_room_isolation', ROOT / 'agents/base/check_brain_isolation.py')
    def docker(*args):
        if args[0] == 'inspect':
            return json.dumps([rows[args[1]]])
        if args[:2] == ('network', 'inspect'):
            return json.dumps([networks[args[2]]])
        assert args[0] == 'exec'
        compile(args[-1], 'placeholder probe', 'exec')
        return ''
    monkeypatch.setattr(gate, 'docker', docker)
    if fault == 'none':
        gate.main(names)
        assert 'PASS ' + room.title() + ' topology' in capsys.readouterr().out
    else:
        with pytest.raises(AssertionError):
            gate.main(names)
