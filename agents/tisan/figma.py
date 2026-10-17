"""Read one Figma page into tokens, a Tailwind theme, and a component manifest.

Colour, type, and space values become CSS custom properties. A value that
disagrees with itself is listed and left out. A state the component does not
have is listed and not invented.

The room has no path to the public internet, so this reader does not call
Figma. It reads the recorded fixture for the Tervory file and no other file.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

TERVORY_FILE_KEY = "ksi7ctRwEnN8wbip1yfuhL"
TERVORY_PAGE_ID = "0:1"

_FILE_KEY = re.compile(r"^[0-9A-Za-z]{22,128}$")
_NODE_ID = re.compile(r"^\d+:\d+$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")
_FAMILY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .+-]{0,60}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Interactive components, from the Tisan build spec. Anything else has no required states.
_ROLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("text field", ("empty", "filled", "error", "success")),
    ("checkbox", ("hover", "disabled")),
    ("button", ("hover", "active", "disabled", "error")),
    ("switch", ("hover", "disabled")),
    ("input", ("empty", "filled", "error", "success")),
    ("field", ("empty", "filled", "error", "success")),
    ("link", ("hover", "active")),
)
_STATE_AXES = {"state", "states"}
_TYPE_SCALE = ("h1", "h2", "h3", "h4", "h5", "h6", "body", "caption", "label")
_TYPE_FIELDS = ("family", "line_height", "weight")
_BLOCKING = {
    "conflicts",
    "inconsistent_box",
    "inconsistent_space",
    "missing_space",
    "missing_states",
    "missing_type_fields",
    "missing_type_scale",
    "partial_frame",
    "token_name",
    "unclassified",
    "unmeasured",
    "unparsed_variant",
    "unresolved_alias",
    "variables_unavailable",
}
_SEPARATORS = ("/", " /", " \u2014", " \u2013", " -")


class FigmaError(ValueError):
    """The page cannot be read safely."""


def fixture_path() -> Path:
    raw = os.environ.get("TISAN_FIGMA_FIXTURE", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent / "fixtures" / "tervory-landing.json"


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FigmaError(f"{field} must be text")
    return value.strip()


def normalise_node_id(value: Any, *, default: str = TERVORY_PAGE_ID) -> str:
    if value is None or value == "":
        value = default
    text = _text(value, "node_id").replace("-", ":", 1)
    if _NODE_ID.fullmatch(text) is None:
        raise FigmaError("node_id must look like 0:1")
    return text


def normalise_file_key(value: Any) -> str:
    if value is None or value == "":
        value = TERVORY_FILE_KEY
    text = _text(value, "file_key")
    if _FILE_KEY.fullmatch(text) is None:
        raise FigmaError("file_key is not a Figma file key")
    return text


def _tenant(tenant_id: str) -> str:
    if not isinstance(tenant_id, str) or _TENANT.fullmatch(tenant_id) is None:
        raise FigmaError("tenant_id is not a safe directory name")
    return tenant_id


def _slug(value: str) -> str:
    cleaned = value.strip().lower().replace("/", "-").replace(" ", "-")
    cleaned = re.sub(r"[^a-z0-9-]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    if _SLUG.fullmatch(cleaned) is None:
        return ""
    return cleaned


def _number(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return None
        value = float(text)
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def _channel(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 1:
        return None
    return max(0, min(255, round(number * 255)))


def _hex(colour: dict[str, Any]) -> str | None:
    red, green, blue = _channel(colour.get("r")), _channel(colour.get("g")), _channel(colour.get("b"))
    if red is None or green is None or blue is None:
        return None
    alpha = colour.get("a", 1)
    if alpha is None:
        alpha = 1
    alpha_channel = _channel(alpha)
    if alpha_channel is None:
        return None
    if alpha_channel >= 255:
        return f"#{red:02x}{green:02x}{blue:02x}"
    return f"#{red:02x}{green:02x}{blue:02x}{alpha_channel:02x}"


def _canonical(value: str) -> str:
    text = value.strip()
    if _HEX.fullmatch(text):
        return text.lower()
    number = _number(text)
    if number is not None and re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return number
    return text


def _resolve(raw: Any, mode_id: str, variables: dict[str, Any], seen: set[str]) -> tuple[str | None, str | None]:
    if isinstance(raw, dict) and raw.get("type") == "VARIABLE_ALIAS":
        target_id = str(raw.get("id") or "")
        if not target_id or target_id in seen or not isinstance(variables.get(target_id), dict):
            return None, "unresolved_alias"
        target = variables[target_id]
        nxt = (target.get("valuesByMode") or {}).get(mode_id)
        return _resolve(nxt, mode_id, variables, seen | {target_id})
    if isinstance(raw, dict) and {"r", "g", "b"} <= set(raw):
        text = _hex(raw)
        if text is None:
            return None, "unclassified"
        return text, None
    if isinstance(raw, str):
        text = raw.strip()
        if not text or len(text) > 80:
            return None, "unclassified"
        return text, None
    number = _number(raw)
    if number is None:
        return None, "unclassified"
    return number, None


def _mode_names(collections: dict[str, Any]) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for collection in collections.values():
        if not isinstance(collection, dict):
            continue
        collection_name = str(collection.get("name") or "")
        for mode in collection.get("modes") or []:
            if not isinstance(mode, dict):
                continue
            mode_id = str(mode.get("modeId") or "")
            mode_name = str(mode.get("name") or mode_id)
            if mode_id:
                found[mode_id] = (collection_name, mode_name)
    return found


def variables_from_rest(payload: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Return variable rows, gaps, and whether collection names were present."""
    if not payload:
        return [], [{"kind": "variables_unavailable"}], False
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else payload
    if not isinstance(meta, dict):
        return [], [{"kind": "variables_unavailable"}], False
    collections = meta.get("variableCollections") if isinstance(meta.get("variableCollections"), dict) else {}
    raw_variables = meta.get("variables") if isinstance(meta.get("variables"), dict) else {}
    modes = _mode_names(collections)
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for variable in raw_variables.values():
        if not isinstance(variable, dict) or not isinstance(variable.get("name"), str):
            continue
        values: list[dict[str, str]] = []
        for mode_id, raw in (variable.get("valuesByMode") or {}).items():
            collection_name, mode_name = modes.get(str(mode_id), ("", str(mode_id)))
            scope = f"{collection_name} / {mode_name}" if collection_name else mode_name
            resolved, problem = _resolve(raw, str(mode_id), raw_variables, set())
            if problem or resolved is None:
                gaps.append({"kind": problem or "unclassified", "name": variable["name"], "scope": scope})
                continue
            values.append({"scope": scope, "value": resolved})
        if values:
            rows.append({"name": variable["name"], "values": values})
    known = any(isinstance(item, dict) and item.get("name") for item in collections.values())
    return rows, gaps, known


