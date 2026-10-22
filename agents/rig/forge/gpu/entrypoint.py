"""HF Jobs controller: scoped R2 I/O; native/GPU child processes get no secrets."""
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import boto3
from botocore.config import Config


def validate_manifest(body, tenant, job, method):
    if body.get("tenant_id") != tenant or body.get("job_id") != job or body.get("method") != method:
        raise ValueError("Manifest scope mismatch")
    names = body["inputs"]
    low, high = (50, 150) if method == "photogrammetry" else (1, 4)
    if not low <= len(names) <= high or len(set(names)) != len(names):
        raise ValueError("Invalid photo count")
    if any(not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,110}\.(?i:png|jpe?g|webp)", name) for name in names):
        raise ValueError("Invalid photo name")
    dimensions = body["dimensions_mm"]
    if len(dimensions) != 3 or any(not math.isfinite(x) or not 0 < x <= 100000 for x in dimensions):
        raise ValueError("Measured dimensions are required")


def download(client, key, target, maximum):
    response = client.get_object(Bucket="tervory-rig", Key=key)
    stream = response["Body"]
    try:
        if response["ContentLength"] > maximum:
            raise ValueError("Photo exceeds job budget")
        size = 0
        with target.open("xb") as output:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise ValueError("Photo exceeds job budget")
                output.write(chunk)
    finally:
        stream.close()


def main(method):
    if method not in {"photogrammetry", "trellis2"}:
        raise ValueError("Unsupported GPU method")
    tenant, job = (str(uuid.UUID(os.environ[name])) for name in ("FORGE_TENANT_ID", "FORGE_JOB_ID"))
    prefix = f"forge/{tenant}/{job}/"
    if os.environ["FORGE_MANIFEST"] != prefix + "inputs/manifest.json":
        raise ValueError("Invalid manifest location")
    account = os.environ["R2_ACCOUNT_ID"]
    if not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ValueError("Invalid Rig storage account")
    client = boto3.client("s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID_RIG"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY_RIG"], region_name="auto",
        config=Config(connect_timeout=10, read_timeout=120, retries={"max_attempts": 2}))
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        manifest = work / "manifest.json"
        download(client, prefix + "inputs/manifest.json", manifest, 65536)
        body = json.loads(manifest.read_text())
        validate_manifest(body, tenant, job, method)
        photos = work / "photos"
        photos.mkdir()
        for name in body["inputs"]:
            download(client, prefix + "inputs/" + name, photos / name, 20_000_000)
        safe = {name: os.environ[name] for name in ("PATH", "LD_LIBRARY_PATH", "CUDA_HOME") if name in os.environ}
        safe.update(HOME=directory, TMPDIR=directory, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                    HF_HUB_DISABLE_TELEMETRY="1", PYTHONPATH="/opt/trellis2", OMP_NUM_THREADS="4",
                    OPENCV_IO_ENABLE_OPENEXR="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
        subprocess.run([sys.executable, str(Path(__file__).with_name("reconstruct.py")), method, directory],
            env=safe, check=True, timeout=body["timeout_seconds"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        outputs = work / "outputs"
        for path in sorted(outputs.iterdir()):
            if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}", path.name):
                raise ValueError("Invalid output artifact")
            if path.stat().st_size > 256_000_000:
                raise ValueError("GPU output exceeds ingestion budget")
            with path.open("rb") as content:
                client.put_object(Bucket="tervory-rig", Key=prefix + "gpu/" + path.name, Body=content,
                                  Metadata={"approval": "draft"})
        if not (outputs / "result.glb").is_file():
            raise ValueError("GPU job produced no model")


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception:
        # Provider errors may contain credentials or signed URLs: never print them.
        print("Forge GPU reconstruction failed. No model was approved.", file=sys.stderr)
        sys.exit(1)
