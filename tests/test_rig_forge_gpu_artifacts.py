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
    body={"tenant_id":tenant,"job_id":job,"method":"trellis2","inputs":["part.png"],"dimensions_mm":[20,30,40],"timeout_seconds":60}
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


def test_remote_controller_uses_only_fixed_capabilities_and_scrubs_child(monkeypatch):
    entry = module("entrypoint")
    tenant, job = str(uuid.uuid4()), str(uuid.uuid4())
    prefix = f"forge/{tenant}/{job}/"
    body = {"tenant_id": tenant, "job_id": job, "method": "trellis2", "inputs": ["photo.png"],
            "dimensions_mm": [20, 30, 40], "timeout_seconds": 60}
    host = uuid.uuid4().hex + ".r2.cloudflarestorage.com"
    def url(relative):
        # Not a usable signed URL or credential; scope validation is exercised.
        return "https://" + host + "/tervory-rig/" + prefix + relative + "?scope-test"
    transfers = {"manifest": body, "get": {"photo.png": url("inputs/photo.png")},
                 "put": {name: url("gpu/" + name) for name in ("result.glb", "source.zip")}}
    monkeypatch.setenv("FORGE_TENANT_ID", tenant)
    monkeypatch.setenv("FORGE_JOB_ID", job)
    monkeypatch.setenv("FORGE_TRANSFERS", json.dumps(transfers))
    downloads, uploads = [], []
    def download(capability, path, maximum):
        downloads.append((capability == transfers["get"]["photo.png"], maximum))
        path.write_bytes(b"photo")
    def reconstruct(args, **kwargs):
        assert set(kwargs["env"]) <= {"PATH", "LD_LIBRARY_PATH", "CUDA_HOME", "HOME", "TMPDIR",
            "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "PYTHONPATH",
            "OMP_NUM_THREADS", "OPENCV_IO_ENABLE_OPENEXR", "PYTORCH_CUDA_ALLOC_CONF"}
        assert kwargs["timeout"] == 60
        output = Path(args[-1]) / "outputs"
        output.mkdir()
        (output / "result.glb").write_bytes(b"glb")
        (output / "model.obj").write_bytes(b"obj")
        (output / "texture.png").write_bytes(b"texture")
    def upload(capability, path):
        assert capability == transfers["put"][path.name]
        uploads.append(path.name)
        if path.name == "source.zip":
            import zipfile
            with zipfile.ZipFile(path) as archive:
                assert set(archive.namelist()) == {"model.obj", "texture.png"}
    monkeypatch.setattr(entry, "download", download)
    monkeypatch.setattr(entry, "upload", upload)
    monkeypatch.setattr(entry.subprocess, "run", reconstruct)
    entry.main("trellis2")
    assert downloads == [(True, 20_000_000)] and uploads == ["source.zip", "result.glb"]
    for invalid in (url("gpu/other.glb"), url("inputs/photo.png").replace(tenant, str(uuid.uuid4())),
                    url("inputs/photo.png").replace(host, "127.0.0.1"),
                    url("inputs/photo.png").replace("https:", "http:")):
        with pytest.raises(ValueError):
            entry.validate_url(invalid, prefix + "inputs/photo.png")


def test_remote_transfer_refuses_redirects_and_does_not_print_urls(monkeypatch, tmp_path, capsys):
    entry = module("entrypoint")
    class Redirect:
        status_code = 302
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def redirect(*args, **kwargs):
        assert kwargs["allow_redirects"] is False
        return Redirect()
    monkeypatch.setattr(entry.requests, "get", redirect)
    with pytest.raises(ValueError, match="Input transfer failed"):
        entry.download("opaque-capability", tmp_path / "photo", 20_000_000)
    assert not (tmp_path / "photo").exists() and not capsys.readouterr().out
