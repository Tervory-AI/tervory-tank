"""OpenCascade STEP/IGES tessellation in millimetres; no UI or FreeCAD process."""
from __future__ import annotations

from pathlib import Path

from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.IGESControl import IGESControl_Reader
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


def convert(source: Path, destination: Path) -> None:
    """Preserve CAD face orientation. Reject a file without transferable shapes."""
    suffix = source.suffix.lower()
    if suffix in {".step", ".stp"}:
        reader = STEPControl_Reader()
        Interface_Static.SetCVal_s("xstep.cascade.unit", "MM")
    elif suffix in {".iges", ".igs"}:
        reader = IGESControl_Reader()
        Interface_Static.SetCVal_s("xstep.cascade.unit", "MM")
    else:
        raise ValueError("Only STEP and IGES are CAD inputs.")
    if reader.ReadFile(str(source)) != IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError("CAD input contains no transferable shape.")
    shape = reader.OneShape()
    mesher = BRepMesh_IncrementalMesh(shape, 0.1, False, 0.2, False)
    if not mesher.IsDone():
        raise ValueError("CAD tessellation failed.")
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    vertices, faces = [], []
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        triangles = BRep_Tool.Triangulation_s(face, location)
        if triangles is None:
            raise ValueError("CAD face could not be tessellated.")
        offset = len(vertices)
        for index in range(1, triangles.NbNodes() + 1):
            point = triangles.Node(index).Transformed(location.Transformation())
            vertices.append((point.X(), point.Y(), point.Z()))
        for index in range(1, triangles.NbTriangles() + 1):
            a, b, c = triangles.Triangle(index).Get()
            if face.Orientation() == TopAbs_REVERSED:
                b, c = c, b
            faces.append((a + offset, b + offset, c + offset))
        explorer.Next()
    if not faces:
        raise ValueError("CAD input has no faces.")
    with destination.open("w") as output:
        output.write("# Neutral geometry; coordinates in millimetres.\n")
        for point in vertices:
            output.write("v %s %s %s\n" % point)
        for face in faces:
            output.write("f %d %d %d\n" % face)