def _length(value: Any) -> int | float | None:
    text = _number(value)
    if text is None or text.startswith("-"):
        return None
    number = float(text)
    if number.is_integer():
        return int(number)
    return number


def _box(node: dict[str, Any]) -> tuple[int | float | None, int | float | None]:
    box = node.get("absoluteBoundingBox")
    if not isinstance(box, dict):
        box = node.get("size") if isinstance(node.get("size"), dict) else {}
    return _length(box.get("width")), _length(box.get("height"))


def _variant_properties(node: dict[str, Any]) -> dict[str, str]:
    raw = node.get("componentProperties")
    if isinstance(raw, dict):
        found: dict[str, str] = {}
        for key, spec in raw.items():
            if isinstance(spec, dict) and spec.get("type") == "VARIANT" and isinstance(spec.get("value"), str):
                found[str(key)] = spec["value"]
        if found:
            return found
    return _properties_from_name(str(node.get("name") or ""))


def _properties_from_name(name: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in (piece.strip() for piece in name.split(",")):
        if "=" not in part:
            return {}
        key, value = part.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            return {}
        found[key] = value
    return found


def _push_component(components: list[dict[str, Any]], node: dict[str, Any], variants: list[dict[str, Any]]) -> None:
    definitions = node.get("componentPropertyDefinitions")
    if isinstance(definitions, dict):
        for key, spec in definitions.items():
            if not isinstance(spec, dict) or spec.get("type") != "VARIANT":
                continue
            options = [str(item) for item in spec.get("variantOptions") or [] if isinstance(item, str)]
            have = {item["properties"].get(str(key)) for item in variants}
            for option in options:
                if option not in have:
                    variants.append(
                        {
                            "id": "",
                            "name": f"{key}={option}",
                            "properties": {str(key): option},
                            "width": None,
                            "height": None,
                        }
                    )
    components.append({"id": str(node.get("id") or ""), "name": str(node.get("name") or ""), "variants": variants})


def _walk_document(
    node: dict[str, Any],
    *,
    page_frame: dict[str, str] | None,
    section: str,
    frames: list[dict[str, str]],
    components: list[dict[str, Any]],
    uses: list[dict[str, str]],
) -> None:
    kind = node.get("type")
    name = str(node.get("name") or "")
    node_id = str(node.get("id") or "")
    if kind == "COMPONENT_SET":
        variants = []
        for child in node.get("children") or []:
            if isinstance(child, dict) and child.get("type") == "COMPONENT":
                width, height = _box(child)
                variants.append(
                    {
                        "id": str(child.get("id") or ""),
                        "name": str(child.get("name") or ""),
                        "properties": _variant_properties(child),
                        "width": width,
                        "height": height,
                    }
                )
        _push_component(components, node, variants)
        return
    if kind == "COMPONENT":
        width, height = _box(node)
        components.append(
            {
                "id": node_id,
                "name": name,
                "variants": [],
                "width": width,
                "height": height,
            }
        )
        return
    if kind == "INSTANCE":
        uses.append(
            {
                "id": node_id,
                "name": name,
                "page": page_frame["name"] if page_frame else "",
                "section": section,
            }
        )
        return
    children = [child for child in node.get("children") or [] if isinstance(child, dict)]
    if kind == "CANVAS":
        for child in children:
            child_id = str(child.get("id") or "")
            child_name = str(child.get("name") or "")
            if child.get("type") == "FRAME":
                frames.append({"id": child_id, "name": child_name})
            _walk_document(
                child,
                page_frame={"id": child_id, "name": child_name} if child.get("type") == "FRAME" else None,
                section="",
                frames=frames,
                components=components,
                uses=uses,
            )
        return
    current_section = section
    if kind == "FRAME" and page_frame is not None and page_frame.get("id") != node_id and not section:
        current_section = name
    for child in children:
        _walk_document(
            child,
            page_frame=page_frame,
            section=current_section,
            frames=frames,
            components=components,
            uses=uses,
        )


def components_from_document(document: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]]:
    page = {"id": str(document.get("id") or ""), "name": str(document.get("name") or "")}
    frames: list[dict[str, str]] = []
    components: list[dict[str, Any]] = []
    uses: list[dict[str, str]] = []
    if document.get("type") == "CANVAS":
        _walk_document(
            document,
            page_frame=None,
            section="",
            frames=frames,
            components=components,
            uses=uses,
        )
    else:
        _walk_document(
            document,
            page_frame={"id": page["id"], "name": page["name"]} if document.get("type") == "FRAME" else None,
            section="",
            frames=frames,
            components=components,
            uses=uses,
        )
        if document.get("type") == "FRAME":
            frames = [{"id": page["id"], "name": page["name"]}]
    return page, frames, components, uses


