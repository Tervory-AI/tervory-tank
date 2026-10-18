"""GET /v1/models reads the roster Tank already loads. Names and a missing-key flag only."""

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


def test_roster_names_follow_the_file_tank_loads_and_hide_the_key(tmp_path: Path) -> None:
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
    rows = main.roster_key_status(
        roster,
        {"OPENAI_API_KEY": SECRET, "GEMINI_API_KEY": "  "},
    )
    encoded = json.dumps(rows)
    assert [row["name"] for row in rows] == ["comet", "blanked", "planted"]
    assert rows[0]["key_missing"] is False
    assert rows[1]["key_missing"] is True
    assert rows[2]["key_missing"] is False
    assert SECRET not in encoded
    assert "OPENAI_API_KEY" not in encoded
    assert "GEMINI_API_KEY" not in encoded
    assert set(rows[0]) == {"name", "key_missing"}


def test_a_model_added_to_tanks_roster_shows_up_and_an_empty_key_is_missing(tmp_path: Path, monkeypatch) -> None:
    loaded = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    expected = [item["model_name"] for item in loaded["model_list"]]
    rows = main.roster_key_status(CONFIG, {})
    assert [row["name"] for row in rows] == expected
    assert rows and all(row["key_missing"] is True for row in rows)
    assert SECRET not in json.dumps(rows)

    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    data["model_list"].append(
        {"model_name": "nova", "litellm_params": {"model": "openai/nova", "api_key": "os.environ/OPENAI_API_KEY"}}
    )
    roster = tmp_path / "config.yaml"
    roster.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setenv("LITELLM_CONFIG", str(roster))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    live = main.roster_key_status()
    assert [row["name"] for row in live] == expected + ["nova"]
    assert live[-1]["key_missing"] is True
    assert "OPENAI_API_KEY" not in json.dumps(live)
