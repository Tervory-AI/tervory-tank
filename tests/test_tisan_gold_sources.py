"""Gold candidates must have real approval evidence, scoped to this room."""
import copy
import importlib.util
import json
from pathlib import Path
import secrets

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tisan_gold", ROOT / "agents/tisan/gold_sources.py")
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)


def record():
    frame = {"id": "2:11", "children": [{"text": "Example"}]}
    page = {"path": "/", "elements": [{"tag": "h1", "text": "Example"}]}
    return {"tenant_id": gold.PLATFORM_TENANT, "region": "us-east", "public": True,
            "non_client": True, "built": True, "frame": frame, "page_structure": page,
            "approval": {"role": "founder", "status": "approved", "reference": "review-1",
                         "frame_sha256": gold.digest(frame), "page_sha256": gold.digest(page)}}


def save(root, row, name="page.json"):
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(row))


def test_pairs_preserve_truth_and_deduplicate(tmp_path):
    row = record()
    save(tmp_path, row)
    save(tmp_path, row, "copy.json")
    pairs = gold.candidates(tmp_path, "us-east")
    assert [p["skill_id"] for p in pairs] == ["tisan.figma", "tisan.scaffold"]
    assert all(p["input"] == row["frame"] and p["expected"] == row["page_structure"] for p in pairs)
    assert set(pairs[0]) == {"skill_id", "input", "expected", "label_source", "region", "public"}
    assert "review-1" not in json.dumps(pairs)


@pytest.mark.parametrize("field,value", [("tenant_id", "another-tenant"), ("region", "za"),
    ("public", None), ("non_client", False), ("built", False), ("approval", {}),
    ("frame", {"changed": True}), ("page_structure", {"changed": True})])
def test_unapproved_stale_client_or_other_region_excluded(tmp_path, field, value):
    row = record()
    row[field] = value
    save(tmp_path, row)
    assert gold.candidates(tmp_path, "us-east") == []


def test_rejected_approval_and_invalid_files(tmp_path):
    row = copy.deepcopy(record())
    row["approval"]["status"] = "rejected"
    save(tmp_path, row)
    (tmp_path / "invalid.json").write_text("{")
    save(tmp_path, [], "array.json")
    assert gold.candidates(tmp_path, "us-east") == []


def test_caps_and_private_flag(tmp_path, monkeypatch):
    row = record()
    row["public"] = False
    save(tmp_path, row)
    monkeypatch.setenv("GOLD_AUTO_MAX", "1")
    assert len(gold.candidates(tmp_path, "us-east")) == 1
    assert gold.candidates(tmp_path, "us-east")[0]["public"] is False
    assert gold.candidates(tmp_path, "unknown") == []
    monkeypatch.setenv("GOLD_AUTO_MAX", "bad")
    assert gold.candidates(tmp_path, "us-east") == []


def test_endpoint_requires_room_key_and_limits(tmp_path, monkeypatch):
    key = secrets.token_hex(24)
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    save(tmp_path / "gold/approved-pages", record())
    app = FastAPI()
    gold.mount(app)
    client = TestClient(app)
    assert client.get("/gold/candidates").status_code == 401
    assert client.get("/gold/candidates", headers={"X-Tank-Key": secrets.token_hex(24)}).status_code == 401
    headers = {"X-Tank-Key": key}
    response = client.get("/gold/candidates?limit=1", headers=headers)
    assert response.status_code == 200 and len(response.json()) == 1
    assert key not in response.text
    for limit in ("0", "-1", "201", "bad"):
        assert client.get(f"/gold/candidates?limit={limit}", headers=headers).status_code == 422
    monkeypatch.delenv("TANK_KEY")
    assert client.get("/gold/candidates", headers=headers).status_code == 401
