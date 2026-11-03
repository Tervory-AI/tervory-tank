"""Offline engine packaging, scaffold, route, approval and image-layout regressions."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/base"))

from engines import ROOT as ENGINES, list_engines, load_engine  # noqa: E402
from engines.new_engine import scaffold  # noqa: E402
from pipeline import engine_terms  # noqa: E402
from skala import _import_run_uncached, load_packages  # noqa: E402


def test_template_manifest_loads_but_discovery_excludes_it():
    template = load_engine(ENGINES / "_template")
    assert template.id == "template"
    assert template.skills == {"ingest": "template.ingest", "profile": "template.profile"}
    assert template.profile_data_keys == ("generic_words", "blocked_hosts", "generic_locals")
    assert json.loads(template.gold_lists.read_text()) == []
    app = FastAPI()
    before = list(app.routes)
    template.register(app)
    assert app.routes == before
    assert [engine.id for engine in list_engines()] == ["ffl"]
    assert not (ROOT / "tank/skills/template.ingest").exists()
    assert not (ROOT / "tank/skills/template.profile").exists()
    packages = load_packages(ROOT / "tank/skills")
    # Same engine discovery as Tank's /v1/base/engines.
    known = {skill_id.split(".")[0] for skill_id, _ in packages if skill_id.endswith(".ingest")}
    assert "template" not in known
    assert "_template" not in known


@pytest.mark.parametrize("field,value", [
    ("id", "../ffl"), ("id", "FFL"), ("id", "a" * 33),
    ("id", "different"),
    ("skills", {"ingest": "ffl.ingest@1.0.0", "profile": "ffl.profile"}),
    ("routes", {"module": "../reference", "function": "register"}),
    ("routes", {"module": "absent", "function": "register"}),
    ("gold_lists", "../gold_lists.json"), ("profile_data_keys", []),
])
def test_manifest_rejects_invalid_contract(tmp_path, field, value):
    folder = tmp_path / "ffl"
    shutil.copytree(ENGINES / "ffl", folder)
    manifest = json.loads((folder / "engine.json").read_text())
    manifest[field] = value
    (folder / "engine.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_engine(folder)


@pytest.mark.parametrize("engine_id", ["", "../ffl", "FFL", "_private", "a-b", "a" * 33])
def test_scaffold_refuses_bad_id_without_writing(tmp_path, engine_id):
    with pytest.raises(ValueError, match="invalid engine id"):
        scaffold(engine_id, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("existing", ["agents/base/engines/throwaway", "tank/skills/throwaway.ingest", "tank/skills/throwaway.profile"])
def test_scaffold_refuses_existing_id_without_overwriting(tmp_path, existing):
    path = tmp_path / existing
    path.mkdir(parents=True)
    marker = path / "keep"
    marker.write_text("keep")
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    with pytest.raises(ValueError, match="already exists"):
        scaffold("throwaway", tmp_path)
    assert marker.read_text() == "keep"
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


@pytest.mark.asyncio
async def test_scaffold_cli_loads_skala_packages_and_cannot_run_unimplemented_code(tmp_path):
    result = subprocess.run([
        sys.executable, str(ENGINES / "new_engine.py"), "throwaway", "--root", str(tmp_path),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    engine = load_engine("throwaway", tmp_path / "agents/base/engines")
    engine.register(FastAPI())
    assert not (engine.path / "skills").exists()
    packages = load_packages(tmp_path / "tank/skills")
    assert set(packages) == {("throwaway.ingest", "1.0.0"), ("throwaway.profile", "1.0.0")}
    for package in packages.values():
        assert package.task_type is None
        assert package.cases == []
        assert json.loads((package.path / "data/site.json").read_text()) == {
            "generic_words": [], "blocked_hosts": [], "generic_locals": [],
        }
        with pytest.raises(NotImplementedError):
            await _import_run_uncached(package)({}, None)
    assert list_engines(tmp_path / "agents/base/engines")[0].id == "throwaway"


@pytest.mark.asyncio
async def test_scaffold_packages_register_as_candidates_without_approval(tmp_path):
    from contextlib import asynccontextmanager

    scaffold("throwaway", tmp_path)
    packages = load_packages(tmp_path / "tank/skills")
    conn = AsyncMock()
    calls = []

    async def execute(query, *args):
        calls.append((query, args))

    conn.execute.side_effect = execute

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    # Execute the unchanged registry function with an offline connection double;
    # importing all of Tank would require unrelated runtime settings.
    tree = ast.parse((ROOT / "tank/main.py").read_text())
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "register_packages")
    scope = {"_packages": packages, "pool": lambda: Pool()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "tank/main.py", "exec"), scope)
    await scope["register_packages"]()
    insertions = [(query, args) for query, args in calls if "INSERT INTO tank.skills" in query]
    assert {args[0] for _, args in insertions} == {"throwaway.ingest", "throwaway.profile"}
    # The existing registry uses the database default 'candidate'; it never sets state.
    for query, _ in insertions:
        assert "state" not in query
    schema = (ROOT / "tank/schema.sql").read_text()
    assert "DEFAULT 'candidate'" in schema
    assert all("approved" not in query for query, _ in calls)


def test_ffl_routes_and_terms_match_existing_contract():
    from base_gold.ffl.reference import register as legacy_register

    before, after = FastAPI(), FastAPI()
    legacy_register(before)
    engine = load_engine("ffl")
    engine.register(after)
    assert before.openapi() == after.openapi()
    paths = set(after.openapi()["paths"])
    assert "/reference/ffl" in paths
    assert paths == set(before.openapi()["paths"])
    for version in ("1.0.0", "1.1.0", "1.1.1"):
        data = {}
        for path in sorted((ROOT / "tank/skills/ffl.profile" / version / "data").glob("*.json")):
            data.update(json.loads(path.read_text()))
        expected = {}
        for key in engine.profile_data_keys:
            expected[key] = list(dict.fromkeys(
                text for item in data.get(key, []) if (text := " ".join(str(item).lower().split()))
            ))
        assert engine_terms(engine.id, version) == expected


def test_flat_image_copy_contains_loader_ffl_and_excludes_template_discovery(tmp_path):
    dockerfile = (ROOT / "agents/base/Dockerfile").read_text()
    assert "COPY agents/base/engines /app/engines" in dockerfile
    assert "COPY agents/base/base_gold /app/base_gold" in dockerfile
    assert "COPY agents/_brain/security.py /app/reference_security.py" in dockerfile
    app = tmp_path / "app"
    app.mkdir()
    for name in ("engines", "base_gold"):
        shutil.copytree(ROOT / "agents/base" / name, app / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "agents/base/pipeline.py", app)
    shutil.copy(ROOT / "tank/base_source_scores.py", app)
    shutil.copy(ROOT / "agents/_brain/security.py", app / "reference_security.py")
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "SKILLS_DIR")}
    result = subprocess.run([sys.executable, "-c", """
from fastapi import FastAPI
from engines import list_engines
from base_gold import build
app = FastAPI()
engines = list_engines()
assert [engine.id for engine in engines] == ['ffl']
for engine in engines:
    engine.register(app)
assert '/reference/ffl' in app.openapi()['paths']
assert callable(build.fetch_list)
print('flat image engine list: ffl; reference routes and gold builder loaded')
"""], cwd=app, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
