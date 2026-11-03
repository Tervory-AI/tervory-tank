"""BF3: core find_site and contacts ship a neutral default. The engine passes its own lists."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "base"))

from pipeline import engine_terms, enrich_one  # noqa: E402

SKILLS = ROOT / "tank" / "skills"
FIND = SKILLS / "base.find_site" / "1.5.0" / "run.py"
FIND_16 = SKILLS / "base.find_site" / "1.6.0" / "run.py"
CONTACTS = SKILLS / "base.contacts" / "1.1.0" / "run.py"
SITE = SKILLS / "ffl.profile" / "1.1.0" / "data" / "site.json"
CORE = (
    FIND,
    SKILLS / "base.find_site" / "1.5.0" / "skill.yaml",
    FIND_16,
    SKILLS / "base.find_site" / "1.6.0" / "skill.yaml",
    SKILLS / "base.find_site" / "1.6.0" / "CHANGELOG.md",
    CONTACTS,
    SKILLS / "base.contacts" / "1.1.0" / "skill.yaml",
    ROOT / "agents" / "base" / "pipeline.py",
)
# Words that belong in the engine list, not in the core packages.
BANNED = re.compile(
    r"firearms?|ammunit|ammo|\bguns?\b|\barms\b|gunbroker|armslist|\batf\b|\bffl\b|"
    r"\btactical\b|\barmory\b|\bshooting\b|\bhunting\b|"
    r"\bsporting\b|\bgoods\b|\boutdoors?\b|\bpawn\b|\bdefense\b|\bprecision\b|"
    r"\bfishing\b|\bbait\b|\btackle\b|\bfarm\b|\branch\b|\bauction\b|\bjewelry\b|\bloans?\b",
    re.I,
)
REMAINDER = (
    "sporting", "goods", "outdoors", "outdoor", "pawn", "defense", "precision",
    "fishing", "bait", "tackle", "farm", "ranch", "auction", "jewelry", "loan", "loans",
)


class BoomHttp:
    def __getattr__(self, name: str):
        async def _call(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError(name)

        return _call


class BoomCtx:
    def __init__(self) -> None:
        self.http = BoomHttp()
        self.env: dict[str, str] = {}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _terms() -> dict:
    return json.loads(SITE.read_text(encoding="utf-8"))


def test_core_packages_do_not_carry_the_trade_list() -> None:
    offenders: list[str] = []
    for path in CORE:
        match = BANNED.search(path.read_text(encoding="utf-8"))
        if match:
            offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert offenders == []
    old_site = (SKILLS / "base.find_site" / "1.4.0" / "run.py").read_text(encoding="utf-8")
    old_contacts = (SKILLS / "base.contacts" / "1.0.0" / "run.py").read_text(encoding="utf-8")
    assert "gunbroker.com" in old_site
    assert "ffl" in old_contacts


def test_engine_file_holds_the_lists_the_call_site_forwards() -> None:
    terms = _terms()
    assert terms["generic_words"]
    assert terms["blocked_hosts"]
    assert terms["generic_locals"]
    loaded = engine_terms("ffl", "1.1.0")
    assert loaded["generic_words"] == terms["generic_words"]
    assert loaded["blocked_hosts"] == terms["blocked_hosts"]
    assert loaded["generic_locals"] == terms["generic_locals"]
    missing = [word for word in REMAINDER if word not in terms["generic_words"]]
    assert missing == []
    assert engine_terms(None) == {"generic_words": [], "blocked_hosts": [], "generic_locals": []}
    assert engine_terms("nope") == {"generic_words": [], "blocked_hosts": [], "generic_locals": []}


@pytest.mark.asyncio
async def test_a_bakery_is_not_scored_with_the_trade_list() -> None:
    find = _load(FIND, "find_site_150")
    contacts = _load(CONTACTS, "contacts_110")
    terms = _terms()
    ctx = BoomCtx()
    bare = await find.run({"name": "Harbor Arms Bakery", "city": "Portland", "state": "OR"}, ctx)
    assert "arms" in bare["name_words"]
    assert "harbor" in bare["name_words"]
    assert "bakery" in bare["name_words"]

    trade_name = await find.run(
        {"name": "Harbor Arms Bakery", "city": "Portland", "state": "OR", "generic_words": terms["generic_words"]},
        ctx,
    )
    assert "arms" not in trade_name["name_words"]
    assert trade_name["name_words"] == ["harbor", "bakery"]

    shop = "Harbor " + " ".join(word.capitalize() for word in REMAINDER)
    kept = await find.run({"name": shop, "city": "Portland", "state": "OR"}, ctx)
    assert kept["name_words"] == ["harbor", *REMAINDER]
    dropped = await find.run({"name": shop, "city": "Portland", "state": "OR", "generic_words": list(REMAINDER)}, ctx)
    assert dropped["name_words"] == ["harbor"]

    host = terms["blocked_hosts"][0]
    open_hint = await find.run({"name": "Harbor Arms Bakery", "website": f"https://{host}/item"}, ctx)
    assert open_hint["hint_blocked"] is False
    closed_hint = await find.run(
        {
            "name": "Harbor Arms Bakery",
            "website": f"https://{host}/item",
            "blocked_hosts": terms["blocked_hosts"],
        },
        ctx,
    )
    assert closed_hint["hint_blocked"] is True
    public = await find.run({"name": "Harbor Arms Bakery", "website": "https://example.gov/form"}, ctx)
    assert public["hint_blocked"] is True

    locals_ = terms["generic_locals"]
    emails = ["info@harbor-bakery.example", *[f"{name}@harbor-bakery.example" for name in locals_]]
    plain = await contacts.run({"website": "https://harbor-bakery.example", "emails": emails, "people": []}, ctx)
    assert plain["generic_emails"] == ["info@harbor-bakery.example"]
    assert plain["personal_emails"] == sorted(f"{name}@harbor-bakery.example" for name in locals_)
    passed = await contacts.run(
        {
            "website": "https://harbor-bakery.example",
            "emails": emails,
            "people": [],
            "generic_words": locals_,
        },
        ctx,
    )
    assert passed["personal_emails"] == []
    assert set(passed["generic_emails"]) == set(emails)


@pytest.mark.asyncio
async def test_the_call_site_passes_engine_lists_only_for_that_engine() -> None:
    seen: dict[str, dict] = {}

    async def call(skill_id: str, payload: dict) -> dict:
        seen[skill_id] = payload
        if skill_id == "base.normalize":
            return {
                "fields": {
                    "name": {"value": "Harbor Arms Bakery", "confidence": 90},
                    "city": {"value": "Portland", "confidence": 90},
                    "state": {"value": "OR", "confidence": 90},
                }
            }
        if skill_id == "base.resolve":
            return {"match": None, "verdict": "new", "score": 0}
        if skill_id == "base.find_site":
            return {"website": {"value": None, "source": "none", "confidence": 0}}
        if skill_id == "base.contacts":
            return {"confidence": 0}
        if skill_id == "base.socials":
            return {"count": 0, "profiles": [], "presence": "none", "confidence": 0}
        if skill_id == "base.verify":
            return {"confidence": 10, "tier": "review", "flags": []}
        return {"confidence": 0}

    raw = {"name": "Harbor Arms Bakery"}
    armed = await enrich_one(raw, None, [], "ffl", call, None, "1.1.0")
    assert armed.status == "done", armed.error
    terms = _terms()
    assert seen["base.find_site"]["generic_words"] == terms["generic_words"]
    assert seen["base.find_site"]["blocked_hosts"] == terms["blocked_hosts"]
    assert seen["base.contacts"]["generic_words"] == terms["generic_locals"]

    seen.clear()
    plain = await enrich_one(raw, None, [], None, call)
    assert plain.status == "done", plain.error
    assert "generic_words" not in seen["base.find_site"]
    assert "blocked_hosts" not in seen["base.find_site"]
    assert "generic_words" not in seen["base.contacts"]


CANDIDATES = {
    ("base.find_site", "1.5.0"),
    ("base.find_site", "1.6.0"),
    ("base.find_site", "1.7.0"),
    ("base.contacts", "1.1.0"),
    ("ffl.profile", "1.1.0"),
    # Eval-only refusal patches start as candidates too.
    ("base.find_site", "1.7.1"),
    ("base.contacts", "1.1.1"),
    ("ffl.profile", "1.1.1"),
    # Base B1 (#585): unapproved until the founder approves them in /skala.
    ("base.contacts", "1.2.0"),
    ("base.verify", "1.2.0"),
}


def _tank():
    os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
    os.environ.setdefault("LITELLM_MASTER_KEY", "test")
    os.environ.setdefault("TANK_API_KEY", "test")
    name = "bf3_tank_main"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tank" / "main.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _SkillRows:
    """The rows Skala would hold. approved_version and skill_state read them for real."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def fetchrow(self, sql: str, *args: object):
        if "agent_skill_submissions" in sql:
            return None  # repository packages in this fixture have no private owner
        raise AssertionError(sql)

    async def fetchval(self, sql: str, *args: object):
        if "state='approved'" in sql:
            chosen = [
                row for row in self.rows
                if row["id"] == args[0] and row["state"] == "approved" and row["present"]
            ]
            chosen.sort(key=lambda row: row["approved_at"], reverse=True)
            return chosen[0]["version"] if chosen else None
        if sql.startswith("SELECT state FROM tank.skills"):
            for row in self.rows:
                if row["id"] == args[0] and row["version"] == args[1]:
                    return row["state"]
            return None
        raise AssertionError(sql)

    async def fetch(self, sql: str, *args: object):
        if "state='staging'" in sql:
            return [
                {"version": row["version"]}
                for row in self.rows
                if row["id"] == args[0] and row["state"] == "staging" and row["present"]
            ]
        raise AssertionError(sql)


