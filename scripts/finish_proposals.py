"""Compile proposed Tank modules in memory; never modify Tank or vendor files."""
import hashlib
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


def proposals(tree, patch):
    result = {}
    for section in patch.read_text().split('diff --git ')[1:]:
        lines = section.splitlines(keepends=True)
        header = re.fullmatch(r'a/(tank/[\w]+\.py) b/\1\n', lines[0])
        if not header:
            raise ValueError('Finish patch must contain existing Tank Python modules')
        name = header[1]
        index = re.fullmatch(r'index ([0-9a-f]{40})\.\.([0-9a-f]{40}) 100644\n', lines[1])
        original = (tree / name).read_bytes()
        if not index or blob_hash(original) != index[1]:
            raise ValueError('Finish patch base differs: ' + name)
        source = original.decode().splitlines(keepends=True)
        output, cursor = [], 0
        for line in lines[4:]:
            if line.startswith('@@ '):
                hunk = re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@', line)
                if not hunk:
                    raise ValueError('Invalid patch hunk')
                start = int(hunk[1]) - 1
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


class ProposedModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, sources):
        self.sources = sources

    def find_spec(self, fullname, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.origin and str(Path(spec.origin).resolve()) in self.sources:
            return importlib.util.spec_from_file_location(fullname, spec.origin, loader=self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        filename = module.__spec__.origin
        source = self.sources[str(Path(filename).resolve())]
        linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
        exec(compile(source, filename, 'exec'), module.__dict__)


if os.environ.get('SKALA_FINISH_PATCH'):
    sys.meta_path.insert(0, ProposedModules(proposals(Path.cwd(), Path(os.environ['SKALA_FINISH_PATCH']))))
