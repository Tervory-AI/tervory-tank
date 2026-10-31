"""Every patch release (x.y.Z, Z > 0) of every skill keeps the code of x.y.(Z-1).

The older check in test_skala_eval_contract.py only covers a hand-written list
of skills and only the newest patch, so zenas.pii 1.1.2 changed detect.py and
still passed. This one walks tank/skills, so a new skill is covered the day it
lands. A code change needs a new minor version (x.Y.0).

"Code" here is every .py file (added, removed or changed) and skill.yaml apart
from its version line. CHANGELOG, docs, data files and evals may change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tank" / "skills"
_VERSION = re.compile(r"\d+\.\d+\.\d+")
_VERSION_LINE = re.compile(r'(?m)^\s*"?version"?\s*:.*$')

# Released before this check existed. Each entry must still differ in exactly
# these files, so the list cannot hide a new change.
KNOWN = {
    # Dropped an unused "import re"; behaviour is the same.
    ("base.socials", "1.0.1"): {"run.py"},
    # Approved on Boston on 31 Oct 2026 before this check; re-released as 1.2.0
    # with byte-identical code and cases. Kept on disk so the approved row
    # still has its package until 1.2.0 supersedes it.
    ("zenas.pii", "1.1.2"): {"detect.py"},
}


def _versions(skill: Path) -> dict[tuple[int, int, int], Path]:
    return {
        tuple(map(int, d.name.split("."))): d
        for d in skill.iterdir()
        if d.is_dir() and _VERSION.fullmatch(d.name)
    }


def _code(folder: Path) -> dict[str, bytes]:
    files = {
        f.relative_to(folder).as_posix(): f.read_bytes()
        for f in folder.rglob("*.py")
        if "__pycache__" not in f.parts
    }
    meta = folder / "skill.yaml"
    if meta.exists():
        files["skill.yaml"] = _VERSION_LINE.sub("", meta.read_text(encoding="utf-8")).encode()
    return files


def changed_code(old: Path, new: Path) -> set[str]:
    a, b = _code(old), _code(new)
    return {name for name in a.keys() | b.keys() if a.get(name) != b.get(name)}


def _patches() -> list[tuple[str, str, Path, Path]]:
    found = []
    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        versions = _versions(skill)
        for key, folder in sorted(versions.items()):
            if key[2] == 0:
                continue
            earlier = [k for k in versions if k[:2] == key[:2] and k < key]
            found.append((skill.name, folder.name, versions[max(earlier)] if earlier else None, folder))
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


def test_pii_1_2_0_is_1_1_2_under_the_right_number():
    pii = SKILLS / "zenas.pii"
    assert changed_code(pii / "1.1.2", pii / "1.2.0") == set()
    assert (pii / "1.1.2" / "evals" / "cases.jsonl").read_bytes() == (pii / "1.2.0" / "evals" / "cases.jsonl").read_bytes()


def test_rule_catches_a_changed_added_or_removed_file(tmp_path):
    old, new = tmp_path / "1.0.0", tmp_path / "1.0.1"
    for folder in (old, new):
        folder.mkdir()
        (folder / "run.py").write_text("x = 1\n")
        (folder / "skill.yaml").write_text("id: a.b\nversion: 1.0.0\nrung: 3\n")
    (new / "skill.yaml").write_text("id: a.b\nversion: 1.0.1\nrung: 3\n")
    (new / "CHANGELOG.md").write_text("notes\n")
    assert changed_code(old, new) == set()
    (new / "run.py").write_text("x = 2\n")
    assert changed_code(old, new) == {"run.py"}
    (new / "run.py").write_text("x = 1\n")
    (new / "extra.py").write_text("y = 1\n")
    assert changed_code(old, new) == {"extra.py"}
    (new / "extra.py").unlink()
    (new / "skill.yaml").write_text("id: a.b\nversion: 1.0.1\nrung: 1\n")
    assert changed_code(old, new) == {"skill.yaml"}
