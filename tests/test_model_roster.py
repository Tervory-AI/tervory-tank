"""litellm/config.yaml is the model roster; Tank's policy rows must only name models it has."""
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "litellm" / "config.yaml").read_text(encoding="utf-8"))
SCHEMA = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
NAMES = {m["model_name"] for m in CONFIG["model_list"]}


def test_every_model_has_a_price_and_a_key_from_the_environment() -> None:
    for m in CONFIG["model_list"]:
        info = m.get("model_info") or {}
        assert info.get("input_cost_per_token", 0) > 0, m["model_name"]
        assert info.get("output_cost_per_token", 0) > 0, m["model_name"]
        assert str(m["litellm_params"]["api_key"]).startswith("os.environ/"), m["model_name"]


def test_no_china_hosted_provider_in_the_roster() -> None:
    for m in CONFIG["model_list"]:
        provider = m["litellm_params"]["model"].split("/", 1)[0]
        assert provider not in {"deepseek", "moonshot"}, m["model_name"]


def test_no_automatic_provider_fallbacks() -> None:
    """Switching provider is an approved step, never automatic."""
    assert not CONFIG.get("litellm_settings", {}).get("fallbacks")
    assert not CONFIG.get("router_settings", {}).get("fallbacks")


def test_policy_seeds_and_the_switch_name_roster_models() -> None:
    seeded = set(re.findall(r"\('[a-z0-9_.]+',\s*\d+,\s*'([a-z0-9-]+)'", SCHEMA))
    switched = set(re.findall(r"THEN '([a-z0-9-]+)'", SCHEMA)) | set(re.findall(r"ELSE '([a-z0-9-]+)'", SCHEMA))
    assert seeded and switched
    assert seeded <= NAMES, seeded - NAMES
    assert switched <= NAMES, switched - NAMES


def test_brave_key_reaches_skills_only_when_route_is_auto() -> None:
    src = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    start = src.index("SKILL_ENV = {")
    block = src[start:src.index("\n\n", start)]
    assert "BRAVE_API_KEY" not in block, "Brave must not be in the always-on skill env"
    assert '_paid_route_mode.get(route) == "auto"' in src
    assert "env=skill_env()" in src
    schema = SCHEMA
    assert "CREATE TABLE IF NOT EXISTS tank.paid_routes" in schema
    assert "DEFAULT 'off'" in schema
