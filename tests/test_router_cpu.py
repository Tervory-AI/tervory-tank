"""CPU transport/process boundaries without model downloads or inference in CI."""
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import router_cpu as cpu


def spec(body=b'placeholder checkpoint',name='config.json'):
    return {'arch':{'repo':'placeholder/model','revision':'a'*40,'files':[
        {'name':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}]}}


@pytest.fixture
def disk(monkeypatch):
    monkeypatch.setattr(cpu.shutil,'disk_usage',lambda root:SimpleNamespace(free=20*cpu.GIB))


def test_bounded_download_verifies_and_reuses(tmp_path,disk):
    body=b'placeholder checkpoint'
    calls=[]
    def open_file(url,timeout):
        calls.append((url,timeout))
        return io.BytesIO(body)
    metadata=spec(body)
    cpu.download(metadata,tmp_path,opener=open_file)
    cpu.verify(tmp_path/'arch',metadata['arch']['files'])
    cpu.download(metadata,tmp_path,opener=open_file)
    assert len(calls)==1 and calls[0][1]==20
    assert (tmp_path/'arch/REVISION').read_text().strip()=='a'*40
    (tmp_path/'arch/config.json').write_bytes(b'placeholder corrupted')
    with pytest.raises(ValueError,match='mismatch'):
        cpu.verify(tmp_path/'arch',metadata['arch']['files'])


@pytest.mark.parametrize('body',[b'too short',b'x'*200])
def test_incomplete_or_oversize_download_cannot_be_loaded(tmp_path,disk,body):
    with pytest.raises(ValueError):
        cpu.download(spec(),tmp_path,opener=lambda *args,**kwargs:io.BytesIO(body))
    assert not list(tmp_path.rglob('*.part'))
    assert not (tmp_path/'arch/config.json').exists()


@pytest.mark.parametrize('name',['../outside.json','optimizer.pt','rng_state.pth','training_args.bin'])
def test_training_binary_and_path_traversal_rejected(tmp_path,disk,name):
    def forbidden(*args,**kwargs):
        pytest.fail('unreviewed download was attempted')
    with pytest.raises(ValueError,match='reviewed'):
        cpu.download(spec(name=name),tmp_path,opener=forbidden)


def test_total_size_and_disk_budgets(tmp_path,disk,monkeypatch):
    metadata=spec()
    metadata['arch']['files'][0]['bytes']=cpu.MAX_DOWNLOAD+1
    with pytest.raises(ValueError,match='byte budget'):
        cpu.download(metadata,tmp_path)
    monkeypatch.setattr(cpu.shutil,'disk_usage',lambda root:SimpleNamespace(free=0))
    with pytest.raises(ValueError,match='free disk'):
        cpu.download(spec(),tmp_path)


def test_timeout_kills_only_own_worker(tmp_path,monkeypatch):
    worker=tmp_path/'worker.py'
    worker.write_text('import time\ntime.sleep(10)\n')
    monkeypatch.setattr(cpu,'WALL_SECONDS',.2)
    with pytest.raises(TimeoutError,match='wall budget'):
        cpu.run_worker(sys.executable,worker,tmp_path/'request.json',tmp_path/'output.json')
    assert not (tmp_path/'output.json').exists()


def test_failed_worker_does_not_disclose_exception_details(tmp_path):
    worker=tmp_path/'worker.py'
    worker.write_text('raise RuntimeError("placeholder private details")\n')
    with pytest.raises(RuntimeError,match='CPU worker failed') as stopped:
        cpu.run_worker(sys.executable,worker,tmp_path/'request.json',tmp_path/'output.json')
    assert 'private' not in str(stopped.value)


def test_manifest_contains_only_immutable_inference_assets():
    root=Path('tools/router_cpu')
    data=json.loads((root/'checkpoints.json').read_text())
    assert data['arch']['revision']=='5b156890a91b1035a86f82faf1a651debf309009'
    assert data['routellm']['revision']=='86237e3df400762178ea98379477b8296e66d5e4'
    assert sum(f['bytes'] for s in data.values() for f in s['files'])<cpu.MAX_DOWNLOAD
    for model in data.values():
        assert len(model['revision'])==40
        for item in model['files']:
            assert len(item['sha256'])==64 and item['bytes']>0
            assert not item['name'].endswith(('.pt','.pth','.bin'))
    lock=(root/'requirements.lock').read_text()
    assert 'torch==2.15.0+cpu' in lock and 'nvidia-' not in lock


def test_resume_verifies_full_file_including_existing_prefix(tmp_path,disk):
    body=b'placeholder checkpoint'
    folder=tmp_path/'arch'
    folder.mkdir()
    (folder/'config.json.part').write_bytes(body[:5])
    class Partial(io.BytesIO):
        status=206
        headers={'Content-Range':f'bytes 5-{len(body)-1}/{len(body)}'}
    def transfer(request,timeout):
        assert request.get_header('Range')=='bytes=5-'
        return Partial(body[5:])
    cpu.download(spec(body),tmp_path,opener=transfer)
    cpu.verify(folder,spec(body)['arch']['files'])
    assert not list(folder.glob('*.part'))


def test_server_ignoring_range_overwrites_prefix(tmp_path,disk):
    body=b'placeholder checkpoint'
    folder=tmp_path/'arch'
    folder.mkdir()
    (folder/'config.json.part').write_bytes(b'wrong cached prefix')
    cpu.download(spec(body),tmp_path,opener=lambda *args,**kwargs:io.BytesIO(body))
    assert (folder/'config.json').read_bytes()==body


def test_worker_preserves_virtual_environment_identity(tmp_path):
    import subprocess
    environment=tmp_path/'venv'
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(environment)],check=True,timeout=30)
    worker=tmp_path/'worker.py'
    worker.write_text('import json,sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_text(json.dumps({"prefix":sys.prefix}))\n')
    result=cpu.run_worker(environment/'bin/python',worker,tmp_path/'request.json',tmp_path/'output.json')
    assert Path(result['prefix'])==environment
