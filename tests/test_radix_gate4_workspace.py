"""Compile/render the unapplied shared-page patch in a disposable directory."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def patched_sources():
    text = (ROOT / 'tank-patches/gate4.patch').read_text()
    result = {}
    for section in text.split('diff --git ')[1:]:
        lines = section.splitlines(keepends=True)
        name = next(line[6:].strip() for line in lines if line.startswith('+++ b/'))
        hunks = [i for i, line in enumerate(lines) if line.startswith('@@ ')]
        assert len(hunks) == 1, 'Patch fixtures must include full-file context'
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', lines[hunks[0]])
        assert match and match[1] in {'0', '1'} and match[3] == '1'
        before, after = [], []
        for line in lines[hunks[0] + 1:]:
            if line.startswith((' ', '-')): before.append(line[1:])
            if line.startswith((' ', '+')): after.append(line[1:])
        assert len(before) == int(match[2] or '1') and len(after) == int(match[4] or '1')
        result[name] = (''.join(before), ''.join(after))
    return result


def test_unapplied_patch_day_zero_charts_lists_and_receipts(tmp_path):
    sources = patched_sources()
    for name, (before, after) in sources.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if before: target.write_text(before)
    checked = subprocess.run(['git', 'apply', '--check', str(ROOT / 'tank-patches/gate4.patch')],
                             cwd=tmp_path, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    # Compile candidate bytes in this temporary tree; Tank/vendor stay untouched.
    for name, (_, after) in sources.items():
        (tmp_path / name).write_text(after)
    result = subprocess.run(['node', str(ROOT / 'tests/radix_gate4/workspace.cjs'), str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