def _registry(tank) -> list[dict]:
    packages = tank.skala.load_packages(SKILLS)
    by_id: dict[str, list[str]] = {}
    for skill_id, version in packages:
        by_id.setdefault(skill_id, []).append(version)
    rows: list[dict] = []
    for skill_id, versions in by_id.items():
        eligible = [version for version in versions if (skill_id, version) not in CANDIDATES]
        approved = max(eligible, key=tank._vkey) if eligible else None
        for version in versions:
            if (skill_id, version) in CANDIDATES:
                state = "candidate"
            elif version == approved:
                state = "approved"
            else:
                state = "retired"
            rows.append({
                "id": skill_id,
                "version": version,
                "state": state,
                "present": True,
                "approved_at": version if state == "approved" else "",
            })
    return rows


class _DescribeHttp:
    def __init__(self, tank) -> None:
        self.tank = tank

    async def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float | None = None):
        skill_id = url.split("/v1/skala/", 1)[1].removesuffix("/run")
        preview = str((params or {}).get("preview", "")).lower() == "true"
        try:
            data = await self.tank.describe_skill(skill_id, preview)
            status = 200
        except self.tank.HTTPException as exc:
            data = {"detail": exc.detail}
            status = exc.status_code
        return _Response(status, data)


class _Response:
    def __init__(self, status_code: int, data: dict) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> dict:
        return self._data


