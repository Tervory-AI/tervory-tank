"""Persisted owner preferences must win by creation time, regardless of list order."""
import pytest

from command_tools._workspace import gates_memory as deployed
from integrations.workspace import gates_memory as source


@pytest.mark.parametrize("memory", [source, deployed], ids=["source", "deployed"])
@pytest.mark.parametrize("ordering", ["oldest-first", "newest-first", "legacy"])
def test_latest_owner_preference_controls_off_edit_off(memory, ordering):
    rows = []
    for index, control in enumerate(("off", "edit", "off"), start=1):
        row = {
            "kind": memory.CONTROL_KIND,
            "text": "placeholder owner preference",
            "meta": {"control": control},
        }
        if ordering != "legacy":
            row["created_at"] = f"2026-11-08T00:00:0{index}+00:00"
        rows.append(row)
        supplied = list(reversed(rows)) if ordering == "newest-first" else list(rows)
        assert memory.memory_control_from_memories(supplied) == control


def test_preference_runtime_mirror_matches_source():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    expected = (root / "integrations/workspace/gates_memory.py").read_text().replace(
        "integrations.workspace.memory_client", "command_tools._workspace.memory_client"
    )
    assert expected == (
        root / "tank/command_tools/_workspace/gates_memory.py"
    ).read_text()
