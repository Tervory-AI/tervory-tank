"""GPU payload/checkpoint boundaries without paid jobs or model credentials."""
import hashlib
import importlib.util
import json
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "agents/rig/forge/gpu"


def module(name):
    spec=importlib.util.spec_from_file_location("forge_gpu_"+name,ROOT/(name+".py"))
    loaded=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_remote_manifest_rejects_cross_tenant_paths_and_bad_counts():
    entry=module("entrypoint")
    tenant,job=str(uuid.uuid4()),str(uuid.uuid4())
    body={"tenant_id":tenant,"job_id":job,"method":"trellis2","inputs":["part.png"],"dimensions_mm":[20,30,40]}
    entry.validate_manifest(body,tenant,job,"trellis2")
    for changed in ({"tenant_id":str(uuid.uuid4())},{"inputs":["../other.png"]},
                    {"inputs":[]},{"inputs":["part.png"]*5},{"dimensions_mm":[20,float("nan"),40]}):
        with pytest.raises(ValueError):entry.validate_manifest({**body,**changed},tenant,job,"trellis2")


def test_checkpoint_verification_and_local_only_config(tmp_path):
    models=module("prepare_models")
    (tmp_path/"trellis2").mkdir()
    config={"args":{"models":{},"image_cond_model":{"args":{}},"rembg_model":{"name":"upstream"}}}
    data=json.dumps(config).encode()
    path=tmp_path/"trellis2/pipeline.json"
    path.write_bytes(data)
    manifest=[{"destination":"trellis2","revision":"published-commit","files":[{"path":"pipeline.json",
        "sha256":hashlib.sha256(data).hexdigest(),
        "git_blob_sha1":hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()}]}]
    models.prepare(tmp_path,manifest)
    changed=json.loads(path.read_text())["args"]
    assert changed["rembg_model"]=={"name":"PreparedBackground","args":{}}
    assert changed["image_cond_model"]["args"]["model_name"]==str(tmp_path/"dino")
    assert json.loads((tmp_path/"verified-sha256.json").read_text())[0]["sha256"]==manifest[0]["files"][0]["sha256"]
    path.write_bytes(data+b" ")
    with pytest.raises(ValueError,match="checksum"):models.prepare(tmp_path,manifest)
