"""Gate before (finish): diffs in and out instead of whole files (ENGINE_CODE_DIFFS_ENABLED).

In: when a file was read more than once in the results a client sends (its result
window keeps earlier rounds), only the latest read keeps the text; earlier copies
become a pointer. What changed between reads is already in the propose_edit diffs
in the same window, so the model sees each file once.

Out: the model is asked for minimal unified diffs. A whole-file rewrite (a hunk
replacing every line, or plain new content in `diff` with `path`) is turned into
the minimal diff against the client's latest read in this request. With no read to
diff against, the answer passes through unchanged (main's behaviour). When the
client reports that a diff could not apply, the model is told it may send the
complete file for that path, which Tank still sends on as a diff.
"""
from __future__ import annotations

import copy
import difflib
import json
import re

import code_finish

INSTRUCTION = ('Send every edit as a minimal unified diff against the file as last read (--- a/path, +++ b/path, '
               'exact context); never resend a whole file. An earlier copy of a re-read file is replaced by a pointer; '
               'the latest read has the current text.')
NO_NEWLINE = '\\ No newline at end of file'
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$')


def make(path: str, before: str, after: str) -> str:
    """Minimal unified diff in the exact form the CLI applies (a/ and b/ headers)."""
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    out = []
    for line in difflib.unified_diff(old, new, 'a/' + path, 'b/' + path, n=3):
        if line.endswith('\n'):
            out.append(line)
        else:
            out.extend([line + '\n', NO_NEWLINE + '\n'])
    return ''.join(out)


def parse(diff: str) -> list[dict] | None:
    """Files and hunks of a unified diff, counting hunk lines so content never reads as a header."""
    lines = diff.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
    files, index = [], 0
    while index < len(lines):
        if not (lines[index].startswith('--- ') and index + 1 < len(lines) and lines[index + 1].startswith('+++ ')):
            return None
        current = {'old': lines[index][4:], 'new': lines[index + 1][4:], 'hunks': []}
        files.append(current)
        index += 2
        while index < len(lines) and lines[index].startswith('@@'):
            match = HUNK.match(lines[index])
            if not match:
                return None
            a, b, c, d, rest = match.groups()
            hunk = {'a': int(a), 'b': int(b) if b is not None else 1, 'c': int(c), 'd': int(d) if d is not None else 1,
                    'rest': rest, 'lines': []}
            old, new = hunk['b'], hunk['d']
            index += 1
            while index < len(lines) and (old > 0 or new > 0 or lines[index] == NO_NEWLINE):
                line = lines[index]
                if line == NO_NEWLINE:
                    if not hunk['lines']:
                        return None
                    sign, text, _ = hunk['lines'][-1]
                    hunk['lines'][-1] = (sign, text, True)
                elif line[:1] == ' ' and old > 0 and new > 0:
                    hunk['lines'].append((' ', line[1:], False))
                    old, new = old - 1, new - 1
                elif line[:1] == '-' and old > 0:
                    hunk['lines'].append(('-', line[1:], False))
                    old -= 1
                elif line[:1] == '+' and new > 0:
                    hunk['lines'].append(('+', line[1:], False))
                    new -= 1
                else:
                    return None
                index += 1
            if old or new:
                return None
            current['hunks'].append(hunk)
        if not current['hunks']:
            return None
    return files or None


def render(files: list[dict]) -> str:
    out = []
    for item in files:
        out += ['--- ' + item['old'], '+++ ' + item['new']]
        for hunk in item['hunks']:
            out.append(f"@@ -{hunk['a']},{hunk['b']} +{hunk['c']},{hunk['d']} @@{hunk['rest']}")
            for sign, text, marker in hunk['lines']:
                out.append(sign + text)
                if marker:
                    out.append(NO_NEWLINE)
    return '\n'.join(out) + '\n'