def _document_from_nodes(payload: dict[str, Any], node_id: str) -> tuple[dict[str, Any], str | None]:
    if isinstance(payload.get("document"), dict) and "nodes" not in payload:
        return payload["document"], payload.get("name") if isinstance(payload.get("name"), str) else None
    nodes = payload.get("nodes")
    if not isinstance(nodes, dict):
        raise FigmaError("Figma did not return that node")
    node = nodes.get(node_id)
    if not isinstance(node, dict) or not isinstance(node.get("document"), dict):
        raise FigmaError("Figma did not return that node")
    name = payload.get("name") if isinstance(payload.get("name"), str) else None
    return node["document"], name


def normalise_rest(file_key: str, node_id: str, nodes_payload: dict[str, Any], variables_payload: dict[str, Any] | None) -> dict[str, Any]:
    document, file_name = _document_from_nodes(nodes_payload, node_id)
    page, frames, components, uses = components_from_document(document)
    if document.get("type") != "CANVAS":
        page = {"id": node_id, "name": str(document.get("name") or page.get("name") or "")}
    variables, gaps, known = variables_from_rest(variables_payload)
    node = page if node_id == page["id"] else {"id": node_id, "name": str(document.get("name") or "")}
    return {
        "file_key": file_key,
        "file_name": file_name,
        "source": "figma",
        "recorded_at": None,
        "note": None,
        "collections_known": known,
        "page": page if document.get("type") == "CANVAS" else node,
        "node": node if document.get("type") != "CANVAS" else page,
        "frames": frames,
        "variables": variables,
        "components": components,
        "uses": uses,
        "extra_gaps": gaps,
    }


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FigmaError(f"{field} must be an object")
    return value


