import json
import uuid

import pytest

from agents.rig.forge import service


@pytest.mark.asyncio
async def test_intake_failure_records_failure_and_stops(monkeypatch, tmp_path):
    body=service.Job(tenant_id=uuid.uuid4(),job_id=uuid.uuid4(),home_region="us-east",method="scan",
                     inputs=["scan.obj"],unit_mm=1,dimensions_mm=(20,30,40))
    events=[]
    async def relay(action,payload):
        events.append((action,payload))
        return payload
    class MissingStorage:
        def download(self,*args):raise OSError("Unavailable")
    monkeypatch.setattr(service,"relay",relay)
    await service.perform(body,tmp_path,MissingStorage())
    state=json.loads((tmp_path/"state.json").read_text())
    assert state["status"]=="failed" and "intake" in state["error"]
    assert len(events)==1 and events[0][1]["outcome"]=="failed"


@pytest.mark.asyncio
async def test_receipt_outage_persists_pending_and_never_advances(monkeypatch,tmp_path):
    body=service.Job(tenant_id=uuid.uuid4(),job_id=uuid.uuid4(),home_region="us-east",method="scan",
                     inputs=["scan.obj"],unit_mm=1,dimensions_mm=(20,30,40))
    async def relay(*args):raise OSError("Unavailable")
    class Storage:
        def download(self,name,destination):destination.write_text("v 0 0 0\n")
    monkeypatch.setattr(service,"relay",relay)
    await service.perform(body,tmp_path,Storage())
    state=json.loads((tmp_path/"state.json").read_text())
    pending=json.loads((tmp_path/"pending-receipt.json").read_text())
    assert state["status"]=="failed" and state["stage"]=="intake"
    assert pending["tenant_id"]==str(body.tenant_id) and pending["outcome"]=="delivered"
    assert not (tmp_path/"blender.glb").exists()


@pytest.mark.asyncio
async def test_success_uploads_before_cleaning_meshes_and_textures(monkeypatch, tmp_path):
    body = service.Job(tenant_id=uuid.uuid4(), job_id=uuid.uuid4(), home_region="us-east", method="scan",
                       inputs=["scan.obj"], unit_mm=1, dimensions_mm=(20, 30, 40))
    uploads = []
    class Storage:
        def download(self, name, path): path.write_bytes(b"input")
        def upload(self, name, path): uploads.append((name, path.read_bytes()))
        def key(self, name): return name
    async def relay(action, payload): return payload
    async def pipeline(source, work, **kwargs):
        (work / "draft.glb").write_bytes(b"glb")
        (work / "report.json").write_text('{"passed":true}')
        (work / "textures").mkdir()
        (work / "textures/map.png").write_bytes(b"texture")
        return {"passed": True}
    monkeypatch.setattr(service, "relay", relay)
    monkeypatch.setattr(service, "run", pipeline)
    service.save(tmp_path / "request.json", body.model_dump(mode="json"))
    await service.perform(body, tmp_path, Storage())
    assert [name for name, _ in uploads] == ["drafts/model.glb", "drafts/report.json"]
    assert set(path.name for path in tmp_path.iterdir()) == {"state.json", "request.json", "report.json"}
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["status"] == "draft" and state["finished_at"] > 0
