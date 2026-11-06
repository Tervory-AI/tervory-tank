"""Exercise shared candidate code without applying patches to Tank or vendor."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from test_radix_gate4_workspace import patched_sources

ROOT = Path(__file__).resolve().parents[1]


def gate5_sources():
    result = {}
    for block in (ROOT/'tank-patches/gate5.patch').read_text().split('diff --git ')[1:]:
        lines = block.splitlines(keepends=True)
        name = next(line[6:].strip() for line in lines if line.startswith('+++ b/'))
        assert name.startswith('workspace/') and '..' not in Path(name).parts
        hunks = [i for i, line in enumerate(lines) if line.startswith('@@ ')]
        assert len(hunks) == 1
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', lines[hunks[0]])
        before = ''.join(line[1:] for line in lines[hunks[0]+1:] if line.startswith((' ', '-')))
        after = ''.join(line[1:] for line in lines[hunks[0]+1:] if line.startswith((' ', '+')))
        assert len(before.splitlines()) == int(match[2] or 1) and len(after.splitlines()) == int(match[4] or 1)
        result[name] = (before, after)
    return result


@pytest.fixture
def candidate(tmp_path):
    shutil.copytree(ROOT/'workspace', tmp_path/'workspace', ignore=shutil.ignore_patterns('node_modules'))
    (tmp_path/'workspace/node_modules').symlink_to((ROOT/'workspace/node_modules').resolve(), target_is_directory=True)
    loader = 'tests/command_acceptance_20261031/workspace_loader.cjs'
    (tmp_path/loader).parent.mkdir(parents=True)
    shutil.copyfile(ROOT/loader, tmp_path/loader)
    for name, (_, after) in patched_sources().items():
        target = tmp_path/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(after)
    sources = gate5_sources()
    for name, (before, after) in sources.items():
        target = tmp_path/name
        if before:
            # Product checks have the pinned source; after Tank sync the same
            # test runs beside the applied implementation. Verify either state,
            # then reconstruct the patch's base only in this disposable tree.
            assert target.read_text() in {before, after}, name
            target.write_text(before)
        elif target.exists():
            assert target.read_text() == after, name
            target.unlink()
    checked = subprocess.run(['git', 'apply', '--check', str(ROOT/'tank-patches/gate5.patch')], cwd=tmp_path, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    for name, (_, after) in sources.items():
        target = tmp_path/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(after)
    return tmp_path


def test_gate5_network_boundaries_auth_and_explicit_retry(candidate):
    result = subprocess.run(['node', str(ROOT/'tests/radix_gate5/boundaries.cjs'), str(candidate)], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_gate5_day_zero_first_request_result_receipt_mobile_keyboard(candidate):
    result = subprocess.run(['node', str(ROOT/'tests/radix_gate5/browser.cjs'), str(candidate)], cwd=ROOT, capture_output=True, text=True, timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
