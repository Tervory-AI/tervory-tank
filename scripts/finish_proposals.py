"""Compile proposed Tank modules in memory; never modify Tank or vendor files."""
import hashlib
import difflib
import importlib.abc
import importlib.machinery
import importlib.util
import linecache
import os
from pathlib import Path
import re
import sys


def blob_hash(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def proposals(tree, patch, previous=None):
    result = {}
    for section in patch.read_text().split('diff --git ')[1:]:
        lines = section.splitlines(keepends=True)
        header = re.fullmatch(r'a/((?:tank|workspace)/[\w./-]+) b/\1\n', lines[0])
        if not header:
            raise ValueError('Patch must contain Tank or Workspace paths')
        name = header[1]
        if '..' in Path(name).parts:
            raise ValueError('Unsafe patch path')
        added = lines[1] == 'new file mode 100644\n'
        offset = 2 if added else 1
        index = re.fullmatch(r'index ([0-9a-f]{40})\.\.([0-9a-f]{40})(?: 100644)?\n', lines[offset])
        filename = str((tree / name).resolve())
        previous = previous or {}
        original = b'' if added else previous[filename].encode() if filename in previous else (tree / name).read_bytes()
        expected = '0' * 40 if added else blob_hash(original)
        if not index or expected != index[1] or (added and ((tree / name).exists() or filename in previous)):
            raise ValueError('Finish patch base differs: ' + name)
        source = original.decode().splitlines(keepends=True)
        output, cursor = [], 0
        for line in lines[offset + 3:]:
            if line.startswith('@@ '):
                hunk = re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@', line)
                if not hunk:
                    raise ValueError('Invalid patch hunk')
                start = max(0, int(hunk[1]) - 1)
                if start < cursor:
                    raise ValueError('Overlapping patch hunks')
                output.extend(source[cursor:start])
                cursor = start
            elif line.startswith((' ', '-')):
                if cursor >= len(source) or line[1:] != source[cursor]:
                    raise ValueError('Patch context differs: ' + name)
                if line[0] == ' ':
                    output.append(source[cursor])
                cursor += 1
            elif line.startswith('+'):
                output.append(line[1:])
            else:
                raise ValueError('Unsupported patch line')
        output.extend(source[cursor:])
        proposed = ''.join(output)
        if blob_hash(proposed.encode()) != index[2]:
            raise ValueError('Finish patch result differs: ' + name)
        result[str((tree / name).resolve())] = proposed
    if not result:
        raise ValueError('Empty finish patch')
    return result


def combine_proposals(tree, patches):
    """Combine independent hunks against the same pinned source in memory."""
    result = {}
    for patch in patches:
        for filename, proposed in proposals(tree, patch).items():
            if filename not in result:
                result[filename] = proposed
                continue
            base = Path(filename).read_text().splitlines(True) if Path(filename).exists() else []
            edits = []
            for source in (result[filename], proposed):
                lines = source.splitlines(True)
                for tag, start, end, lo, hi in difflib.SequenceMatcher(None, base, lines, autojunk=False).get_opcodes():
                    edit = (start, end, lines[lo:hi])
                    if tag != 'equal' and edit not in edits:
                        edits.append(edit)
            cursor, merged = 0, []
            for start, end, replacement in sorted(edits):
                if start < cursor:
                    raise ValueError('Conflicting Tank proposals: ' + filename)
                merged.extend(base[cursor:start])
                merged.extend(replacement)
                cursor = end
            merged.extend(base[cursor:])
            result[filename] = ''.join(merged)
    return result


class ProposedModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, sources):
        self.sources = sources

    def find_spec(self, fullname, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.origin and str(Path(spec.origin).resolve()) in self.sources:
            return importlib.util.spec_from_file_location(fullname, spec.origin, loader=self)
        if spec is None:
            for directory in path if path is not None else sys.path:
                filename = str((Path(directory) / (fullname.rsplit('.', 1)[-1] + '.py')).resolve())
                if filename in self.sources:
                    return importlib.util.spec_from_file_location(fullname, filename, loader=self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        filename = module.__spec__.origin
        source = self.sources[str(Path(filename).resolve())]
        linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
        exec(compile(source, filename, 'exec'), module.__dict__)


SOURCES = combine_proposals(Path.cwd(), [Path(os.environ[name]) for name in
    ('SKALA_FINISH_PATCH', 'SKALA_GATE4_PATCH') if os.environ.get(name)])
if os.environ.get('SKALA_GATE5_PATCH'):
    SOURCES.update(proposals(Path.cwd(), Path(os.environ['SKALA_GATE5_PATCH']), SOURCES))
if SOURCES:
    sys.meta_path.insert(0, ProposedModules(SOURCES))
