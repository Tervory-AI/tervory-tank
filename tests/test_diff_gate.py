"""Diff gate (founder, 6 Nov 2026): one positive and one negative case per rule, offline."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diff_gate", ROOT / ".github/scripts/diff_gate.py")
gate = importlib.util.module_from_spec(spec)
sys.modules["diff_gate"] = gate
spec.loader.exec_module(gate)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "placeholder@example.invalid")
    _git(tmp_path, "config", "user.name", "placeholder")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _commit(repo: Path, files: dict[str, str | None]) -> str:
    for name, text in files.items():
        path = repo / name
        if text is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "change")
    return _git(repo, "rev-parse", "HEAD")


def _run(repo, before, after, unlocked=False):
    base = _commit(repo, before)
    head = _commit(repo, after)
    rep = gate.check(base, head)
    _, code = gate.receipt(rep, unlocked)
    return rep, code


def test_clean_change_passes(repo):
    rep, code = _run(repo, {"app/x.py": "a = 1\n"}, {"app/x.py": "a = 2\nb = 3\n"})
    assert code == 0 and not rep.blocks and not rep.unlockable


@pytest.mark.parametrize("line", ["import os  # noqa: F401", "x = f()  # type: ignore", "// @ts-ignore",
                                  "/* eslint-disable */"])
def test_suppressions_block(repo, line):
    name = "app/x.py" if line.startswith(("import", "x =")) else "web/x.ts"
    rep, code = _run(repo, {name: "a = 1\n"}, {name: f"a = 1\n{line}\n"})
    assert code == 1 and rep.blocks


def test_existing_suppression_is_not_flagged(repo):
    rep, code = _run(repo, {"app/x.py": "import os  # noqa: F401\n"}, {"app/x.py": "import os  # noqa: F401\nb = 1\n"})
    assert code == 0


def test_eval_exec_pickle_block_but_model_eval_passes(repo):
    rep, code = _run(repo, {"app/x.py": "a = 1\n"}, {"app/x.py": "a = 1\neval('1')\nexec('a=2')\nimport pickle\npickle.loads(b'')\n"})
    assert code == 1 and len([b for b in rep.blocks if "call" in b]) == 3
    rep, code = _run(repo, {"app/y.py": "m = None\n"}, {"app/y.py": "m = None\nm.eval()\nre_exec = 1\n"})
    assert code == 0


def test_wildcard_cors_and_extra_allow_block(repo):
    rep, code = _run(repo, {"app/x.py": "a = 1\n"},
                     {"app/x.py": "a = 1\nallow_origins=['*']\nmodel_config = ConfigDict(extra='allow')\n"})
    assert code == 1 and any("CORS" in b for b in rep.blocks) and any("extra" in b for b in rep.blocks)
    rep, code = _run(repo, {"app/y.py": "a = 1\n"}, {"app/y.py": "a = 1\nmodel_config = ConfigDict(extra='forbid')\n"})
    assert code == 0


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", ".gitleaks.toml", "hermes/auth.py",
                                  "agents/x/requirements.txt", "cli/package.json", "ops/seal-check.sh"])
def test_protected_files_need_the_founder(repo, path):
    rep, code = _run(repo, {path: "a\n"}, {path: "b\n"})
    assert code == 1 and rep.unlockable
    _, code = gate.receipt(rep, True)
    assert code == 0


def test_rls_lines_in_nested_schema_need_the_founder(repo):
    rep, code = _run(repo, {"agents/z/schema.sql": "CREATE TABLE t(a int);\n"},
                     {"agents/z/schema.sql": "CREATE TABLE t(a int);\nCREATE POLICY p ON t USING (true);\n"})
    assert code == 1
    rep, code = _run(repo, {"tank/schema.sql": "CREATE TABLE t(a int);\n"},
                     {"tank/schema.sql": "CREATE TABLE t(a int);\nCREATE INDEX i ON t(a);\n"})
    assert code == 0


def test_nested_compose_risks_block_but_plain_edits_pass(repo):
    rep, code = _run(repo, {"agents/zenas/docker-compose.za.yml": "services:\n  a:\n    image: x\n"},
                     {"agents/zenas/docker-compose.za.yml": "services:\n  a:\n    image: x\n    privileged: true\n    volumes:\n      - /var/run/docker.sock:/var/run/docker.sock\n"})
    assert code == 1 and any("privileged" in b for b in rep.blocks) and any("socket" in b for b in rep.blocks)
    rep, code = _run(repo, {"agents/tiger/docker-compose.yml": "services:\n  a:\n    image: x\n"},
                     {"agents/tiger/docker-compose.yml": "services:\n  a:\n    image: y\n    environment:\n      HF_TOKEN: ${HF_TOKEN}\n"})
    assert code == 0


def test_removed_hardening_needs_the_founder(repo):
    rep, code = _run(repo, {"agents/x/docker-compose.yml": "services:\n  a:\n    read_only: true\n    cap_drop: [ALL]\n"},
                     {"agents/x/docker-compose.yml": "services:\n  a:\n    image: x\n"})
    assert code == 1 and rep.unlockable


def test_adding_tests_passes_and_removing_an_assert_blocks(repo):
    before = "def test_a():\n    assert 1\n    assert 2\n"
    rep, code = _run(repo, {"tests/test_a.py": before}, {"tests/test_a.py": before + "\ndef test_b():\n    assert 3\n"})
    assert code == 0
    rep, code = _run(repo, {"tests/test_c.py": before}, {"tests/test_c.py": "def test_a():\n    assert 1\n"})
    assert code == 1 and any("asserts" in u for u in rep.unlockable)


def test_skip_only_and_loose_xfail_block_strict_xfail_passes(repo):
    base = "import pytest\n\ndef test_a():\n    assert 1\n"
    rep, code = _run(repo, {"tests/test_d.py": base}, {"tests/test_d.py": base + "\n@pytest.mark.skip\ndef test_b():\n    assert 1\n"})
    assert code == 1
    rep, code = _run(repo, {"tests/test_e.py": base}, {"tests/test_e.py": base + "\n@pytest.mark.xfail(reason='x')\ndef test_b():\n    assert 1\n"})
    assert code == 1
    rep, code = _run(repo, {"tests/test_f.py": base},
                     {"tests/test_f.py": base + "\n@pytest.mark.xfail(strict=True, reason='codex/hermes-user-scope')\ndef test_b():\n    assert 1\n"})
    assert code == 0
    rep, code = _run(repo, {"web/a.test.ts": "it('a', () => expect(1))\n"}, {"web/a.test.ts": "it.only('a', () => expect(1))\n"})
    assert code == 1


def test_deleting_a_test_file_needs_the_founder(repo):
    rep, code = _run(repo, {"tests/test_g.py": "def test_a():\n    assert 1\n"}, {"tests/test_g.py": None})
    assert code == 1 and any("deleted" in u for u in rep.unlockable)


def test_warnings_never_block(repo):
    rep, code = _run(repo, {"app/x.py": "a = 1\n"}, {"app/big.py": "x = 1\n" * 300})
    assert code == 0 and any("cap 250" in w for w in rep.warnings)


def test_workflow_unlock_trusts_only_the_founder_label():
    text = (ROOT / ".github/workflows/diff-gate.yml").read_text(encoding="utf-8")
    assert '.actor.login' in text and 'FOUNDER_UNLOCK=1' in text
    assert '"$who" = "$FOUNDER"' in text
    assert "labeled" in text and "unlabeled" in text
    assert "FOUNDER_UNLOCK" not in (ROOT / "scripts/precheck.sh").read_text(encoding="utf-8")
