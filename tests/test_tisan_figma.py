"""TS-2: Tisan's Figma reader. No database and no network."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIGMA_PATH = ROOT / "agents" / "tisan" / "figma.py"
FIXTURE = ROOT / "agents" / "tisan" / "fixtures" / "tervory-landing.json"
SKILL = ROOT / "tank" / "skills" / "tisan.figma" / "1.0.0"
TENANT = "11111111-1111-4111-8111-111111111111"
FILE_KEY = "ksi7ctRwEnN8wbip1yfuhL"

COLOURS = {
    "accent-default": "#e80008",
    "accent-red": "#e80008",
    "accent-text": "#001840",
    "bg-accent-soft": "#eef1f8",
    "bg-ink": "#001840",
    "bg-page": "#ffffff",
    "bg-subtle": "#f4f6fb",
    "border-default": "#d9dee9",
    "border-strong": "#b8bfd0",
    "status-positive": "#1f7a4d",
    "text-muted": "#7e889e",
    "text-on-accent": "#ffffff",
    "text-on-ink": "#ffffff",
    "text-on-ink-muted": "#b8bfd0",
    "text-primary": "#001840",
    "text-secondary": "#4a5570",
}
TYPE = {
    "size-body": "17px",
    "size-caption": "12px",
    "size-h1": "48px",
    "size-h2": "36px",
    "size-h3": "24px",
    "size-lead": "20px",
    "size-small": "14px",
}


def _load():
    spec = importlib.util.spec_from_file_location("tisan_figma_test", FIGMA_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gaps(reading: dict, kind: str) -> list[dict]:
    return [item for item in reading["gaps"] if item["kind"] == kind]


def _component(reading: dict, name: str) -> dict:
    return next(item for item in reading["components"] if item["figma_name"] == name)


def test_recorded_page_tokens_match_the_figma_values() -> None:
    figma = _load()
    reading = figma.compile_reading(figma.load_fixture("0:1"))
    assert reading["source"] == "fixture"
    assert reading["file_key"] == FILE_KEY
    assert reading["page"]["name"] == "Landing — Desktop & Mobile"
    assert reading["ready"] is False
    assert reading["conflicts"] == []
    assert reading["tokens"]["colour"] == COLOURS
    assert reading["tokens"]["type"] == TYPE
    assert reading["tokens"]["space"] == {}
    for key, value in COLOURS.items():
        assert f"--colour-{key}: {value};" in reading["css"]
    for key, value in TYPE.items():
        assert f"--type-{key}: {value};" in reading["css"]
    colour_lines = [line for line in reading["css"].splitlines() if "--colour-" in line]
    assert len(colour_lines) == len(COLOURS)
    assert "#" not in reading["tailwind"]
    assert "var(--colour-text-primary)" in reading["tailwind"]
    assert "var(--type-size-h1)" in reading["tailwind"]
    assert "Jost" not in reading["css"]
    assert "Inter" not in reading["css"]
    assert "spacing" not in reading["tailwind"]


def test_gaps_name_what_the_page_does_not_define() -> None:
    figma = _load()
    reading = figma.compile_reading(figma.load_fixture("0:1"))
    assert {item["kind"] for item in reading["gaps"]} == {
        "inconsistent_box",
        "missing_space",
        "missing_states",
        "missing_type_fields",
        "missing_type_scale",
        "partial_frame",
        "source",
    }
    assert "source" not in reading["blocked"]
    button = _component(reading, "Button")
    assert button["location"] == "components/ui/Button.tsx"
    assert button["variants"] == {"Kind": ["ghost", "ink", "primary", "secondary"]}
    assert button["states"] == []
    assert button["missing_states"] == ["active", "disabled", "error", "hover"]
    assert _gaps(reading, "missing_states") == [
        {"kind": "missing_states", "component": "Button", "states": ["active", "disabled", "error", "hover"]}
    ]
    assert _component(reading, "Logo")["missing_states"] == []
    assert _component(reading, "Squad card")["code_name"] == "SquadCard"
    assert _component(reading, "Logo")["used_in"] == [
        "Desktop — 1440 / Footer",
        "Desktop — 1440 / Nav",
        "Mobile — 390 / Footer",
        "Mobile — 390 / Nav",
    ]
    heights = _gaps(reading, "inconsistent_box")[0]["heights"]
    assert heights["Kind=secondary"] == 44
    assert heights["Kind=primary"] == 42
    partial = {item["name"]: item for item in _gaps(reading, "partial_frame")}
    assert partial["size/h1"]["present_on"] == ["Desktop — 1440"]
    assert partial["size/h1"]["absent_on"] == ["Mobile — 390"]
    assert partial["size/body"]["present_on"] == ["Mobile — 390"]
    assert _gaps(reading, "missing_type_scale")[0]["names"] == ["h4", "h5", "h6", "label"]
    assert _gaps(reading, "missing_type_fields")[0]["fields"] == ["family", "line_height", "weight"]
    assert "Tervory / Colour" not in reading["css"]
    assert "collection" in _gaps(reading, "source")[0]["detail"]


def test_one_frame_does_not_borrow_the_other_frames_type_size() -> None:
    figma = _load()
    desktop = figma.compile_reading(figma.load_fixture("2:11"))
    mobile = figma.compile_reading(figma.load_fixture("6:45"))
    assert "size-h1" in desktop["tokens"]["type"]
    assert "size-body" not in desktop["tokens"]["type"]
    assert "size-body" in mobile["tokens"]["type"]
    assert "size-h1" not in mobile["tokens"]["type"]
    assert _gaps(desktop, "partial_frame") == []
    assert _component(desktop, "Button")["used_in"] == [
        "Desktop — 1440 / Hero",
        "Desktop — 1440 / Nav",
        "Desktop — 1440 / Pricing",
    ]


def test_a_conflicting_value_is_left_out() -> None:
    figma = _load()
    source = {
        "file_key": FILE_KEY,
        "file_name": None,
        "source": "figma",
        "recorded_at": None,
        "note": None,
        "collections_known": True,
        "page": {"id": "0:1", "name": "Page"},
        "node": {"id": "0:1", "name": "Page"},
        "frames": [{"id": "1:1", "name": "Desktop"}, {"id": "1:2", "name": "Mobile"}],
        "variables": [
            {
                "name": "text/primary",
                "values": [
                    {"scope": "Desktop", "value": "#001840"},
                    {"scope": "Mobile", "value": "#111111"},
                ],
            },
            {
                "name": "space/4",
                "values": [
                    {"scope": "Desktop", "value": "16"},
                    {"scope": "Mobile", "value": "16"},
                ],
            },
            {
                "name": "space/odd",
                "values": [
                    {"scope": "Desktop", "value": "6"},
                    {"scope": "Mobile", "value": "6"},
                ],
            },
        ],
        "components": [
            {
                "id": "2:1",
                "name": "Button",
                "variants": [
                    {"id": "2:2", "name": "State=hover", "properties": {"State": "hover"}, "width": 10, "height": 40},
                ],
            }
        ],
        "uses": [{"id": "3:1", "name": "Button/go", "page": "Desktop", "section": "Nav"}],
        "extra_gaps": [],
    }
    reading = figma.compile_reading(source)
    assert reading["conflicts"] == [
        {
            "name": "text/primary",
            "values": [
                {"scope": "Desktop", "value": "#001840"},
                {"scope": "Mobile", "value": "#111111"},
            ],
        }
    ]
    assert "--colour-text-primary" not in reading["css"]
    assert reading["tokens"]["space"] == {"4": "16px", "odd": "6px"}
    assert _gaps(reading, "inconsistent_space") == [{"kind": "inconsistent_space", "values": [6, 16]}]
    assert _gaps(reading, "missing_space") == []
    assert _component(reading, "Button")["missing_states"] == ["active", "disabled", "error"]
    assert "hover" in _component(reading, "Button")["states"]


def test_rest_payload_resolves_aliases_and_does_not_read_raw_fills() -> None:
    figma = _load()
    nodes = {
        "name": "Example",
        "nodes": {
            "0:1": {
                "document": {
                    "id": "0:1",
                    "name": "Landing",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "2:10",
                            "name": "Button",
                            "type": "COMPONENT_SET",
                            "componentPropertyDefinitions": {
                                "Kind": {
                                    "type": "VARIANT",
                                    "defaultValue": "primary",
                                    "variantOptions": ["primary", "secondary"],
                                }
                            },
                            "children": [
                                {
                                    "id": "2:2",
                                    "name": "Kind=primary",
                                    "type": "COMPONENT",
                                    "absoluteBoundingBox": {"width": 79, "height": 42},
                                }
                            ],
                        },
                        {
                            "id": "2:11",
                            "name": "Desktop",
                            "type": "FRAME",
                            "children": [
                                {
                                    "id": "2:12",
                                    "name": "Nav",
                                    "type": "FRAME",
                                    "children": [
                                        {"id": "2:21", "name": "Button/go", "type": "INSTANCE"},
                                        {
                                            "id": "9:9",
                                            "name": "Swatch",
                                            "type": "RECTANGLE",
                                            "fills": [{"color": {"r": 1, "g": 0, "b": 1}}],
                                        },
                                    ],
                                }
                            ],
                        },
                    ],
                }
            }
        },
    }
    variables = {
        "meta": {
            "variableCollections": {
                "VariableCollectionId:1:1": {
                    "name": "Tervory / Colour",
                    "modes": [
                        {"modeId": "1:0", "name": "Default"},
                        {"modeId": "1:1", "name": "Dark"},
                    ],
                }
            },
            "variables": {
                "VariableID:1:2": {
                    "id": "VariableID:1:2",
                    "name": "text/primary",
                    "valuesByMode": {
                        "1:0": {"r": 0, "g": 24 / 255, "b": 64 / 255, "a": 1},
                        "1:1": {"r": 1, "g": 1, "b": 1, "a": 1},
                    },
                },
                "VariableID:1:3": {
                    "id": "VariableID:1:3",
                    "name": "bg/page",
                    "valuesByMode": {
                        "1:0": {"r": 1, "g": 1, "b": 1, "a": 1},
                        "1:1": {"r": 1, "g": 1, "b": 1, "a": 1},
                    },
                },
                "VariableID:1:4": {
                    "id": "VariableID:1:4",
                    "name": "text/alias",
                    "valuesByMode": {
                        "1:0": {"type": "VARIABLE_ALIAS", "id": "VariableID:1:3"},
                        "1:1": {"type": "VARIABLE_ALIAS", "id": "VariableID:1:3"},
                    },
                },
                "VariableID:1:5": {
                    "id": "VariableID:1:5",
                    "name": "text/missing",
                    "valuesByMode": {"1:0": {"type": "VARIABLE_ALIAS", "id": "VariableID:nope"}},
                },
                "VariableID:1:6": {
                    "id": "VariableID:1:6",
                    "name": "text/loop-a",
                    "valuesByMode": {"1:0": {"type": "VARIABLE_ALIAS", "id": "VariableID:1:7"}},
                },
                "VariableID:1:7": {
                    "id": "VariableID:1:7",
                    "name": "text/loop-b",
                    "valuesByMode": {"1:0": {"type": "VARIABLE_ALIAS", "id": "VariableID:1:6"}},
                },
                "VariableID:1:8": {
                    "id": "VariableID:1:8",
                    "name": "space/4",
                    "valuesByMode": {"1:0": 16, "1:1": 16},
                },
                "VariableID:1:9": {
                    "id": "VariableID:1:9",
                    "name": "text/fade",
                    "valuesByMode": {
                        "1:0": {"r": 0, "g": 0, "b": 0, "a": 0.5},
                        "1:1": {"r": 0, "g": 0, "b": 0, "a": 0.5},
                    },
                },
            },
        }
    }
    reading = figma.compile_reading(figma.normalise_rest(FILE_KEY, "0:1", nodes, variables))
    assert reading["source"] == "figma"
    assert reading["tokens"]["colour"]["bg-page"] == "#ffffff"
    assert reading["tokens"]["colour"]["text-alias"] == "#ffffff"
    assert reading["tokens"]["colour"]["text-fade"] == "#00000080"
    assert "text-primary" not in reading["tokens"]["colour"]
    assert reading["tokens"]["space"] == {"4": "16px"}
    assert "#ff00ff" not in reading["css"]
    assert {item["name"] for item in _gaps(reading, "unresolved_alias")} >= {"text/missing", "text/loop-a", "text/loop-b"}
    assert _component(reading, "Button")["variants"]["Kind"] == ["primary", "secondary"]
    assert _component(reading, "Button")["used_in"] == ["Desktop / Nav"]


@pytest.mark.asyncio
async def test_the_room_reads_the_fixture_and_does_not_call_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    figma = _load()
    monkeypatch.setenv("FIGMA_TOKEN", "super-secret-token")
    reading = await figma.execute({"node_id": "0-1"}, TENANT, data_root=tmp_path)
    dumped = json.dumps(reading)
    assert "super-secret-token" not in dumped
    assert reading["source"] == "fixture"
    assert reading["tokens"]["colour"]["accent-default"] == "#e80008"
    assert reading["stored"] == f"readings/{TENANT}/{FILE_KEY}/0-1.json"
    assert "super-secret-token" not in (tmp_path / reading["stored"]).read_text(encoding="utf-8")
    with pytest.raises(figma.FigmaError, match="recorded Tervory page only"):
        await figma.execute({"file_key": "a" * 22}, TENANT, data_root=tmp_path)
    with pytest.raises(figma.FigmaError):
        await figma.execute({"file_key": "../secrets"}, TENANT, data_root=tmp_path)
    with pytest.raises(figma.FigmaError):
        await figma.execute({"node_id": "9:9"}, TENANT, data_root=tmp_path)
    with pytest.raises(figma.FigmaError):
        await figma.execute({}, "../tenant", data_root=tmp_path)


def test_room_has_no_path_to_figma_and_copies_the_reader() -> None:
    reader = FIGMA_PATH.read_text(encoding="utf-8")
    assert "api.figma.com" not in reader
    assert "httpx" not in reader
    docker = (ROOT / "agents" / "tisan" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY tisan/figma.py /app/figma.py" in docker
    assert "COPY tisan/fixtures /app/fixtures" in docker
    assert "TISAN_FIGMA_FIXTURE=/app/fixtures/tervory-landing.json" in docker
    compose = (ROOT / "agents" / "tisan" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "FIGMA_TOKEN" not in compose
    assert "api.figma.com" not in compose
    assert "name: tervory-gw-tisan" in compose
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert any(line.strip() == "FIGMA_TOKEN=" for line in example.splitlines())
    readme = (ROOT / "agents" / "tisan" / "README.md").read_text(encoding="utf-8")
    assert "tisan.figma" in readme
    assert "does not call Figma" in readme
    app = (ROOT / "agents" / "tisan" / "app.py").read_text(encoding="utf-8")
    assert '"figma": figma' in app
    recorded = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert recorded["schema"] == "tisan.figma.fixture/1"
    assert recorded["file_key"] == FILE_KEY
    assert recorded["recorded_from"] == "figma-mcp"


def test_skill_package_is_offline_and_versioned() -> None:
    meta = (SKILL / "skill.yaml").read_text(encoding="utf-8")
    assert "id: tisan.figma" in meta
    assert "agent: tisan" in meta
    assert "rung: 3" in meta
    assert (SKILL / "CHANGELOG.md").is_file()
    assert (SKILL / "run.py").is_file()
    cases = [json.loads(line) for line in (SKILL / "evals" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) == 3
    assert cases[0]["expected"]["source"] == "fixture"
    assert cases[0]["expected"]["ready"] is False


def test_visual_frame_data_is_retained_without_inventing_missing_measurements() -> None:
    figma = _load()
    raw = json.loads(FIXTURE.read_text())
    visual = {"page": "/", "frameId": "2:11", "width": 1440, "height": 900,
              "tokens": {"--colour-ink": "#001840"},
              "elements": [{"nodeId": "heading", "selector": "h1", "text": "Example",
                            "box": {"x": 16, "y": 32, "width": 200, "height": 40},
                            "colours": {"color": "--colour-ink"}}]}
    raw["frames"][0]["visual"] = visual
    result = figma.compile_reading(figma.normalise_fixture(raw, "2:11"))
    assert result["visual"] == [visual]
    assert result["frame_data"][0]["visual"] == visual
    missing = figma.compile_reading(figma.load_fixture("6:45"))
    assert missing["visual"] == []
    assert missing["visual_status"] == "frame data incomplete"


def test_rest_frame_retains_measured_boxes_text_and_bound_colours() -> None:
    figma = _load()
    document = {"type": "FRAME", "name": "Home — 375", "id": "1:1", "absoluteBoundingBox": {"x": 100, "y": 200, "width": 375, "height": 900},
                "children": [{"type": "TEXT", "id": "1:2", "characters": "Recorded text",
                              "absoluteBoundingBox": {"x": 116, "y": 232, "width": 200, "height": 40},
                              "fills": [{"type": "SOLID"}], "boundVariables": {"fills": [{"id": "ink"}]}}]}
    variables = {"variables": {"ink": {"name": "ink", "valuesByMode": {"default": {"r": 0, "g": 24 / 255, "b": 64 / 255}}}}}
    frame = figma.visual_frames(document, variables)[0]
    assert "incomplete" not in frame
    assert frame["tokens"] == {"--colour-ink": "#001840"}
    assert frame["elements"][1]["box"] == {"x": 16, "y": 32, "width": 200, "height": 40}
    assert frame["elements"][1]["text"] == "Recorded text"
    document["children"][0].pop("absoluteBoundingBox")
    assert figma.visual_frames(document, variables)[0]["incomplete"] is True


@pytest.mark.asyncio
async def test_saved_reading_keeps_visual_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.loads(FIXTURE.read_text())
    # Synthetic capture explicitly marked incomplete, never substituted for approved truth.
    raw["frames"][0]["visual"] = {"frameId": "2:11", "incomplete": True, "elements": []}
    fixture = tmp_path / "capture.json"
    fixture.write_text(json.dumps(raw))
    monkeypatch.setenv("TISAN_FIGMA_FIXTURE", str(fixture))
    result = await _load().execute({"node_id": "2:11"}, TENANT, data_root=tmp_path / "data")
    saved = json.loads((tmp_path / "data" / result["stored"]).read_text())
    assert saved["visual"] == [raw["frames"][0]["visual"]]
    assert saved["frame_data"][0]["visual"]["incomplete"] is True
    assert saved["visual_status"] == "frame data incomplete"


def test_saved_landing_logos_and_image_fills_are_geometry_only() -> None:
    figma = _load()
    raw = json.loads(FIXTURE.read_text())
    logos = [use for use in raw["uses"] if use["name"].startswith("Logo")]
    assert len(logos) == 4
    # The saved capture has component sizes, but no positions: synthetic positions
    # exercise extraction only, never become a recorded landing-page baseline.
    size = raw["components"][1]["variants"][0]
    for use in logos:
        node = {**use, "type": "INSTANCE", "fills": [{"type": "IMAGE"}],
                "absoluteBoundingBox": {"x": 0, "y": 0, "width": size["width"], "height": size["height"]},
                "children": [{"type": "VECTOR", "fills": [{"type": "SOLID"}]}]}
        frame = {"type": "FRAME", "name": "Home — 1440", "id": "2:11", "absoluteBoundingBox":
                 {"x": 0, "y": 0, "width": 1440, "height": 900}, "children": [node]}
        visual = figma.visual_frames(frame, None)[0]
        assert not visual.get("incomplete")
        assert visual["elements"][1]["asset"] == "logo"
        assert visual["elements"][1]["brandFile"] == use["brandFile"]
        node.pop("brandFile")
        assert figma.visual_frames(frame, None)[0]["incomplete"]
        node["brandFile"] = use["brandFile"]
        assert visual["elements"][1]["colours"] == {}
        assert len(visual["elements"]) == 2
        node["name"] = "Photo"
        assert figma.visual_frames(frame, None)[0]["elements"][1]["asset"] == "image"
        node["fills"] = [{"type": "GRADIENT_LINEAR"}]
        assert figma.visual_frames(frame, None)[0]["incomplete"]


def test_any_incomplete_visual_sets_reading_status() -> None:
    figma = _load()
    raw = json.loads(FIXTURE.read_text())
    for frame in raw["frames"]:
        frame["visual"] = {"frameId": frame["id"], "incomplete": False}
    assert figma.compile_reading(figma.normalise_fixture(raw, "0:1"))["visual_status"] == "recorded"
    raw["frames"][1]["visual"]["incomplete"] = True
    assert figma.compile_reading(figma.normalise_fixture(raw, "0:1"))["visual_status"] == "frame data incomplete"