def _frame_variables(frame: dict[str, Any]) -> dict[str, str]:
    raw = frame.get("variables")
    if not isinstance(raw, dict):
        raise FigmaError("a frame is missing its variables")
    values: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise FigmaError("a recorded variable is not text")
        values[key] = value.strip()
    return values


def normalise_fixture(payload: dict[str, Any], node_id: str) -> dict[str, Any]:
    if payload.get("schema") != "tisan.figma.fixture/1":
        raise FigmaError("the recorded fixture is not one this reader knows")
    file_key = normalise_file_key(payload.get("file_key"))
    page = _mapping(payload.get("page"), "page")
    page_id = normalise_node_id(page.get("id"), default="")
    page_name = _text(page.get("name"), "page.name")
    frames_in = payload.get("frames")
    components_in = payload.get("components")
    uses_in = payload.get("uses")
    if not isinstance(frames_in, list) or not isinstance(components_in, list) or not isinstance(uses_in, list):
        raise FigmaError("the recorded fixture is incomplete")
    frames = []
    variables: list[dict[str, Any]] = []
    by_name: dict[str, list[dict[str, str]]] = {}
    for frame in frames_in:
        item = _mapping(frame, "frame")
        frame_id = normalise_node_id(item.get("id"), default="")
        frame_name = _text(item.get("name"), "frame.name")
        frames.append({"id": frame_id, "name": frame_name})
        for name, value in _frame_variables(item).items():
            by_name.setdefault(name, []).append({"scope": frame_name, "value": value})
    components = []
    for component in components_in:
        item = _mapping(component, "component")
        name = _text(item.get("name"), "component.name")
        variants = []
        raw_variants = item.get("variants")
        if not isinstance(raw_variants, list):
            raise FigmaError("a component is missing its variants")
        for variant in raw_variants:
            row = _mapping(variant, "variant")
            variants.append(
                {
                    "id": _text(row.get("id"), "variant.id"),
                    "name": _text(row.get("name"), "variant.name"),
                    "properties": _properties_from_name(_text(row.get("name"), "variant.name")),
                    "width": row.get("width"),
                    "height": row.get("height"),
                }
            )
        if isinstance(item.get("variables"), dict):
            for var_name, value in item["variables"].items():
                if isinstance(var_name, str) and isinstance(value, str):
                    by_name.setdefault(var_name, []).append({"scope": f"component:{name}", "value": value.strip()})
        components.append(
            {
                "id": _text(item.get("id"), "component.id"),
                "name": name,
                "variants": variants,
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )
    uses = []
    for use in uses_in:
        row = _mapping(use, "use")
        uses.append(
            {
                "id": _text(row.get("id"), "use.id"),
                "name": _text(row.get("name"), "use.name"),
                "page": _text(row.get("page"), "use.page") if row.get("page") else "",
                "section": _text(row.get("section"), "use.section") if row.get("section") else "",
            }
        )
    for name, values in by_name.items():
        variables.append({"name": name, "values": values})
    node = {"id": page_id, "name": page_name}
    chosen = frames
    if node_id != page_id:
        chosen = [frame for frame in frames if frame["id"] == node_id]
        if not chosen:
            raise FigmaError("the recorded fixture has no node with that id")
        node = {"id": chosen[0]["id"], "name": chosen[0]["name"]}
        uses = [use for use in uses if use["page"] == chosen[0]["name"]]
        keep = {match_component(use["name"], [item["name"] for item in components]) for use in uses}
        components = [item for item in components if item["name"] in keep]
        chosen_names = {frame["name"] for frame in chosen}
        trimmed = []
        for variable in variables:
            values = [
                value
                for value in variable["values"]
                if value["scope"] in chosen_names or value["scope"].startswith("component:")
            ]
            if values:
                trimmed.append({"name": variable["name"], "values": values})
        variables = trimmed
    note = payload.get("note") if isinstance(payload.get("note"), str) else None
    return {
        "file_key": file_key,
        "file_name": payload.get("file_name") if isinstance(payload.get("file_name"), str) else None,
        "source": "fixture",
        "recorded_at": payload.get("recorded_at") if isinstance(payload.get("recorded_at"), str) else None,
        "note": note,
        "collections_known": False,
        "page": {"id": page_id, "name": page_name},
        "node": node,
        "frames": chosen,
        "variables": variables,
        "components": components,
        "uses": uses,
        "extra_gaps": [],
    }


def load_fixture(node_id: str) -> dict[str, Any]:
    path = fixture_path()
    if not path.is_file():
        raise FigmaError("the recorded Figma fixture is missing")
    return normalise_fixture(json.loads(path.read_text(encoding="utf-8")), node_id)


def _classify(name: str, value: str) -> tuple[str, str] | None:
    canonical = _canonical(value)
    if _HEX.fullmatch(canonical):
        return "colour", canonical
    if name.startswith("size/") or name.startswith("font-size/"):
        text = _px(canonical)
        return ("type", text) if text else None
    if name.startswith("space/") or name.startswith("spacing/"):
        text = _px(canonical)
        return ("space", text) if text else None
    if name.startswith("weight/") or name.startswith("font-weight/"):
        number = _number(canonical)
        return ("type", number) if number and not number.startswith("-") else None
    if name.startswith("family/") or name.startswith("font/"):
        if _FAMILY.fullmatch(canonical) is None:
            return None
        return "type", f'"{canonical}"'
    if name.startswith("line/") or name.startswith("leading/") or name.startswith("line-height/"):
        text = _px(canonical)
        return ("type", text) if text else None
    return None


def _px(value: str) -> str | None:
    number = value[:-2] if value.endswith("px") else value
    if _NUMBER.fullmatch(number) is None:
        return None
    text = _number(number)
    if text is None or text.startswith("-"):
        return None
    return f"{text}px"


def _css_name(bucket: str, name: str) -> str:
    if bucket == "space":
        rest = name.split("/", 1)[1] if "/" in name else name
        slug = _slug(rest)
        return f"--space-{slug}" if slug else ""
    slug = _slug(name)
    if not slug:
        return ""
    if bucket == "colour":
        return f"--colour-{slug}"
    return f"--type-{slug}"


def _token_key(bucket: str, name: str) -> str:
    if bucket == "space":
        rest = name.split("/", 1)[1] if "/" in name else name
        return _slug(rest)
    return _slug(name)


def _tailwind_place(tree: dict[str, Any], bucket: str, name: str, css_name: str) -> str | None:
    reference = f"var({css_name})"
    if bucket == "colour":
        head, _, tail = name.partition("/")
        group = tree.setdefault("colors", {})
        key_head, key_tail = _slug(head), _slug(tail) if tail else ""
        if not key_head:
            return "token_name"
        if key_tail:
            nested = group.setdefault(key_head, {})
            if not isinstance(nested, dict) or key_tail in nested:
                return "token_name"
            nested[key_tail] = reference
        else:
            if key_head in group:
                return "token_name"
            group[key_head] = reference
        return None
    table = {
        "size": "fontSize",
        "font-size": "fontSize",
        "weight": "fontWeight",
        "font-weight": "fontWeight",
        "family": "fontFamily",
        "font": "fontFamily",
        "line": "lineHeight",
        "leading": "lineHeight",
        "line-height": "lineHeight",
        "space": "spacing",
        "spacing": "spacing",
    }
    head, _, tail = name.partition("/")
    theme_key = table.get(head, "fontSize" if bucket == "type" else "spacing")
    leaf = _slug(tail or head)
    if not leaf:
        return "token_name"
    group = tree.setdefault(theme_key, {})
    if leaf in group:
        return "token_name"
    group[leaf] = reference
    return None


def _required_states(name: str) -> tuple[str, ...]:
    folded = name.casefold()
    for role, states in _ROLES:
        if folded == role or folded.startswith(role + " "):
            return states
    return ()


def match_component(instance_name: str, names: list[str]) -> str | None:
    best: str | None = None
    for name in names:
        if instance_name == name or any(instance_name.startswith(name + separator) for separator in _SEPARATORS):
            if best is None or len(name) > len(best):
                best = name
    return best


def _present_states(variants: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for variant in variants:
        properties = variant.get("properties") if isinstance(variant.get("properties"), dict) else {}
        for key, value in properties.items():
            if not isinstance(value, str):
                continue
            if str(key).casefold() in _STATE_AXES or value.casefold() in {"hover", "active", "disabled", "error", "empty", "filled", "success", "loading", "focus", "checked", "default"}:
                found.add(value.casefold())
    return found


def _component_manifest(components: list[dict[str, Any]], uses: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    names = [str(item.get("name") or "") for item in components]
    used: dict[str, set[str]] = {name: set() for name in names}
    gaps: list[dict[str, Any]] = []
    for use in uses:
        match = match_component(str(use.get("name") or ""), names)
        if match is None:
            gaps.append({"kind": "unmapped_instance", "name": use.get("name")})
            continue
        where = str(use.get("page") or "")
        section = str(use.get("section") or "")
        if section:
            where = f"{where} / {section}" if where else section
        if where:
            used[match].add(where)
    manifest = []
    for component in sorted(components, key=lambda item: str(item.get("name") or "")):
        name = str(component.get("name") or "")
        variants = [item for item in component.get("variants") or [] if isinstance(item, dict)]
        axes: dict[str, set[str]] = {}
        unparsed = False
        boxes = []
        for variant in variants:
            properties = variant.get("properties") if isinstance(variant.get("properties"), dict) else {}
            if not properties:
                properties = _properties_from_name(str(variant.get("name") or ""))
                variant["properties"] = properties
            if not properties and variant.get("name"):
                unparsed = True
            for key, value in properties.items():
                axes.setdefault(str(key), set()).add(str(value))
            if _length(variant.get("width")) is not None and _length(variant.get("height")) is not None:
                boxes.append(
                    {
                        "name": variant.get("name"),
                        "width": _length(variant.get("width")),
                        "height": _length(variant.get("height")),
                    }
                )
        if (
            not variants
            and _length(component.get("width")) is not None
            and _length(component.get("height")) is not None
        ):
            boxes.append(
                {
                    "name": name,
                    "width": _length(component.get("width")),
                    "height": _length(component.get("height")),
                }
            )
        if unparsed:
            gaps.append({"kind": "unparsed_variant", "component": name})
        present = _present_states(variants)
        missing = sorted(state for state in _required_states(name) if state not in present)
        if missing:
            gaps.append({"kind": "missing_states", "component": name, "states": missing})
        heights = {str(box["name"]): box["height"] for box in boxes}
        if len(variants) > 1 and len(boxes) == len(variants) and len(set(heights.values())) > 1:
            gaps.append(
                {
                    "kind": "inconsistent_box",
                    "component": name,
                    "heights": {key: heights[key] for key in sorted(heights)},
                }
            )
        code = "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", name) if part)
        manifest.append(
            {
                "figma_id": component.get("id"),
                "figma_name": name,
                "code_name": code,
                "location": f"components/ui/{code}.tsx",
                "variants": {key: sorted(values) for key, values in sorted(axes.items())},
                "states": sorted(present),
                "missing_states": missing,
                "used_in": sorted(used.get(name, set())),
                "boxes": sorted(boxes, key=lambda item: str(item["name"])),
            }
        )
    return manifest, gaps


def _render_map(value: dict[str, Any], indent: int) -> str:
    pad = "  " * indent
    if not value:
        return "{}"
    lines = ["{"]
    for key in sorted(value, key=str):
        child = value[key]
        rendered = _render_map(child, indent + 1) if isinstance(child, dict) else json.dumps(str(child))
        lines.append(f"{pad}  {json.dumps(str(key))}: {rendered},")
    lines.append(f"{pad}}}")
    return "\n".join(lines)


def render_css(tokens: list[dict[str, str]]) -> str:
    lines = [":root {"]
    for token in sorted(tokens, key=lambda item: item["css"]):
        lines.append(f"  {token['css']}: {token['value']};")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def render_tailwind(tree: dict[str, Any]) -> str:
    extend = {key: tree[key] for key in ("colors", "fontFamily", "fontSize", "fontWeight", "lineHeight", "spacing") if tree.get(key)}
    body = _render_map(extend, 2)
    return (
        'import type { Config } from "tailwindcss";\n\n'
        "const config: Config = {\n"
        '  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],\n'
        "  theme: {\n"
        "    extend: "
        + body
        + ",\n"
        "  },\n"
        "  plugins: [],\n"
        "};\n\n"
        "export default config;\n"
    )


def _space_gap(tokens: list[dict[str, str]]) -> dict[str, Any] | None:
    numbers = []
    for token in tokens:
        if token["bucket"] != "space":
            continue
        if not token["value"].endswith("px"):
            return {"kind": "inconsistent_space", "detail": "A space token is not in px."}
        numbers.append(float(token["value"][:-2]))
    if not numbers:
        return None

    def fits(base: int) -> bool:
        return all(abs((number / base) - round(number / base)) < 1e-6 for number in numbers)

    if fits(4) or fits(8):
        return None
    shown = [int(number) if number.is_integer() else number for number in sorted(numbers)]
    return {"kind": "inconsistent_space", "values": shown}


def compile_reading(source: dict[str, Any]) -> dict[str, Any]:
    gaps = [dict(item) for item in source.get("extra_gaps") or []]
    if source.get("source") == "fixture" and not source.get("collections_known"):
        gaps.append({"kind": "source", "detail": "The recording has variable values and no collection names."})
    grouped: dict[str, dict[str, set[str]]] = {}
    for variable in source.get("variables") or []:
        name = str(variable.get("name") or "")
        for item in variable.get("values") or []:
            scope = str(item.get("scope") or "")
            grouped.setdefault(name, {}).setdefault(scope, set()).add(_canonical(str(item.get("value") or "")))
    conflicts = []
    emitted: list[dict[str, str]] = []
    theme: dict[str, Any] = {}
    frame_names = [str(frame.get("name") or "") for frame in source.get("frames") or []]
    seen_css: dict[str, str] = {}
    for name in sorted(grouped):
        scopes = grouped[name]
        distinct = {value for values in scopes.values() for value in values if value}
        listed = [
            {"scope": scope, "value": value}
            for scope, values in sorted(scopes.items())
            for value in sorted(values)
            if value
        ]
        if any(len(values) != 1 for values in scopes.values()) or len(distinct) != 1:
            conflicts.append({"name": name, "values": listed})
            continue
        value = next(iter(distinct))
        classified = _classify(name, value)
        if classified is None:
            gaps.append({"kind": "unclassified", "name": name, "value": value})
            continue
        bucket, css_value = classified
        css_name = _css_name(bucket, name)
        key = _token_key(bucket, name)
        if not css_name or not key:
            gaps.append({"kind": "token_name", "name": name})
            continue
        previous = seen_css.get(css_name)
        if previous is not None and previous != css_value:
            conflicts.append({"name": name, "values": [{"scope": css_name, "value": previous}, {"scope": css_name, "value": css_value}]})
            continue
        if previous is not None:
            gaps.append({"kind": "token_name", "name": name, "css": css_name})
            continue
        if _tailwind_place(theme, bucket, name, css_name):
            gaps.append({"kind": "token_name", "name": name, "css": css_name})
            continue
        seen_css[css_name] = css_value
        emitted.append({"bucket": bucket, "name": name, "key": key, "css": css_name, "value": css_value})
        if frame_names and any(scope in frame_names for scope in scopes):
            absent = [frame for frame in frame_names if frame not in scopes]
            if absent:
                gaps.append(
                    {
                        "kind": "partial_frame",
                        "name": name,
                        "present_on": [frame for frame in frame_names if frame in scopes],
                        "absent_on": absent,
                    }
                )
    space_gap = _space_gap(emitted)
    if space_gap:
        gaps.append(space_gap)
    if not any(token["bucket"] == "space" for token in emitted) and not any(item["name"].startswith(("space/", "spacing/")) for item in conflicts):
        gaps.append({"kind": "missing_space", "detail": "No spacing variables on this page."})
    size_names = {token["name"].split("/", 1)[1] for token in emitted if token["name"].startswith("size/")}
    missing_scale = [name for name in _TYPE_SCALE if name not in size_names]
    if missing_scale:
        gaps.append({"kind": "missing_type_scale", "names": missing_scale})
    variable_names = set(grouped)
    missing_fields = []
    prefixes = {
        "family": ("family/", "font/"),
        "weight": ("weight/", "font-weight/"),
        "line_height": ("line/", "leading/", "line-height/"),
    }
    for field in _TYPE_FIELDS:
        if not any(name.startswith(prefixes[field]) for name in variable_names):
            missing_fields.append(field)
    if missing_fields and any(token["bucket"] == "type" for token in emitted):
        gaps.append({"kind": "missing_type_fields", "fields": missing_fields})
    manifest, component_gaps = _component_manifest(list(source.get("components") or []), list(source.get("uses") or []))
    gaps.extend(component_gaps)
    tokens = {
        "colour": {token["key"]: token["value"] for token in emitted if token["bucket"] == "colour"},
        "type": {token["key"]: token["value"] for token in emitted if token["bucket"] == "type"},
        "space": {token["key"]: token["value"] for token in emitted if token["bucket"] == "space"},
    }
    blocked = sorted({item["kind"] for item in gaps if item["kind"] in _BLOCKING})
    if conflicts:
        blocked = sorted(set(blocked) | {"conflicts"})
    gaps = sorted(gaps, key=lambda item: json.dumps(item, sort_keys=True))
    return {
        "ok": True,
        "ready": not blocked,
        "blocked": blocked,
        "source": source.get("source"),
        "recorded_at": source.get("recorded_at"),
        "note": source.get("note"),
        "file_key": source.get("file_key"),
        "file_name": source.get("file_name"),
        "page": source.get("page"),
        "node": source.get("node"),
        "tokens": tokens,
        "css": render_css(emitted),
        "tailwind": render_tailwind(theme),
        "components": manifest,
        "conflicts": conflicts,
        "gaps": gaps,
    }


def _data_root(explicit: Path | None) -> Path:
    if explicit is not None:
        explicit.mkdir(parents=True, exist_ok=True)
        return explicit
    raw = os.environ.get("DATA_DIR", "/data")
    path = Path(raw)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        path = Path(os.environ.get("TMPDIR", "/tmp")) / "tisan-data"
        path.mkdir(parents=True, exist_ok=True)
    return path


def _store(reading: dict[str, Any], tenant: str, data_root: Path | None) -> str:
    root = _data_root(data_root)
    readings = (root / "readings").resolve()
    node = reading.get("node") if isinstance(reading.get("node"), dict) else {}
    node_id = str(node.get("id") or "page").replace(":", "-")
    folder = readings / tenant / str(reading.get("file_key"))
    folder.mkdir(parents=True, exist_ok=True)
    if readings not in folder.resolve().parents:
        raise FigmaError("refusing to write outside this tenant's readings")
    path = folder / f"{node_id}.json"
    stored = path.relative_to(root).as_posix()
    reading["stored"] = stored
    path.write_text(json.dumps(reading, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return stored


async def execute(
    payload: dict[str, Any],
    tenant_id: str,
    *,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """Read the recorded page for this tenant. This does not call Figma."""
    if not isinstance(payload, dict):
        raise FigmaError("input must be an object")
    file_key = normalise_file_key(payload.get("file_key"))
    node_id = normalise_node_id(payload.get("node_id"))
    tenant = _tenant(str(tenant_id))
    if file_key != TERVORY_FILE_KEY:
        raise FigmaError("this room reads the recorded Tervory page only")
    source = load_fixture(node_id)
    reading = compile_reading(source)
    reading["stored"] = _store(reading, tenant, data_root)
    return reading
