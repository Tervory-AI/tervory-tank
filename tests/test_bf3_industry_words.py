"""BF3: core find_site and contacts ship a neutral default. The engine passes its own lists."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "base"))

from pipeline import engine_terms, enrich_one  # noqa: E402

SKILLS = ROOT / "tank" / "skills"
FIND = SKILLS / "base.find_site" / "1.5.0" / "run.py"
CONTACTS = SKILLS / "base.contacts" / "1.1.0" / "run.py"
SITE = SKILLS / "ffl.profile" / "1.1.0" / "data" / "site.json"
CORE = (
    FIND,
    SKILLS / "base.find_site" / "1.5.0" / "skill.yaml",
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
    loaded = engine_terms("ffl")
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
    armed = await enrich_one(raw, None, [], "ffl", call)
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
