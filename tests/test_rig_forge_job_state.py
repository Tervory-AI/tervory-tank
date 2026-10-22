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
