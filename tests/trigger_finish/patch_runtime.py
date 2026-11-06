"""Compile the proposed Tank changes in memory; never alter either checkout."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def proposed_text(relative, original):
    if not (ROOT / 'vendor/tervory-tank').is_dir() and (ROOT / relative).is_file():
        return (ROOT / relative).read_text()
    original = original.splitlines(keepends=True)
    patch = (ROOT / 'tank-patches/finish.patch').read_text().splitlines(keepends=True)
    start = patch.index('+++ b/' + relative + '\n') + 1
    output, cursor = [], 0
    index = start
    while index < len(patch) and not patch[index].startswith('diff --git '):
        match = re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@', patch[index])
        assert match, patch[index]
        stop = int(match[1]) - 1
        output.extend(original[cursor:stop])
        cursor = stop
        index += 1
        while index < len(patch) and not patch[index].startswith(('@@ ', 'diff --git ')):
            marker, line = patch[index][0], patch[index][1:]
            if marker in ' -':
                assert original[cursor] == line, (relative, cursor + 1)
                cursor += 1
            if marker in ' +':
                output.append(line)
            index += 1
    output.extend(original[cursor:])
    return ''.join(output)


def patched(module, names):
    relative = 'tank/' + module.__name__ + '.py'
    tree = ast.parse(proposed_text(relative, Path(module.__file__).read_text()))
    nodes = [node for node in tree.body if getattr(node, 'name', None) in names]
    assert {node.name for node in nodes} == set(names)
    namespace = dict(vars(module))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), relative, 'exec'), namespace)
    return namespace
