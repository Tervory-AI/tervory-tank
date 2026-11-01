"""tests/quarantine.txt may only shrink.

Every entry must be on ALLOWED below, so quarantining another test needs an
explicit, reviewed edit to this file as well (Tervory Review on #486, item 3).
Remove an id here in the PR that fixes the test and deletes its entry.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUARANTINE = ROOT / "tests" / "quarantine.txt"

# The 2 entries on main after #508 (5d954e96, 31 Oct 2026). Do not add ids. The PR
# that removes Docassemble deletes both entries and should drop them here too (a stale
# id here fails nothing: the check is only that every entry is on this list).
ALLOWED = frozenset({
    "tests/test_room_seal.py::test_no_room_service_would_leak_when_coolify_deploys_it[agents/zenas/docker-compose.docassemble.yml]",
    "tests/test_room_seal.py::test_no_room_service_would_leak_when_coolify_deploys_it[agents/zenas/docker-compose.docassemble.za.yml]",
})


def _lines() -> list[str]:
    if not QUARANTINE.exists():
        return []
    return [line for line in QUARANTINE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _entries() -> list[tuple[str, str, str]]:
    return [tuple(part.strip() for part in line.split("|", 2)) for line in _lines()]


def test_quarantine_entries_are_on_the_reviewed_allow_list():
    extra = sorted(node for node, _, _ in _entries() if node not in ALLOWED)
    assert not extra, (
        "tests/quarantine.txt has entries that are not on the allow-list in "
        f"tests/test_quarantine_rules.py: {extra}. Fix the test instead.")


def test_quarantine_entries_are_strict_xfail_with_a_reason():
    for line in _lines():
        parts = [part.strip() for part in line.split("|", 2)]
        assert len(parts) == 3 and parts[1] == "xfail" and parts[2], line
    nodes = [node for node, _, _ in _entries()]
    assert len(nodes) == len(set(nodes)), "duplicate quarantine entries"


def test_quarantine_entries_name_one_existing_test():
    """Each entry is an exact node id of a test function that exists, so it can
    never quarantine a whole file or class."""
    for node, _, _ in _entries():
        path, _, rest = node.partition("::")
        assert rest, f"{node}: not a test id (a file alone would quarantine every test in it)"
        source = ROOT / path
        assert source.is_file(), f"{node}: {path} does not exist"
        names = rest.split("[", 1)[0].split("::")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        scope = tree.body
        for name in names[:-1]:
            cls = next((n for n in scope if isinstance(n, ast.ClassDef) and n.name == name), None)
            assert cls is not None, f"{node}: no class {name} in {path}"
            scope = cls.body
        assert any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == names[-1]
                   and n.name.startswith("test") for n in scope), f"{node}: no test {names[-1]}"


@pytest.fixture
def root_conftest(pytestconfig):
    """tests/conftest.py as pytest loaded it. A bare `import conftest` can return
    a sub-folder's conftest, depending on which tests ran first in the worker."""
    want = ROOT / "tests" / "conftest.py"
    for plugin in pytestconfig.pluginmanager.get_plugins():
        if Path(getattr(plugin, "__file__", "") or "").resolve() == want:
            return plugin
    pytest.fail("tests/conftest.py is not loaded")


@pytest.mark.parametrize("bad", [
    "tests/test_room_seal.py | xfail | a whole file",
    "tests/test_room_seal.py::test_no_room_service_would_leak_when_coolify_deploys_it | skip | hidden",
    "tests/test_room_seal.py::test_no_room_service_would_leak_when_coolify_deploys_it | xfail |",
])
def test_conftest_rejects_file_entries_skip_mode_and_missing_reasons(bad, tmp_path, monkeypatch, root_conftest):
    conftest = root_conftest
    monkeypatch.setattr(conftest, "_QUARANTINE_FILE", tmp_path / "quarantine.txt")
    (tmp_path / "quarantine.txt").write_text(bad + "\n", encoding="utf-8")
    with pytest.raises(pytest.UsageError):
        conftest._quarantine()


def test_conftest_matches_exact_ids_only(root_conftest):
    conftest = root_conftest
    for node in conftest._QUARANTINE_BY_ID:
        assert conftest._quarantine_entry(node)
        assert conftest._quarantine_entry(node + "[x]") is None
        assert conftest._quarantine_entry(node + "::inner") is None
        assert conftest._quarantine_entry(node.split("::", 1)[0]) is None
