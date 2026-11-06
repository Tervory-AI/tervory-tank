"""Concurrent builds and approved evidence stay durable and tenant private."""
from concurrent.futures import ProcessPoolExecutor
import copy
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest
from agents.tisan import scaffold, builder
from test_tisan_builder import payload, copy_for, client_for
from test_tisan_wave4_pipeline import service, payload as request_payload, TENANT


def reserve(folder):
    return scaffold._next_build_number(Path(folder))


def test_concurrent_builds_reserve_distinct_numbers_and_keep_failed_receipts(tmp_path):
    (tmp_path/'7.json').write_text('{"ok":false}')
    (tmp_path/'3.tar.gz').write_bytes(b'placeholder')
    with ProcessPoolExecutor(max_workers=4) as processes:
        numbers = list(processes.map(reserve, [str(tmp_path)] * 24))
    assert sorted(numbers) == list(range(8, 32))
    assert reserve(str(tmp_path)) == 32
    assert json.loads((tmp_path/'7.json').read_text()) == {'ok': False}


@pytest.mark.asyncio
async def test_pipeline_binds_approved_frame_even_when_caller_omits_it(tmp_path):
    flow, calls = service(tmp_path)
    data = request_payload()
    original = copy.deepcopy(data)
    result = await flow.run(str(TENANT), str(uuid4()), data)
    assert result['ok'] is True
    assert calls.build.await_args.args[2]['figma'] == {
        'file_key': calls.approval.return_value['figma_file_id'],
        'node_id': calls.approval.return_value['figma_frame_id']}
    assert data == original


@pytest.mark.asyncio
async def test_pipeline_never_builds_a_caller_selected_unapproved_frame(tmp_path):
    flow, calls = service(tmp_path)
    data = request_payload()
    data['brief']['figma'] = {'file_key': 'placeholderOtherFileKey01', 'node_id': '9:9'}
    result = await flow.run(str(TENANT), str(uuid4()), data)
    assert not result['ok']
    calls.build.assert_not_awaited()
    calls.stage.assert_not_awaited()


@pytest.mark.asyncio
async def test_builder_carries_recorded_visual_pair_into_actual_checks(tmp_path, monkeypatch):
    data = payload()
    data['copy'] = copy_for(builder, data['plan'])
    data['figma'] = {'file_key': 'placeholderFigmaFileKey01', 'node_id': '0:1'}
    frames = [{'frameId': '0:1' if width == 1440 else '0:2', 'width': width, 'page': '/'}
              for width in (375, 1440)]
    path = tmp_path/'readings'/str(TENANT)/data['figma']['file_key']/'0-1.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'visual': frames}))
    module = builder._scaffold()
    async def check(project, **kwargs):
        assert json.loads((project/'visual/frames.json').read_text()) == frames
        return [{'name': 'accessibility', 'ok': False, 'summary': 'frame data incomplete'}], 'frame data incomplete'
    monkeypatch.setattr(module, 'run_checks', check)
    monkeypatch.setattr(builder, '_scaffold', lambda: module)
    async with client_for(tenant=str(TENANT)) as client:
        result = await builder.execute(data, str(TENANT), http=client, data_root=tmp_path)
    assert result['ok'] is False
    assert not list(tmp_path.rglob('*.tar.gz'))


def test_saved_reading_cannot_follow_a_different_tenants_symlink(tmp_path):
    tenant = str(TENANT)
    other = tmp_path/'readings'/str(uuid4())
    other.mkdir(parents=True)
    (tmp_path/'readings'/tenant).symlink_to(other, target_is_directory=True)
    source = {'file_key': 'placeholderFigmaFileKey01', 'node_id': '0:1'}
    with pytest.raises(ValueError, match='frame data incomplete'):
        scaffold.attach_visual_frames({'figma': source}, tmp_path/'project', tmp_path, tenant, {'pages':['home']})


def test_actual_visual_gate_detects_text_and_geometry_regressions():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', 'tests/tisan_finish_visual.cjs'], cwd=root, capture_output=True,
                            text=True, timeout=60, env=os.environ.copy())
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'visual comparisons passed' in result.stdout


@pytest.mark.asyncio
async def test_direct_room_builds_inherit_the_same_approved_source(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from agents.tisan import app as room
    module = room._load_beside(room._figma_cache(), 'tisan_pipeline_room', 'pipeline.py')
    approval = {'figma_file_id': 'placeholderFigmaFileKey01', 'figma_frame_id': '0:1'}
    monkeypatch.setattr(module, 'service', lambda *args: SimpleNamespace(approved_page=AsyncMock(return_value=approval)))
    monkeypatch.setattr(room.app.state, 'pool', object(), raising=False)
    original = {'page_id': 'placeholder-home'}
    context = SimpleNamespace(tenant_id=str(TENANT), input=original)
    assert await room._approved_build(context) is True
    assert context.input['figma'] == {'file_key': approval['figma_file_id'], 'node_id': '0:1'}
    assert original == {'page_id': 'placeholder-home'}
