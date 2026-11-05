"""Read a patch proposal in memory; never modify the Tank checkout or vendor."""
from pathlib import Path
import re
import os
import subprocess
ROOT = Path(__file__).resolve().parents[2]

def proposed_files():
    lines = (ROOT/'tank-patches/opli-agent.patch').read_text().splitlines(keepends=True)
    paths = [line[4:].strip().removeprefix('b/') for line in lines if line.startswith('+++ ')]
    assert all(not Path(path).is_absolute() and '..' not in Path(path).parts for path in paths)
    # After Tank sync, exercise the integrated files directly. Before sync,
    # reconstruct this proposal from the verified base without writing it.
    if (ROOT/'tank/code_sessions.py').is_file():
        return {path: (ROOT/path).read_text() for path in paths}
    result = {}; index = 0
    while index < len(lines):
        assert lines[index].startswith('--- ')
        old = lines[index][4:].strip(); new = lines[index+1][4:].strip(); index += 2
        path = new.removeprefix('b/')
        assert not Path(path).is_absolute() and '..' not in Path(path).parts
        if old == '/dev/null':
            original = []
        elif (ROOT/path).is_file():
            original = (ROOT/path).read_text().splitlines(keepends=True)
        else:
            sha = (ROOT/'tank-patches/SOURCE').read_text().strip()
            original = subprocess.check_output(['git', '-C', os.environ['TANK_SOURCE_REPO'], 'show', sha+':'+path], text=True).splitlines(keepends=True)
        output = []; cursor = 0
        while index < len(lines) and not lines[index].startswith('--- '):
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', lines[index]); assert match
            start, before, _, after = match.groups(); start = max(0, int(start)-1)
            before = int(before or 1); after = int(after or 1); index += 1
            output += original[cursor:start]; cursor = start; removed = added = 0
            while index < len(lines) and not lines[index].startswith(('@@ ', '--- ')):
                mark, content = lines[index][0], lines[index][1:]; index += 1
                if mark in (' ', '-'):
                    assert original[cursor] == content, (path, cursor)
                    cursor += 1; removed += 1
                if mark in (' ', '+'): output.append(content); added += 1
            assert (removed, added) == (before, after), path
        output += original[cursor:]; result[path] = ''.join(output)
    return result
