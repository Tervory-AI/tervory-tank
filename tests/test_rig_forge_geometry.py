"""Real CAD/mesh dependencies: reject defects rather than repairing the evidence."""
import numpy as np
import pytest
import trimesh

from agents.rig.forge.cad import convert
from agents.rig.forge.model_check import Budget, check


def save(tmp_path, mesh, extension="obj"):
    path = tmp_path / ("sample." + extension)
    mesh.export(path)
    return path


def test_step_to_mesh_preserves_millimetres_and_outward_faces(tmp_path):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    source, target = tmp_path / "block.step", tmp_path / "block.obj"
    writer = STEPControl_Writer()
    writer.Transfer(BRepPrimAPI_MakeBox(20, 30, 40).Shape(), STEPControl_AsIs)
    assert writer.Write(str(source)) == IFSelect_RetDone
    convert(source, target)
    report = check(target, unit_mm=1, expected_mm=(20, 30, 40))
    assert report["passed"], report
    assert report["status"] == "draft" and report["triangles"] == 12


def test_scan_roundtrip_glb_is_draft_and_uses_metres(tmp_path):
    scan = trimesh.creation.box(extents=(20, 30, 40))
    assert check(save(tmp_path, scan), unit_mm=1, expected_mm=(20, 30, 40))["passed"]
    scan.apply_scale(0.001)
    report = check(save(tmp_path, scan, "glb"), unit_mm=1000, expected_mm=(20, 30, 40))
    assert report["passed"] and report["status"] == "draft"


@pytest.mark.parametrize("defect,failed_check", [("inside_out", "outward"), ("hole", "watertight"),
                                                ("small_inverted_part", "outward")])
def test_bad_scans_are_rejected_with_a_reason(tmp_path, defect, failed_check):
    mesh = trimesh.creation.box(extents=(20, 30, 40))
    if defect == "inside_out":
        mesh.invert()
    elif defect == "hole":
        mesh.update_faces(np.arange(len(mesh.faces) - 1))
    else:
        # The aggregate volume is positive; testing total volume alone misses it.
        part = trimesh.creation.box(extents=(1, 1, 1))
        part.apply_translation((15, 0, 0))
        part.invert()
        mesh = trimesh.util.concatenate([mesh, part])
        assert mesh.volume > 0
    report = check(save(tmp_path, mesh), unit_mm=1, expected_mm=(20, 30, 40))
    assert not report["passed"] and not report["checks"][failed_check]
    assert report["status"] == "rejected" and report["reasons"]


def test_scale_and_size_budget_are_enforced(tmp_path):
    path = save(tmp_path, trimesh.creation.box(extents=(20, 30, 40)))
    wrong_size = check(path, unit_mm=1000, expected_mm=(20, 30, 40))
    assert not wrong_size["checks"]["dimensions"]
    for budget in (Budget(triangles=11), Budget(bytes=10)):
        report = check(path, unit_mm=1, expected_mm=(20, 30, 40), budget=budget)
        assert not report["checks"]["budget"] and not report["passed"]


def test_invalid_cad_is_rejected(tmp_path):
    path = tmp_path / "bad.step"
    path.write_text("invalid")
    with pytest.raises(ValueError, match="no transferable"):
        convert(path, tmp_path / "unused.obj")
