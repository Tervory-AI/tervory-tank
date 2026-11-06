"""Compile/render the unapplied shared-page patch in a disposable directory."""
from pathlib import Path
import re
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[1]


def patched_sources():
    text = (ROOT / 'tank-patches/radix/gate4.patch').read_text()
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


def verify_patch(folder, relative, sources):
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(folder)], check=True)
    for name, (before, after) in sources.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if before:
            target.write_text(before)
            assert target.read_text() in {before, after}, name
        else:
            target.unlink(missing_ok=True)
    checked = subprocess.run(['git', 'apply', '--check', str(ROOT / relative)],
                             cwd=folder, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    applied = subprocess.run(['git', 'apply', str(ROOT / relative)], cwd=folder,
                             capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr
    for name, (_, after) in sources.items():
        assert (folder/name).read_text() == after, name


def test_unapplied_patch_day_zero_charts_lists_and_receipts(tmp_path):
    verify_patch(tmp_path/'patch-proof', 'tank-patches/radix/gate4.patch', patched_sources())
    # Browser assertions exercise the integrated production implementation.
    shutil.copytree(ROOT/'workspace', tmp_path/'workspace',
                    ignore=shutil.ignore_patterns('node_modules', '.next'))
    result = subprocess.run(['node', str(ROOT / 'tests/radix_gate4/workspace.cjs'), str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
