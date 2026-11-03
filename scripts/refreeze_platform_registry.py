#!/usr/bin/env python3
"""Refreeze before final merge: run `prepare`, resolve any rebase conflicts, then `finish`.

Use the test virtualenv's Python. Never pushes. Keep the printed backup branch.
A new first commit freezes fetched main before replaying the existing move commits.
Finish refuses every snapshot drift except the authorized teachers tool/route/DDL.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HELPER = 'tests/test_registry_frozen.py'
GOLDEN = 'tests/registry_frozen.golden'


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def capture(root):
    spec = importlib.util.spec_from_file_location('platform_freeze', root / HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fresh_snapshot()


def without_teachers(registry):
    result = json.loads(json.dumps(registry))
    result['founder_tools'].remove('skala.teachers')
    result['adapters'] = [entry for entry in result['adapters'] if entry[0] != 'skala.teachers']
    result['dispatch'].pop('skala.teachers')
    result['allowed_tools']['founder'].remove('skala.teachers')
    prefix = 'Available tools and argument schemas: '
    separator = '\nUntrusted external MCP catalogue'
    head, tail = result['planning_message']['founder']['content'].split(prefix, 1)
    available, end = tail.split(separator, 1)
    args = json.loads(available)
    args.pop('skala.teachers')
    result['planning_message']['founder']['content'] = head + prefix + json.dumps(args, ensure_ascii=False) + separator + end
    result['routes'] = [row for row in result['routes'] if row['path'] != '/v1/training/teachers']
    sql = 'ALTER TABLE tank.training_pairs ADD COLUMN IF NOT EXISTS teacher_model text;\n'
    assert result['schema'].count(sql) == 1
    result['schema'] = result['schema'].replace(sql, '')
    return result


def finish():
    helper = (ROOT / HELPER).read_text()
    origin = re.search(r"ORIGIN_COMMIT = '([a-f0-9]+)'", helper).group(1)
    first = git('log', '--reverse', '--format=%H', '--diff-filter=A', origin + '..HEAD', '--', HELPER).splitlines()[0]
    baseline = json.loads(git('show', first + ':' + GOLDEN))
    assert baseline['origin_commit'] == origin
    current = capture(ROOT)
    normalized = without_teachers(current)
    different = [key for key in baseline['registry'] if normalized[key] != baseline['registry'][key]]
    assert not different, f'Current-main contracts changed: {different}; restore them before finishing'
    (ROOT / GOLDEN).write_text(json.dumps({'origin_commit': origin, 'registry': current}, indent=2) + '\n')
    subprocess.run([sys.executable, '-m', 'pytest', '-q', HELPER], cwd=ROOT, check=True)
    git('add', GOLDEN)
    if git('diff', '--cached', '--name-only'):
        git('commit', '-m', 'test: extend fresh main golden only for teachers read and provenance')
    print('Golden preserves current main plus the authorized teachers addition. Run focused regressions before pushing.')


def prepare():
    assert git('branch', '--show-current') == 'codex/platform-registry'
    assert not git('status', '--porcelain'), 'Commit changes before refreezing'
    helper = (ROOT / HELPER).read_text()
    previous = re.search(r"ORIGIN_COMMIT = '([a-f0-9]+)'", helper).group(1)
    backup = 'codex/platform-registry-before-refreeze-' + str(int(time.time()))
    git('branch', backup, 'HEAD')
    git('fetch', 'origin', 'main')
    origin = git('rev-parse', 'origin/main')
    with tempfile.TemporaryDirectory(prefix='platform-refreeze-') as folder:
        root = Path(folder) / 'main'
        git('worktree', 'add', '--detach', str(root), origin)
        try:
            (root / HELPER).write_text(helper.replace(previous, origin))
            snapshot = capture(root)
            (root / GOLDEN).write_text(json.dumps({'origin_commit': origin, 'registry': snapshot}, indent=2) + '\n')
            subprocess.run([sys.executable, '-m', 'pytest', '-q', HELPER], cwd=root, check=True)
            git('add', HELPER, GOLDEN, cwd=root)
            git('commit', '-m', f'test: freeze current main {origin[:8]} before registry extraction', cwd=root)
            freeze = git('rev-parse', 'HEAD', cwd=root)
        finally:
            git('worktree', 'remove', '--force', str(root))
    print(f'Backup: {backup}; new first freeze: {freeze}', flush=True)
    # Old golden-only updates are superseded. Product/move commits replay normally.
    commits = git('rev-list', '--reverse', origin + '..HEAD').splitlines()
    skip = []
    for commit in commits:
        files = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', commit).splitlines())
        if files and files <= {HELPER, GOLDEN, 'tests/registry_frozen.json'}:
            skip.append(commit)
    with tempfile.TemporaryDirectory(prefix='platform-sequence-') as folder:
        editor = Path(folder) / 'sequence.py'
        editor.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nimport sys\np=Path(sys.argv[1])\nskip=' + repr(skip) + '\np.write_text("\\n".join(line for line in p.read_text().splitlines() if not (line.startswith("pick ") and any(sha.startswith(line.split()[1]) for sha in skip)))+"\\n")\n')
        editor.chmod(0o700)
        import os
        env = {**os.environ, 'GIT_SEQUENCE_EDITOR': str(editor)}
        result = subprocess.run(['git', 'rebase', '-i', '--onto', freeze, origin], cwd=ROOT, env=env)
    if result.returncode:
        print('Resolve conflicts preserving current main, then git rebase --continue. For golden/helper conflicts keep the new first freeze version. Run this script finish after rebase.', file=sys.stderr)
        raise SystemExit(result.returncode)
    finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['prepare', 'finish'])
    args = parser.parse_args()
    (prepare if args.step == 'prepare' else finish)()