@pytest.mark.asyncio
async def test_the_agent_is_pinned_to_approved_versions_and_a_candidate_run_is_rejected() -> None:
    """Calls the real _pick_version. Candidates stay off the pin until the Skills page approves them."""
    from room import SkillClient

    tank = _tank()
    packages = tank.skala.load_packages(SKILLS)
    tank._packages = packages
    rows = _SkillRows(_registry(tank))
    tank.pool = lambda: rows

    assert await tank._pick_version("base.find_site", False) == "1.4.0"
    assert await tank._pick_version("base.contacts", False) == "1.0.0"
    assert await tank._pick_version("ffl.profile", False) == "1.0.0"

    client = SkillClient(_DescribeHttp(tank), "http://tank", "test-key")
    versions, refs = await client.pin(False, "ffl")
    assert versions["base.find_site"] == "1.4.0"
    assert versions["base.contacts"] == "1.0.0"
    assert versions["ffl.profile"] == "1.0.0"
    assert refs["base.find_site"] == "base.find_site@1.4.0"
    assert refs["base.contacts"] == "base.contacts@1.0.0"
    assert refs["ffl.profile"] == "ffl.profile@1.0.0"
    assert versions["base.find_site"] != "1.5.0"
    assert versions["base.find_site"] != "1.6.0"
    assert versions["base.find_site"] != "1.7.0"
    assert versions["base.contacts"] != "1.1.0"

    tenant = uuid.UUID("00000000-0000-0000-0000-000000000001")
    for skill_id, version in (
        ("base.find_site", "1.5.0"),
        ("base.find_site", "1.6.0"),
        ("base.find_site", "1.7.0"),
        ("base.contacts", "1.1.0"),
        ("ffl.profile", "1.1.0"),
        ("base.find_site", "1.7.1"),
        ("base.contacts", "1.1.1"),
        ("ffl.profile", "1.1.1"),
    ):
        body = tank.SkillRun(tenant_id=tenant, input={"name": "Example"}, version=version, preview=False)
        with pytest.raises(tank.HTTPException) as caught:
            await tank._run_one_skill(skill_id, body, None)
        assert caught.value.status_code == 409
        assert "candidate" in str(caught.value.detail)
