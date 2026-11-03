"""Every patch release (x.y.Z, Z > 0) of every skill keeps the code of the release before it.

The older check in test_skala_eval_contract.py only covers a hand-written list
of skills and only the newest patch, so zenas.pii 1.1.2 changed detect.py and
still passed. This one walks tank/skills, so a new skill is covered the day it
lands. A code change needs a new minor version (x.Y.0).

What "code" is lives in tank/skala_patch.py, which the approval gate
(skala.approval_reason) also uses: every file in the version folder (data
files included) except evals/, *.md notes and build output, with skill.yaml
compared without its version line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import skala
import skala_patch
from skala_patch import KNOWN, SUPERSEDED, changed_code, patch_refusal, previous_release, release

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tank" / "skills"


def _patches() -> list[tuple[str, str, Path | None, Path]]:
    found = []
    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        for folder in sorted(d for d in skill.iterdir() if d.is_dir() and release(d.name)):
            if release(folder.name)[2]:
                found.append((skill.name, folder.name, previous_release(folder), folder))
    return found


PATCHES = _patches()


def test_every_skill_is_walked():
    assert len(PATCHES) >= 30
    assert {"zenas.pii", "zenas.scope", "base.find_site"} <= {p[0] for p in PATCHES}


@pytest.mark.parametrize("skill,version,old,new", PATCHES, ids=[f"{p[0]}@{p[1]}" for p in PATCHES])
def test_patch_keeps_previous_code(skill, version, old, new):
    assert old is not None, f"{skill} {version} is a patch with no earlier {version.rsplit('.', 1)[0]}.x release"
    changed = changed_code(old, new)
    assert changed == KNOWN.get((skill, version), set()), (
        f"{skill} {version} changes {sorted(changed)} against {old.name}. "
        "A code change needs a new minor version (x.Y.0)."
    )


def test_known_exceptions_still_exist():
    names = {(p[0], p[1]) for p in PATCHES}
    assert set(KNOWN) <= names
    assert set(SUPERSEDED) <= set(KNOWN)


def test_gate_and_test_agree_on_every_shipped_patch():
    """The approval gate refuses exactly the superseded exception and nothing else on disk."""
    refused = {(s, v) for s, v, _old, new in PATCHES if patch_refusal(s, v, new)}
    assert refused == set(SUPERSEDED)


def test_pii_1_2_0_is_1_1_2_under_the_right_number():
    pii = SKILLS / "zenas.pii"
    assert changed_code(pii / "1.1.2", pii / "1.2.0") == set()
    assert (pii / "1.1.2" / "evals" / "cases.jsonl").read_bytes() == (pii / "1.2.0" / "evals" / "cases.jsonl").read_bytes()
    assert "approve 1.2.0 instead" in patch_refusal("zenas.pii", "1.1.2", pii / "1.1.2")
    assert patch_refusal("zenas.pii", "1.2.0", pii / "1.2.0") is None


def _skill(folder: Path, version: str, run: str = "x = 1\n") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "run.py").write_text(run)
    (folder / "skill.yaml").write_text(f"id: a.b\nversion: {version}\nrung: 3\n")
    return folder


def test_rule_catches_a_changed_added_or_removed_file(tmp_path):
    old, new = _skill(tmp_path / "1.0.0", "1.0.0"), _skill(tmp_path / "1.0.1", "1.0.1")
    (new / "CHANGELOG.md").write_text("notes\n")
    (new / "evals").mkdir()
    (new / "evals" / "cases.jsonl").write_text("{}\n")
    assert changed_code(old, new) == set()
    (new / "run.py").write_text("x = 2\n")
    assert changed_code(old, new) == {"run.py"}
    (new / "run.py").write_text("x = 1\n")
    (new / "extra.py").write_text("y = 1\n")
    assert changed_code(old, new) == {"extra.py"}
    (new / "extra.py").unlink()
    (new / "skill.yaml").write_text("id: a.b\nversion: 1.0.1\nrung: 1\n")
    assert changed_code(old, new) == {"skill.yaml"}


def test_data_files_count_as_code(tmp_path):
    old, new = _skill(tmp_path / "1.0.0", "1.0.0"), _skill(tmp_path / "1.0.1", "1.0.1")
    for folder in (old, new):
        (folder / "osv").mkdir()
        (folder / "osv" / "GHSA-1.json").write_text('{"affected": []}')
    assert patch_refusal("a.b", "1.0.1", new) is None
    (new / "osv" / "GHSA-1.json").write_text('{"affected": ["x"]}')
    assert changed_code(old, new) == {"osv/GHSA-1.json"}
    assert "osv/GHSA-1.json" in patch_refusal("a.b", "1.0.1", new)
    (new / "osv" / "GHSA-1.json").unlink()
    assert "osv/GHSA-1.json" in patch_refusal("a.b", "1.0.1", new)


def test_patch_compares_with_the_highest_earlier_release(tmp_path):
    _skill(tmp_path / "1.0.0", "1.0.0", "x = 0\n")
    _skill(tmp_path / "1.0.1", "1.0.1", "x = 0\n")
    _skill(tmp_path / "1.1.0", "1.1.0", "x = 1\n")
    new = _skill(tmp_path / "1.1.1", "1.1.1", "x = 1\n")
    assert previous_release(new) == tmp_path / "1.1.0"
    assert patch_refusal("a.b", "1.1.1", new) is None
    assert patch_refusal("a.b", "1.1.0", tmp_path / "1.1.0") is None  # x.Y.0 may change code
    lone = _skill(tmp_path / "other" / "2.0.3", "2.0.3")
    assert "no earlier 2.0.x release" in patch_refusal("a.b", "2.0.3", lone)


def test_known_exception_must_match_exactly(tmp_path, monkeypatch):
    _skill(tmp_path / "1.0.0", "1.0.0")
    new = _skill(tmp_path / "1.0.1", "1.0.1", "x = 2\n")
    monkeypatch.setitem(KNOWN, ("a.b", "1.0.1"), frozenset({"run.py"}))
    assert patch_refusal("a.b", "1.0.1", new) is None
    (new / "more.py").write_text("y = 1\n")
    assert "more.py" in patch_refusal("a.b", "1.0.1", new)
    assert skala_patch.KNOWN is KNOWN


def _staged(pkg):
    return {"state": "staging", "present": True, "version": pkg.version}


def test_approval_gate_refuses_a_patch_that_changes_code(tmp_path):
    """skala.approval_reason refuses before looking at any eval evidence."""
    root = tmp_path / "a.b"
    _skill(root / "1.0.0", "1.0.0")
    new = _skill(root / "1.0.1", "1.0.1", "x = 2\n")
    pkg = skala._parse_package(new / "skill.yaml", new)
    reason = skala.approval_reason(pkg, _staged(pkg), None, [], [])
    assert reason and "changes run.py against 1.0.0" in reason and "1.1.0" in reason
    (new / "run.py").write_text("x = 1\n")
    # Same code: the patch rule passes and the usual evidence rules apply.
    assert skala.approval_reason(pkg, _staged(pkg), None, [], []) != reason


def test_approval_gate_handles_the_shipped_exceptions():
    packages = skala.load_packages(SKILLS)
    for (skill, version) in KNOWN:
        pkg = packages[(skill, version)]
        reason = skala.approval_reason(pkg, _staged(pkg), None, [], [])
        if (skill, version) in SUPERSEDED:
            assert "instead" in reason
        else:
            assert "changes" not in (reason or "")
    # Already-approved rows are never re-decided: the older-or-equal check runs first.
    pii = packages[("zenas.pii", "1.1.2")]
    assert "older than or equal" in skala.approval_reason(pii, _staged(pii), {"version": "1.1.2"}, [], [])
