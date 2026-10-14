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


def test_fallbacks_name_roster_models_only() -> None:
    for entry in CONFIG["litellm_settings"]["fallbacks"]:
        for primary, chain in entry.items():
            assert primary in NAMES
            assert chain and all(name in NAMES for name in chain), primary
            assert primary not in chain


def test_policy_seeds_and_the_switch_name_roster_models() -> None:
    seeded = set(re.findall(r"\('[a-z0-9_.]+',\s*\d+,\s*'([a-z0-9-]+)'", SCHEMA))
    switched = set(re.findall(r"THEN '([a-z0-9-]+)'", SCHEMA)) | set(re.findall(r"ELSE '([a-z0-9-]+)'", SCHEMA))
    assert seeded and switched
    assert seeded <= NAMES, seeded - NAMES
    assert switched <= NAMES, switched - NAMES


def test_anthropic_names_fall_back_to_funded_providers() -> None:
    chains = {k: v for entry in CONFIG["litellm_settings"]["fallbacks"] for k, v in entry.items()}
    providers = {m["model_name"]: m["litellm_params"]["model"].split("/", 1)[0] for m in CONFIG["model_list"]}
    for name in ("haiku", "sonnet", "opus"):
        assert all(providers[n] != "anthropic" for n in chains[name]), name
