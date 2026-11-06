"""Read proposed Tank source in memory; never apply a patch to the Tank clone."""
import os
from pathlib import Path
import re
import subprocess
import types


def source(name):
    integrated = Path(__file__).resolve().parents[2] / name
    if integrated.is_file():
        return integrated.read_text()
    project = Path(os.environ['TIGER_PROJECT_ROOT'])
    commit = (project/'vendor/tervory-tank/SOURCE').read_text().strip()
    original = subprocess.check_output(['git', '-C', os.environ['TANK_SOURCE_DIR'],
                                       'show', commit + ':' + name], text=True).splitlines(True)
    patch = (project/'tank-patches/finish.patch').read_text().splitlines(True)
    start = patch.index('+++ b/' + name + '\n') + 1
    end = next((i for i in range(start, len(patch)) if patch[i].startswith('--- a/')), len(patch))
    output, cursor, i = [], 0, start
    while i < end:
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*\n', patch[i])
        assert match, patch[i]
        position = int(match[1]) - 1
        assert position >= cursor
        output.extend(original[cursor:position])
        cursor, i = position, i + 1
        old_count, new_count = 0, 0
        while i < end and not patch[i].startswith('@@'):
            operation, line = patch[i][0], patch[i][1:]
            assert operation in ' +-'
            if operation in ' -':
                assert original[cursor] == line, (name, cursor)
                cursor += 1
                old_count += 1
            if operation in ' +':
                output.append(line)
                new_count += 1
            i += 1
        assert old_count == int(match[2] or 1) and new_count == int(match[4] or 1)
    return ''.join(output + original[cursor:])


def module(name):
    result = types.ModuleType('finish_' + Path(name).stem)
    result.__file__ = name
    exec(compile(source(name), name, 'exec'), result.__dict__)
    return result
