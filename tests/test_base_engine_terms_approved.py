"""Base reads engine word lists only from the approved engine profile version."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "base"))

from pipeline import engine_terms, enrich_one  # noqa: E402
from room import SkillClient, SkillError  # noqa: E402

EMPTY = {"generic_words": [], "blocked_hosts": [], "generic_locals": []}
SITE_110 = json.loads((ROOT / "tank/skills/ffl.profile/1.1.0/data/site.json").read_text())


def test_approved_version_without_words_loads_nothing() -> None:
    assert engine_terms("ffl", "1.0.0") == EMPTY


def test_approved_version_with_words_loads_them() -> None:
    got = engine_terms("ffl", "1.1.0")
    assert got["generic_words"] == SITE_110["generic_words"]
    assert got["blocked_hosts"] == SITE_110["blocked_hosts"]
    assert got["generic_locals"] == SITE_110["generic_locals"]


@pytest.mark.parametrize("version", [None, "", "9.9.9", "../1.1.0", "1.1.0/../1.1.0", "*"])
def test_no_or_bad_version_never_falls_back(version) -> None:
    assert engine_terms("ffl", version) == EMPTY


def test_no_engine() -> None:
    assert engine_terms(None, "1.1.0") == EMPTY
    assert engine_terms("nope", "1.0.0") == EMPTY


class _Resp:
    def __init__(self, status: int, data: dict) -> None:
        self.status_code, self._data = status, data

    def json(self) -> dict:
        return self._data


class _Tank:
    """Approved ffl.profile is `approved`; 1.1.0 sits in staging (what preview would pick)."""

    def __init__(self, approved: str | None) -> None:
        self.approved, self.seen = approved, []

    async def get(self, url, params=None, headers=None, timeout=None):
        preview = str((params or {}).get("preview")).lower() == "true"
        self.seen.append(preview)
        if preview:
            return _Resp(200, {"version": "1.1.0", "ref": "ffl.profile@1.1.0"})
        if self.approved is None:
            return _Resp(409, {"detail": "ffl.profile has no approved version"})
        return _Resp(200, {"version": self.approved, "ref": f"ffl.profile@{self.approved}"})


@pytest.mark.asyncio
async def test_worker_asks_for_the_approved_version_never_preview() -> None:
    tank = _Tank("1.0.0")
    client = SkillClient(tank, "http://tank", "k")
    assert await client.approved("ffl.profile") == "1.0.0"
    assert tank.seen == [False]
    assert await SkillClient(_Tank(None), "http://tank", "k").approved("ffl.profile") is None


@pytest.mark.asyncio
async def test_a_tank_outage_is_not_read_as_no_version() -> None:
    class Down:
        async def get(self, *a, **k):
            return _Resp(502, {"detail": "down"})
    with pytest.raises(SkillError):
        await SkillClient(Down(), "http://tank", "k").approved("ffl.profile")


async def _run(engine_version):
    seen: dict[str, dict] = {}

    async def call(skill_id, payload):
        seen[skill_id] = payload
        return {
            "base.normalize": {"fields": {"name": {"value": "Harbor Arms Bakery", "confidence": 90}}},
            "base.resolve": {"match": None, "verdict": "new", "score": 0},
            "base.find_site": {"website": {"value": None, "source": "none", "confidence": 0}},
            "base.socials": {"count": 0, "profiles": [], "presence": "none", "confidence": 0},
            "base.verify": {"confidence": 10, "tier": "review", "flags": []},
        }.get(skill_id, {"confidence": 0})

    out = await enrich_one({"name": "Harbor Arms Bakery"}, None, [], "ffl", call, None, engine_version)
    assert out.status == "done", out.error
    return seen


@pytest.mark.asyncio
async def test_call_site_with_approved_100_sends_no_lists() -> None:
    seen = await _run("1.0.0")
    assert "generic_words" not in seen["base.find_site"]
    assert "blocked_hosts" not in seen["base.find_site"]
    assert "generic_words" not in seen["base.contacts"]


@pytest.mark.asyncio
async def test_call_site_once_110_is_approved_sends_its_lists() -> None:
    seen = await _run("1.1.0")
    assert seen["base.find_site"]["generic_words"] == SITE_110["generic_words"]
    assert seen["base.find_site"]["blocked_hosts"] == SITE_110["blocked_hosts"]
    assert seen["base.contacts"]["generic_words"] == SITE_110["generic_locals"]


@pytest.mark.asyncio
async def test_pipeline_retains_complete_observed_contact_collections() -> None:
    phones = [f"+1512555020{i}" for i in range(1, 6)]
    emails = [f"team{i}@shop.example" for i in range(6)]
    links = ["https://facebook.com/shop", "https://facebook.com/shop-store"]
    proof = [{"source_url": "https://shop.example/contact", "checked_at": "2026-10-27T10:00:00+00:00",
              "phones": phones, "emails": emails, "websites": ["https://store.shop.example/"], "socials": links, "links": links}]

    async def call(skill_id, payload):
        return {
            "base.normalize": {"fields": {"name": {"value": "Fixture Shop", "confidence": 90}}},
            "base.resolve": {"match": None, "verdict": "new", "score": 0},
            "base.find_site": {"website": {"value": "https://shop.example/", "source": "input:verified", "confidence": 85}},
            "base.scrape_site": {"phones": phones, "emails": emails, "socials": {"facebook": links[0]}, "_base_observations": proof},
            "base.socials": {"count": 0, "profiles": [], "presence": "none", "confidence": 0},
            "base.verify": {"confidence": 50, "tier": "review", "flags": []},
        }.get(skill_id, {"confidence": 0})

    result = await enrich_one({"name": "Fixture Shop"}, None, [], None, call)
    assert result.status == "done", result.error
    assert result.profile["phones"]["value"] == phones
    assert result.profile["emails"]["value"] == emails
    assert result.profile["social_links"]["value"] == links
    assert result.profile["websites"]["value"] == ["https://shop.example/", "https://store.shop.example/"]
    assert result.passes["2b"]["field_observations"] == proof


def _flat(tmp_path: Path, skills_dir: Path | None) -> dict:
    """Import pipeline.py from a flat /app-style folder, like the room image."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "pipeline.py").write_text((ROOT / "agents/base/pipeline.py").read_text())
    # agents/base/Dockerfile copies tank/base_source_scores.py next to pipeline.py.
    (app / "base_source_scores.py").write_text((ROOT / "tank/base_source_scores.py").read_text())
    shutil.copytree(ROOT / "agents/base/base_gold", app / "base_gold", ignore=shutil.ignore_patterns("__pycache__"))
    env = {k: v for k, v in os.environ.items() if k != "SKILLS_DIR"}
    if skills_dir:
        env["SKILLS_DIR"] = str(skills_dir)
    code = textwrap.dedent("""
        import json, pipeline
        print(json.dumps({"a": pipeline.engine_terms("ffl", "1.0.0"),
                          "b": pipeline.engine_terms("ffl", "1.1.0"),
                          "none": pipeline.engine_terms("ffl", None)}))
    """)
    done = subprocess.run([sys.executable, "-c", code], cwd=app, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _image_skills(tmp_path: Path) -> Path:
    """Same selection the Dockerfile makes: */<ver>/data/*.json of every *.profile package."""
    out = tmp_path / "skills"
    src = ROOT / "tank" / "skills"
    for path in src.glob("*.profile/*/data/*.json"):
        dest = out / path.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    return out


def test_flat_app_layout_boots_and_reads_only_the_named_version(tmp_path: Path) -> None:
    got = _flat(tmp_path, _image_skills(tmp_path))
    assert got["a"] == EMPTY
    assert got["b"]["generic_words"] == SITE_110["generic_words"]
    assert got["none"] == EMPTY


def test_flat_app_layout_without_skills_dir_boots_empty(tmp_path: Path) -> None:
    got = _flat(tmp_path, None)
    assert got == {"a": EMPTY, "b": EMPTY, "none": EMPTY}
