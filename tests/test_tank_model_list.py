"""GET /v1/models reads the roster Tank already loads. Names only."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import yaml

import main

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "litellm" / "config.yaml"
SECRET = "sk-live_secretvalue"


def test_roster_names_follow_the_file_and_hide_the_key(tmp_path: Path) -> None:
    roster = tmp_path / "config.yaml"
    roster.write_text(
        """
model_list:
  - model_name: comet
    litellm_params:
      api_key: os.environ/OPENAI_API_KEY
  - model_name: blanked
    litellm_params:
      api_key: os.environ/GEMINI_API_KEY
  - model_name: planted
    litellm_params:
      api_key: sk-live_secretvalue
""".strip()
        + "\n",
        encoding="utf-8",
    )
    rows = main.roster_names(roster)
    encoded = json.dumps(rows)
    assert rows == [{"name": "comet"}, {"name": "blanked"}, {"name": "planted"}]
    assert SECRET not in encoded
    assert "OPENAI_API_KEY" not in encoded
    assert "GEMINI_API_KEY" not in encoded
    assert "key_missing" not in encoded
    assert "Key is missing" not in encoded


def test_a_model_added_to_tanks_roster_shows_up(tmp_path: Path, monkeypatch) -> None:
    loaded = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    expected = [item["model_name"] for item in loaded["model_list"]]
    rows = main.roster_names(CONFIG)
    assert [row["name"] for row in rows] == expected
    assert all(set(row) == {"name"} for row in rows)
    assert SECRET not in json.dumps(rows)

    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    data["model_list"].append(
        {"model_name": "nova", "litellm_params": {"model": "openai/nova", "api_key": "os.environ/OPENAI_API_KEY"}}
    )
    roster = tmp_path / "config.yaml"
    roster.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setenv("LITELLM_CONFIG", str(roster))
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    live = main.roster_names()
    encoded = json.dumps(live)
    assert [row["name"] for row in live] == expected + ["nova"]
    assert SECRET not in encoded
    assert "OPENAI_API_KEY" not in encoded
    assert "key_missing" not in encoded
