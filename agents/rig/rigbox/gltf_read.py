"""Read a binary glTF (.glb). Never builds a mesh the file does not contain."""

from __future__ import annotations

import json
import struct
from typing import Any

_JSON = 0x4E4F534A
_BIN = 0x004E4942


def parse_glb(data: bytes) -> dict[str, Any]:
    """Return mounts, materials, and the file's own bounds. No new geometry."""
    document, _blob = _document(data)
    nodes = list(document.get("nodes") or [])
    if not isinstance(nodes, list):
        raise ValueError("not a glb file")
    worlds = _worlds(nodes)
    mounts = _mounts(nodes, worlds)
    materials = _materials(document)
    polycount = _polycount(document)
    extent = _extent(document, nodes, worlds)
    return {
        "mounts": mounts,
        "attach": _attach(nodes, worlds),
        "materials": materials,
        "polycount": polycount,
        "extent_m": extent,
        "clearance_mm": _body_clearance(document, nodes),
        "pbr": any(item["pbr"] for item in materials),
        "unit": _unit(document),
        "measured": "not checked",
    }


def _document(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) < 12 or data[:4] != b"glTF":
        raise ValueError("not a glb file")
    _magic, version, length = struct.unpack_from("<4sII", data, 0)
    if version != 2 or length != len(data):
        raise ValueError("not a glb file")
    offset = 12
    document: dict[str, Any] | None = None
    blob = b""
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        if chunk_length < 0 or offset + chunk_length > len(data):
            raise ValueError("not a glb file")
        chunk = data[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == _JSON:
            document = json.loads(chunk.decode("utf-8").strip())
        elif chunk_type == _BIN:
            blob = chunk
    if not isinstance(document, dict) or str((document.get("asset") or {}).get("version") or "")[:1] != "2":
        raise ValueError("not a glb file")
    return document, blob


def _unit(document: dict[str, Any]) -> str:
    extras = document.get("asset", {}).get("extras") if isinstance(document.get("asset"), dict) else None
    if isinstance(extras, dict):
        declared = str(extras.get("unit") or "").strip().lower()
        if declared in {"mm", "millimetre", "millimeter", "millimetres", "millimeters"}:
            return "mm"
        if declared in {"m", "metre", "meter", "metres", "meters"}:
            return "m"
    return "m"


def _local(node: dict[str, Any]) -> list[float]:
    matrix = node.get("matrix")
    if isinstance(matrix, list) and len(matrix) == 16:
        return [float(item) for item in matrix]
    translation = _vec3(node.get("translation")) or [0.0, 0.0, 0.0]
    rotation = _quat(node.get("rotation")) or [0.0, 0.0, 0.0, 1.0]
    scale = _vec3(node.get("scale")) or [1.0, 1.0, 1.0]
    return _trs(translation, rotation, scale)


def _trs(translation: list[float], rotation: list[float], scale: list[float]) -> list[float]:
    matrix = _quat_matrix(rotation)
    matrix[0] *= scale[0]
    matrix[1] *= scale[0]
    matrix[2] *= scale[0]
    matrix[4] *= scale[1]
    matrix[5] *= scale[1]
    matrix[6] *= scale[1]
    matrix[8] *= scale[2]
    matrix[9] *= scale[2]
    matrix[10] *= scale[2]
    matrix[12] = translation[0]
    matrix[13] = translation[1]
    matrix[14] = translation[2]
    return matrix


def _quat_matrix(rotation: list[float]) -> list[float]:
    x, y, z, w = rotation
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    return [
        1.0 - (yy + zz), xy + wz, xz - wy, 0.0,
        xy - wz, 1.0 - (xx + zz), yz + wx, 0.0,
        xz + wy, yz - wx, 1.0 - (xx + yy), 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def multiply(left: list[float], right: list[float]) -> list[float]:
    out = [0.0] * 16
    for column in range(4):
        for row in range(4):
            out[column * 4 + row] = sum(
                left[k * 4 + row] * right[column * 4 + k] for k in range(4)
            )
    return out


def _worlds(nodes: list[Any]) -> list[list[float]]:
    parents: dict[int, int] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        for child in node.get("children") or []:
            if isinstance(child, int):
                parents[child] = index
    cache: dict[int, list[float]] = {}

    def world(index: int, trail: set[int]) -> list[float]:
        if index in cache:
            return cache[index]
        if index in trail or index < 0 or index >= len(nodes) or not isinstance(nodes[index], dict):
            return _identity()
        local = _local(nodes[index])
        parent = parents.get(index)
        if parent is None:
            cache[index] = local
            return local
        cache[index] = multiply(world(parent, trail | {index}), local)
        return cache[index]

    return [world(index, set()) for index in range(len(nodes))]


def _mounts(nodes: list[Any], worlds: list[list[float]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        role = _mount_role(node)
        if not role:
            continue
        matrix = worlds[index]
        found.append(
            {
                "role": role,
                "name": str(node.get("name") or role),
                "translation_m": [round(matrix[12], 6), round(matrix[13], 6), round(matrix[14], 6)],
                "matrix": [round(value, 6) for value in matrix],
                "clearance_mm": _clearance((node.get("extras") or {}).get("mount") if isinstance(node.get("extras"), dict) else None),
            }
        )
    return found


def _mount_role(node: dict[str, Any]) -> str:
    extras = node.get("extras") if isinstance(node.get("extras"), dict) else {}
    mount = extras.get("mount") if isinstance(extras, dict) else None
    if isinstance(mount, dict) and str(mount.get("role") or "").strip():
        return str(mount["role"]).strip().lower()
    name = str(node.get("name") or "").strip()
    lowered = name.lower()
    for prefix in ("mount/", "mount.", "mount_"):
        if lowered.startswith(prefix) and len(name) > len(prefix):
            return lowered[len(prefix) :]
    return ""


def _attach(nodes: list[Any], worlds: list[list[float]]) -> dict[str, Any] | None:
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        if str(node.get("name") or "").strip().lower() != "attach":
            continue
        matrix = worlds[index]
        return {
            "name": "attach",
            "matrix": [round(value, 6) for value in matrix],
        }
    return None


def _materials(document: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for material in document.get("materials") or []:
        if not isinstance(material, dict):
            continue
        pbr = material.get("pbrMetallicRoughness")
        pbr = pbr if isinstance(pbr, dict) else {}
        found.append(
            {
                "name": str(material.get("name") or ""),
                "pbr": "pbrMetallicRoughness" in material,
                "base_color": pbr.get("baseColorFactor"),
                "metallic": pbr.get("metallicFactor"),
                "roughness": pbr.get("roughnessFactor"),
                "base_color_texture": isinstance(pbr.get("baseColorTexture"), dict),
            }
        )
    return found


def _polycount(document: dict[str, Any]) -> int:
    accessors = document.get("accessors") or []
    total = 0
    for mesh in document.get("meshes") or []:
        if not isinstance(mesh, dict):
            continue
        for primitive in mesh.get("primitives") or []:
            if not isinstance(primitive, dict):
                continue
            indices = primitive.get("indices")
            if isinstance(indices, int) and 0 <= indices < len(accessors):
                count = accessors[indices].get("count") if isinstance(accessors[indices], dict) else None
                if isinstance(count, int):
                    total += count // 3
                    continue
            attributes = primitive.get("attributes") if isinstance(primitive.get("attributes"), dict) else {}
            position = attributes.get("POSITION")
            if isinstance(position, int) and 0 <= position < len(accessors):
                count = accessors[position].get("count") if isinstance(accessors[position], dict) else None
                if isinstance(count, int):
                    total += count // 3
    return total


def _extent(
    document: dict[str, Any], nodes: list[Any], worlds: list[list[float]]
) -> dict[str, list[float]] | None:
    meshes = document.get("meshes") or []
    accessors = document.get("accessors") or []
    points: list[tuple[float, float, float]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not isinstance(node.get("mesh"), int):
            continue
        mesh_index = node["mesh"]
        if mesh_index < 0 or mesh_index >= len(meshes) or not isinstance(meshes[mesh_index], dict):
            continue
        for primitive in meshes[mesh_index].get("primitives") or []:
            if not isinstance(primitive, dict):
                continue
            attributes = primitive.get("attributes") if isinstance(primitive.get("attributes"), dict) else {}
            position = attributes.get("POSITION")
            if not isinstance(position, int) or position < 0 or position >= len(accessors):
                continue
            accessor = accessors[position]
            if not isinstance(accessor, dict):
                continue
            low = _vec3(accessor.get("min"))
            high = _vec3(accessor.get("max"))
            if low is None or high is None:
                continue
            for corner in _corners(low, high):
                points.append(_transform_point(worlds[index], corner))
    if not points:
        return None
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "min": [round(value, 6) for value in minimum],
        "max": [round(value, 6) for value in maximum],
    }


def _body_clearance(document: dict[str, Any], nodes: list[Any]) -> list[float] | None:
    scenes = document.get("scenes") or []
    scene_index = document.get("scene") if isinstance(document.get("scene"), int) else 0
    if isinstance(scene_index, int) and 0 <= scene_index < len(scenes) and isinstance(scenes[scene_index], dict):
        found = _clearance_box(scenes[scene_index].get("extras"))
        if found is not None:
            return found
    for node in nodes:
        if not isinstance(node, dict) or _mount_role(node):
            continue
        found = _clearance_box(node.get("extras"))
        if found is not None:
            return found
    return None


def _clearance(mount: Any) -> list[float] | None:
    if not isinstance(mount, dict):
        return None
    return _vec3(mount.get("clearance_mm"))


def _clearance_box(extras: Any) -> list[float] | None:
    if not isinstance(extras, dict):
        return None
    return _vec3(extras.get("clearance_mm"))


def _corners(low: list[float], high: list[float]) -> list[tuple[float, float, float]]:
    return [
        (low[0], low[1], low[2]),
        (low[0], low[1], high[2]),
        (low[0], high[1], low[2]),
        (low[0], high[1], high[2]),
        (high[0], low[1], low[2]),
        (high[0], low[1], high[2]),
        (high[0], high[1], low[2]),
        (high[0], high[1], high[2]),
    ]


def _transform_point(matrix: list[float], point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
    )


def _vec3(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _quat(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _identity() -> list[float]:
    return [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
