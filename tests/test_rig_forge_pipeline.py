"""Required by the forge-image CI job; exercise every real CPU executable."""
import json
import os
import shutil
import struct
from pathlib import Path

import pytest
import trimesh

from agents.rig.forge.model_check import Budget
from agents.rig.forge.pipeline import StageFailed, run

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not shutil.which("blender"), reason="Runs in required forge-image CI job")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["ai-sample.glb", "scan.obj"])
async def test_neutral_samples_pass_all_real_tools(tmp_path, name):
    source = tmp_path / name
    shutil.copyfile(ROOT / "tests/fixtures/rig_forge_models" / name, source)
    steps = []
    async def receipt(stage, outcome):
        steps.append((stage, outcome))
    report = await run(source, tmp_path, unit_mm=1000 if name.endswith(".glb") else 1, dimensions_mm=(20, 30, 40), budget=Budget(), receipt=receipt)
    assert report["passed"] and report["status"] == "draft" and all(report["checks"].values())
    assert report["bytes"] < 8_000_000 and report["triangles"] <= 100_000
    assert steps[-1] == ("validate", "delivered")
    assert {step for step, status in steps if status == "delivered"} >= {
        "blender", "dedup", "simplify", "meshopt", "gltfpack", "ktx2", "model_check", "validate"}
    validation = json.loads((tmp_path / "validation.json").read_text())
    assert validation["issues"]["numErrors"] == 0
    glb = (tmp_path / "draft.glb").read_bytes()
    length = struct.unpack_from("<I", glb, 12)[0]
    document = json.loads(glb[20:20 + length])
    assert "EXT_meshopt_compression" in document["extensionsUsed"]
    assert any(image["mimeType"] == "image/ktx2" for image in document["images"])


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["hole", "inside_out"])
async def test_defective_scan_stops_before_conversion(tmp_path, defect):
    mesh = trimesh.creation.box(extents=(20, 30, 40))
    if defect == "hole":
        mesh.update_faces(list(range(len(mesh.faces) - 1)))
    else:
        mesh.invert()
    source = tmp_path / "bad.obj"
    mesh.export(source)
    steps = []
    async def receipt(stage, outcome):
        steps.append((stage, outcome))
    with pytest.raises(StageFailed, match="preflight"):
        await run(source, tmp_path, unit_mm=1, dimensions_mm=(20, 30, 40), budget=Budget(), receipt=receipt)
    assert steps == [("preflight", "failed")]
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["reasons"] and report["status"] == "rejected"
    assert not (tmp_path / "draft.glb").exists()


@pytest.mark.asyncio
async def test_receipt_delivery_failure_prevents_next_step(tmp_path):
    source = tmp_path / "scan.obj"
    shutil.copyfile(ROOT / "tests/fixtures/rig_forge_models/scan.obj", source)
    async def receipt(stage, outcome):
        raise RuntimeError("receipt service unavailable")
    with pytest.raises(RuntimeError, match="receipt service"):
        await run(source, tmp_path, unit_mm=1, dimensions_mm=(20, 30, 40), budget=Budget(), receipt=receipt)
    assert not (tmp_path / "blender.glb").exists()


def test_image_environment_never_contains_tank_credentials():
    if os.environ.get("RIG_FORGE_TOOL_ROOT"):
        assert not any(os.environ.get(k) for k in ("TANK_KEY", "TANK_KEY_RIG", "TANK_API_KEY"))