def invert(diff: str) -> str:
    """The inverse of a unified diff that modifies existing files (no create or delete)."""
    files = parse(diff)
    if files is None:
        raise ValueError('Not a unified diff')
    flipped = []
    for item in files:
        hunks = []
        for hunk in item['hunks']:
            lines, block = [], []
            for entry in [*hunk['lines'], None]:
                if entry is not None and entry[0] != ' ':
                    block.append(entry)
                    continue
                lines += [('-', text, marker) for sign, text, marker in block if sign == '+']
                lines += [('+', text, marker) for sign, text, marker in block if sign == '-']
                block = []
                if entry is not None:
                    lines.append(entry)
            hunks.append({'a': hunk['c'], 'b': hunk['d'], 'c': hunk['a'], 'd': hunk['b'], 'rest': hunk['rest'], 'lines': lines})
        flipped.append({'old': item['old'], 'new': item['new'], 'hunks': hunks})
    return render(flipped)


def whole_rewrite(diff: str, base: str) -> str | None:
    """New text when a diff is one hunk replacing every line of the base, else None."""
    files = parse(diff)
    if not files or len(files) != 1 or len(files[0]['hunks']) != 1:
        return None
    lines = files[0]['hunks'][0]['lines']
    if any(sign == ' ' for sign, _, _ in lines):
        return None

    def text(side):
        chosen = [(body, marker) for sign, body, marker in lines if sign == side]
        if not chosen:
            return ''
        return '\n'.join(body for body, _ in chosen) + ('' if chosen[-1][1] else '\n')
    return text('+') if text('-') == base else None


def inbound(body, turn_id: str, timeline: list[dict], fresh: list[dict]) -> None:
    """Keep the latest read of each file; stash it as the base for diffs out."""
    reads = [item for item in timeline if item['kind'] == 'read']
    latest = {item['path']: item for item in reads}
    failed = {path for item in fresh if item['kind'] == 'edit' and item['applied'] == 'error' for path in item['files']}
    current = code_finish.stash()
    if current.get('turn') != turn_id:
        current = {'turn': turn_id}
        code_finish._STASH.set(current)
    current['bases'] = {path: item['text'] for path, item in latest.items()}
    if failed:
        current.setdefault('notes', []).append(
            'The diff for ' + ', '.join(sorted(failed)) + ' could not apply. Read the file again and, if a diff still '
            'cannot apply, send its complete new content in diff with path set.')
    stale = {item['index'] for item in reads if latest[item['path']] is not item}
    if not stale:
        return
    results = list(body.tool_results)
    for index in stale:
        arguments, _ = code_finish.envelope(results[index])
        pointer = {'arguments': arguments, 'result': {'exists': True, 'superseded': 'A later read of this file in these '
                                                      'results has its current text.'}}
        results[index] = results[index].model_copy(update={'output': json.dumps(pointer, ensure_ascii=False)})
    body.tool_results = results


def outbound(answer, bases: dict[str, str]):
    """Whole-file edits in the model's answer become minimal diffs against the latest read."""
    content = getattr(answer, 'content', None)
    if not isinstance(content, str) or not bases:
        return answer
    candidate = content.strip()
    fenced = candidate.startswith('```') and candidate.endswith('```')
    if fenced:
        candidate = candidate.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        decoded = json.loads(candidate)
    except (ValueError, RecursionError):
        return answer
    if not isinstance(decoded, dict) or not isinstance(decoded.get('requests'), list):
        return answer
    changed = False
    from code_preflight import norm
    for request in decoded['requests']:
        if not isinstance(request, dict) or request.get('name') != 'propose_edit' or not isinstance(request.get('arguments'), dict):
            continue
        arguments = request['arguments']
        diff = arguments.get('diff')
        if not isinstance(diff, str):
            continue
        if diff.startswith('--- '):
            files, whole = code_finish.diff_files(diff)
            if whole or len(files) != 1 or files[0] not in bases:
                continue
            path, after = files[0], whole_rewrite(diff, bases[files[0]])
        else:
            path = norm(arguments.get('path'))
            after = diff if path in bases else None
        if after is None or after == bases[path]:
            continue
        arguments['diff'] = make(path, bases[path], after)
        arguments.pop('path', None)
        changed = True
    if not changed:
        return answer
    shaped = json.dumps(decoded, ensure_ascii=False)
    if hasattr(answer, 'model_copy'):
        return answer.model_copy(update={'content': shaped})
    result = copy.copy(answer)
    result.content = shaped
    return result
