"""Persistent artifacts remain complete, isolated and available after restart."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Event
from uuid import uuid4

import pytest
from agents.tisan import storage, scaffold, figma


@pytest.mark.parametrize('module', [scaffold, figma])
def test_unwritable_room_volume_never_falls_back_to_temporary_storage(module, tmp_path, monkeypatch):
    destination = tmp_path/'configured-data'
    monkeypatch.setenv('DATA_DIR', str(destination))
    monkeypatch.setenv('TMPDIR', str(tmp_path/'temporary'))
    def unavailable(**kwargs):
        raise PermissionError('placeholder unavailable volume')
    monkeypatch.setattr(storage.tempfile, 'NamedTemporaryFile', unavailable)
    with pytest.raises(ValueError):
        module._data_root(None)
    assert not (tmp_path/'temporary/tisan-data').exists()
    assert list(destination.iterdir()) == []


def test_concurrent_root_probes_never_remove_each_other_or_change_volume(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        roots = list(pool.map(storage.durable_root, [tmp_path]*32))
    assert roots == [tmp_path]*32
    assert list(tmp_path.iterdir()) == []


def test_failed_serialization_preserves_existing_receipt_and_cleans_partial(tmp_path):
    target = tmp_path/'receipt.json'
    storage.atomic_json(target, {'ok': True, 'revision': 1})
    with pytest.raises(TypeError):
        storage.atomic_json(target, {'payload': object()})
    assert json.loads(target.read_text()) == {'ok': True, 'revision': 1}
    assert [p.name for p in tmp_path.iterdir()] == ['receipt.json']


def test_readers_never_observe_truncated_receipts_while_updates_commit(tmp_path):
    target = tmp_path/'receipt.json'
    storage.atomic_json(target, {'revision': 0, 'payload': 'x'*8192})
    done = Event()
    def writer():
        try:
            for revision in range(1, 40):
                storage.atomic_json(target, {'revision': revision, 'payload': 'x'*8192})
        finally:
            done.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        observed = []
        while not done.is_set():
            value = json.loads(target.read_text())
            assert value['payload'] == 'x'*8192
            observed.append(value['revision'])
        future.result()
    assert observed
    assert json.loads(target.read_text())['revision'] == 39


@pytest.mark.parametrize('category', ['builds', 'readings', 'reviews'])
def test_tenant_directories_cannot_alias_another_tenant(category, tmp_path):
    tenant, other = str(uuid4()), str(uuid4())
    foreign = tmp_path/category/other
    foreign.mkdir(parents=True)
    (tmp_path/category/tenant).symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError):
        storage.tenant_folder(tmp_path, category, tenant)
    assert list(foreign.iterdir()) == []


def test_atomic_receipt_cannot_overwrite_a_symlink_target(tmp_path):
    foreign = tmp_path/'other.json'
    foreign.write_text('{"private":true}')
    alias = tmp_path/'alias.json'
    alias.symlink_to(foreign)
    with pytest.raises(ValueError):
        storage.atomic_json(alias, {'private':False})
    assert json.loads(foreign.read_text()) == {'private': True}


def test_flat_room_image_imports_the_same_storage_module_without_a_checkout(tmp_path):
    room = Path(__file__).resolve().parents[1]/'agents/tisan'
    for name in ['scaffold.py', 'figma.py', 'storage.py']:
        shutil.copy2(room/name, tmp_path/name)
    code = ('import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
            'import scaffold,figma; root=Path(sys.argv[1])/"data"; '
            'assert scaffold._data_root(root)==root; assert figma._data_root(root)==root')
    result = subprocess.run([sys.executable, '-I', '-c', code, str(tmp_path)], cwd=tmp_path,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    docker = (room/'Dockerfile').read_text()
    assert 'agents/tisan/storage.py' in docker


@pytest.mark.parametrize('category', ['builds', 'readings', 'reviews'])
def test_existing_review_artifact_aliases_are_rejected_on_read(category, tmp_path):
    from agents.tisan import gold_sources
    tenant, other = str(uuid4()), str(uuid4())
    foreign = tmp_path/category/other
    foreign.mkdir(parents=True)
    (foreign/'private.json').write_text('{"private":true}')
    own = tmp_path/category/tenant
    own.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match='invalid artifact path'):
        gold_sources.safe_path(own, 'private.json')


def test_publish_cannot_read_a_different_tenants_build_directory(tmp_path):
    from agents.tisan import publish
    tenant, other = str(uuid4()), str(uuid4())
    foreign = tmp_path/'builds'/other/'placeholder-site'
    foreign.mkdir(parents=True)
    (foreign/'1.json').write_text('{}')
    (foreign/'1.tar.gz').write_bytes(b'placeholder')
    own = tmp_path/'builds'/tenant
    own.symlink_to(foreign.parent, target_is_directory=True)
    with pytest.raises(ValueError, match='invalid stored build'):
        publish.stored_build(tmp_path, tenant, 'placeholder-site', 1)


def test_optimized_python_still_refuses_reading_file_symlinks(tmp_path):
    folder = tmp_path/'readings/tenant-a/placeholderFigmaFileKey01'
    folder.mkdir(parents=True)
    foreign = tmp_path/'outside.json'
    foreign.write_text('placeholder original')
    (folder/'0-1.json').symlink_to(foreign)
    code = """from pathlib import Path
import sys
from agents.tisan import figma
try:
    figma._store({'file_key':'placeholderFigmaFileKey01','node':{'id':'0:1'}}, 'tenant-a', Path(sys.argv[1]))
except figma.FigmaError:
    pass
else:
    raise RuntimeError('symlink refusal missing')
"""
    result = subprocess.run([sys.executable, '-O', '-c', code, str(tmp_path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert foreign.read_text() == 'placeholder original'
