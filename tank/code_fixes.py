"""Gate before, items 2, 5 and 6: fixes without a model, diffs in and out, error-to-fix memory.

Every fix here is proposed as an ordinary local tool request (propose_edit or
run_command), so the client's existing validation, approval and undo still apply.
No model is selected or called from this module.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import uuid

import code_checks

log = logging.getLogger('tank.code_fixes')
MEMORY_TASK = 'command.code.fix'
MEMORY_PREFIX = 'spin-fix-v1 '
# Hermes keeps 1500 request and 3000 outcome characters of a receipt; a pair is
# only remembered when it is retained whole and can be verified by its digest.
MEMORY_OUTCOME_CHARS = 2800
MEMORY_LOOKUPS = 4
HEADER = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$')


class DiffError(ValueError):
    pass


# ---------------------------------------------------------------- unified diffs

def parse(diff: str) -> list[dict]:
    """The CLI's own unified-diff shape: --- a/p (or /dev/null), +++ b/p, exact hunks."""
    if not isinstance(diff, str) or not diff.endswith('\n'):
        raise DiffError('not a unified diff')
    lines = diff.split('\n')[:-1]
    files, i = [], 0
    while i < len(lines):
        old = re.fullmatch(r'--- (?:a/(.+)|(/dev/null))', lines[i])
        new = re.fullmatch(r'\+\+\+ b/(.+)', lines[i + 1]) if i + 1 < len(lines) else None
        if not old or not new or (old.group(1) and old.group(1) != new.group(1)):
            raise DiffError('not a unified diff')
        entry = {'path': new.group(1), 'created': bool(old.group(2)), 'hunks': []}
        i += 2
        while i < len(lines) and lines[i].startswith('@@'):
            match = HEADER.fullmatch(lines[i])
            if not match:
                raise DiffError('not a unified diff')
            start_old, count_old = int(match.group(1)), int(match.group(2) or 1)
            start_new, count_new = int(match.group(3)), int(match.group(4) or 1)
            body, before, after = [], count_old, count_new
            i += 1
            while before > 0 or after > 0:
                if i >= len(lines):
                    raise DiffError('not a unified diff')
                line = lines[i]
                if line[:1] == ' ':
                    before, after = before - 1, after - 1
                elif line[:1] == '-':
                    before -= 1
                elif line[:1] == '+':
                    after -= 1
                elif line != '\\ No newline at end of file':
                    raise DiffError('not a unified diff')
                if before < 0 or after < 0:
                    raise DiffError('not a unified diff')
                body.append(line)
                i += 1
            if i < len(lines) and lines[i] == '\\ No newline at end of file':
                body.append(lines[i])
                i += 1
            entry['hunks'].append({'old': (start_old, count_old), 'new': (start_new, count_new), 'lines': body})
        if not entry['hunks']:
            raise DiffError('not a unified diff')
        files.append(entry)
    if not files or len(files) > 20:
        raise DiffError('not a unified diff')
    return files


def render(files: list[dict]) -> str:
    out = []
    for entry in files:
        out += ['--- /dev/null' if entry['created'] else '--- a/' + entry['path'], '+++ b/' + entry['path']]
        for hunk in entry['hunks']:
            (a, b), (c, d) = hunk['old'], hunk['new']
            out.append(f'@@ -{a},{b} +{c},{d} @@')
            out += hunk['lines']
    return '\n'.join(out) + '\n'


def inverse(diff: str) -> str | None:
    """Undo one applied diff. A created file cannot be deleted by the client's edit tool."""
    files = parse(diff)
    if any(entry['created'] for entry in files):
        return None
    swapped = {'-': '+', '+': '-'}
    for entry in files:
        for hunk in entry['hunks']:
            if any(line.startswith('\\') for line in hunk['lines']):
                return None
            hunk['old'], hunk['new'] = hunk['new'], hunk['old']
            hunk['lines'] = [swapped.get(line[:1], line[:1]) + line[1:] for line in hunk['lines']]
    return render(files)


def _region_diff(old: list[str], new: list[str], start_old: int, start_new: int) -> list[dict] | None:
    hunks = []
    for group in difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(3):
        first, last = group[0], group[-1]
        i1, i2, j1, j2 = first[1], last[2], first[3], last[4]
        lines = []
        for tag, a1, a2, b1, b2 in group:
            if tag == 'equal':
                lines += [' ' + text for text in old[a1:a2]]
                continue
            lines += ['-' + text for text in old[a1:a2]]
            lines += ['+' + text for text in new[b1:b2]]
        count_old, count_new = i2 - i1, j2 - j1
        hunks.append({'old': (start_old + i1 if count_old else start_old + i1 - 1, count_old),
                      'new': (start_new + j1 if count_new else start_new + j1 - 1, count_new), 'lines': lines})
    return hunks


def minimal(diff: str) -> str:
    """A rewrite of unchanged lines (a whole file sent back) becomes its minimal diff."""
    files = parse(diff)
    for entry in files:
        if entry['created']:
            continue
        rebuilt = []
        for hunk in entry['hunks']:
            if any(line.startswith('\\') for line in hunk['lines']):
                rebuilt.append(hunk)
                continue
            old = [line[1:] for line in hunk['lines'] if line[:1] in ' -']
            new = [line[1:] for line in hunk['lines'] if line[:1] in ' +']
            start_old = hunk['old'][0] if hunk['old'][1] else hunk['old'][0] + 1
            start_new = hunk['new'][0] if hunk['new'][1] else hunk['new'][0] + 1
            rebuilt += _region_diff(old, new, start_old, start_new)
        entry['hunks'] = rebuilt
    files = [entry for entry in files if entry['hunks']]
    if not files:
        raise DiffError('the edit changes nothing')
    return render(files)


def whole_file_diff(path: str, before: str, after: str) -> str:
    if not before.endswith('\n') or not after.endswith('\n'):
        raise DiffError('a file without a final newline is not converted')
    old, new = before.split('\n')[:-1], after.split('\n')[:-1]
    entry = {'path': path, 'created': False, 'hunks': _region_diff(old, new, 1, 1)}
    if not entry['hunks']:
        raise DiffError('the edit changes nothing')
    return render([entry])


def reads(results) -> dict[str, str]:
    """The latest whole-file text the client read in this request, per path.

    A read followed by an applied edit to the same path is stale and dropped.
    """
    texts: dict[str, str] = {}
    for result in results:
        value = code_checks.tool_json(result.output)
        if value is None:
            continue
        arguments, inner = value.get('arguments'), value.get('result')
        if not isinstance(arguments, dict) or not isinstance(inner, dict):
            continue
        if result.name == 'read_file' and isinstance(arguments.get('path'), str) and inner.get('exists') is True \
                and isinstance(inner.get('text'), str):
            texts[arguments['path']] = inner['text']
        elif result.name == 'propose_edit' and isinstance(arguments.get('diff'), str):
            try:
                touched = [entry['path'] for entry in parse(arguments['diff'])]
            except DiffError:
                touched = list(texts)
            for path in touched:
                texts.pop(path, None)
    return texts


def diffs_in(results) -> list:
    """Code goes to the model as diffs: a file read again in the same request is
    sent as the diff from its earlier read, never as a second whole copy."""
    from types import SimpleNamespace
    seen: dict[str, str] = {}
    rows = []
    for result in results:
        value = code_checks.tool_json(result.output) if result.name == 'read_file' else None
        arguments = value.get('arguments') if value else None
        inner = value.get('result') if value else None
        path = arguments.get('path') if isinstance(arguments, dict) else None
        text = inner.get('text') if isinstance(inner, dict) and inner.get('exists') is True else None
        if not isinstance(path, str) or not isinstance(text, str):
            rows.append(result)
            continue
        if path in seen:
            try:
                change = whole_file_diff(path, seen[path], text) if seen[path] != text else ''
            except DiffError:
                change = None
            if change is not None and len(change) < len(text):
                seen[path] = text
                rows.append(SimpleNamespace(name='read_file', output=json.dumps(
                    {'arguments': arguments, 'result': {'exists': True, 'unchanged': change == '',
                     'diff_from_earlier_read': change}}, ensure_ascii=False)))
                continue
        seen[path] = text
        rows.append(result)
    return rows


def diffs_out(content: str, results) -> tuple[str, dict]:
    """Code comes back from the model as diffs. A whole-file reply is converted to
    its minimal diff where the earlier text is known, and refused otherwise."""
    try:
        plan = json.loads(content.strip().removeprefix('```json').removeprefix('```').removesuffix('```'))
    except (ValueError, RecursionError):
        return content, {'converted': 0}
    if not isinstance(plan, dict) or not isinstance(plan.get('requests'), list):
        return content, {'converted': 0}
    texts, converted = None, 0
    for request in plan['requests']:
        if not isinstance(request, dict) or request.get('name') != 'propose_edit' or not isinstance(request.get('arguments'), dict):
            continue
        arguments = request['arguments']
        diff = arguments.get('diff')
        if not isinstance(diff, str):
            continue
        try:
            parse(diff)
        except DiffError:
            # Not a diff at all: a whole file. Convert it against the read the
            # client sent in this request, or refuse it.
            texts = reads(results) if texts is None else texts
            path = arguments.get('path')
            if not isinstance(path, str) or path not in texts:
                raise
            arguments['diff'] = whole_file_diff(path, texts[path], diff)
            converted += 1
            continue
        else:
            try:
                smaller = minimal(diff)
            except DiffError:
                continue  # An edit that changes nothing is left for the client to refuse.
        if len(smaller) < len(diff):
            arguments['diff'] = smaller
            converted += 1
    if not converted:
        return content, {'converted': 0}
    return json.dumps(plan, ensure_ascii=False), {'converted': converted}


def issued_diffs(content: str) -> list[str]:
    try:
        plan = json.loads(content)
    except (ValueError, RecursionError):
        return []
    if not isinstance(plan, dict) or not isinstance(plan.get('requests'), list):
        return []
    return [request['arguments']['diff'] for request in plan['requests']
            if isinstance(request, dict) and request.get('name') == 'propose_edit'
            and isinstance(request.get('arguments'), dict) and isinstance(request['arguments'].get('diff'), str)]


def applied(results, issued: list[str]) -> list[str]:
    """Only diffs Tank itself issued (by digest), and the client reports applied, are trusted."""
    done = []
    for result in results:
        value = code_checks.tool_json(result.output) if result.name == 'propose_edit' else None
        if not value or not isinstance(value.get('arguments'), dict) or not isinstance(value.get('result'), dict):
            continue
        diff = value['arguments'].get('diff')
        if isinstance(diff, str) and hashlib.sha256(diff.encode()).hexdigest() in issued \
                and value['result'].get('applied') is True and diff not in done:
            done.append(diff)
    return done


# ------------------------------------------------------------ fixes without a model

IMPORT_UNUSED = re.compile(r"""^(?:F401|unused-import|W0611)$""")
IMPORT_NAME = re.compile(r"""['"`]([A-Za-z_][\w.]*)['"`]""")


def unused_import(error, texts: dict[str, str]) -> str | None:
    """Remove an unused single-name import line, exactly as reported, when its text is known."""
    if not IMPORT_UNUSED.fullmatch(error.code) or error.file not in texts or error.line < 1:
        return None
    text = texts[error.file]
    if not text.endswith('\n'):
        return None
    lines = text.split('\n')[:-1]
    if error.line > len(lines):
        return None
    line = lines[error.line - 1]
    named = IMPORT_NAME.search(error.message)
    if not named:
        return None
    name = named.group(1)
    single = re.fullmatch(r'import ' + re.escape(name) + r'(?: as \w+)?\s*', line) or \
        re.fullmatch(r'from [\w.]+ import ' + re.escape(name.rsplit('.', 1)[-1]) + r'(?: as \w+)?\s*', line)
    if not single:
        return None
    return render([{'path': error.file, 'created': False,
                    'hunks': [{'old': (error.line, 1), 'new': (error.line - 1, 0), 'lines': ['-' + line]}]}])


def deterministic(checks, results, tried: set[str]) -> tuple[list[dict], list[str]]:
    """Formatting, lint autofixes and import fixes, each tried once per error."""
    requests, fixed = [], []
    texts = None
    for check in checks or []:
        if check.passed:
            continue
        prints = [code_checks.fingerprint(check.kind, error) for error in check.errors]
        if check.kind in {'format', 'lint'} and check.fix_command and not set(prints) <= tried:
            requests.append({'name': 'run_command', 'arguments': {'command': check.fix_command}})
            fixed += prints
            continue
        for error, mark in zip(check.errors, prints):
            if mark in tried:
                continue
            texts = reads(results) if texts is None else texts
            diff = unused_import(error, texts)
            if diff:
                requests.append({'name': 'propose_edit', 'arguments': {'diff': diff}})
                fixed.append(mark)
    return requests[:6], fixed


# ------------------------------------------------------------ error-to-fix memory

def memory_key(kind, error) -> str:
    mark = code_checks.fingerprint(kind, error)
    return MEMORY_PREFIX + mark + '\n' + json.dumps([kind, error.file, error.code, code_checks.normal(error.message)[:600]],
                                                    ensure_ascii=False)


def memory_outcome(mark: str, diffs: list[str]) -> str | None:
    body = {'fix': MEMORY_PREFIX.strip(), 'fingerprint': mark,
            'requests': [{'name': 'propose_edit', 'arguments': {'diff': diff}} for diff in diffs]}
    body['digest'] = hashlib.sha256(json.dumps(body['requests'], sort_keys=True).encode()).hexdigest()
    text = json.dumps(body, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= MEMORY_OUTCOME_CHARS else None


def verified_fix(row: dict, tenant_id: str, user_id: str, mark: str) -> list[dict] | None:
    """A recalled claim is used only if it is this tenant's and user's exact pair."""
    if row.get('tenant_id') != tenant_id or row.get('kind', 'engine.outcome') != 'engine.outcome':
        return None
    meta = row.get('meta') if isinstance(row.get('meta'), dict) else {}
    if meta.get('task_type', MEMORY_TASK) != MEMORY_TASK or meta.get('user_id', user_id) != user_id:
        return None
    claim = row.get('claim', row.get('text'))
    if not isinstance(claim, str) or not claim.startswith('Request excerpt:\n' + MEMORY_PREFIX + mark + '\n'):
        return None
    _, separator, outcome = claim.partition('\nOutcome excerpt:\n')
    if not separator:
        return None
    try:
        body = json.loads(outcome)
    except (ValueError, RecursionError):
        return None
    if not isinstance(body, dict) or body.get('fingerprint') != mark or not isinstance(body.get('requests'), list):
        return None
    if hashlib.sha256(json.dumps(body['requests'], sort_keys=True).encode()).hexdigest() != body.get('digest'):
        return None
    requests = body['requests']
    if not 0 < len(requests) <= 6:
        return None
    for request in requests:
        if not isinstance(request, dict) or request.get('name') != 'propose_edit' or set(request) != {'name', 'arguments'} \
                or not isinstance(request['arguments'], dict) or set(request['arguments']) != {'diff'}:
            return None
        try:
            parse(request['arguments']['diff'])
        except DiffError:
            return None
    return requests


async def recall(actor, checks, tried: set[str]) -> tuple[list[dict], list[str]]:
    """Ask Tank's existing memory service (Hermes /engine/recall, signed user scope)."""
    import engine_memory
    import product_identity
    if not engine_memory.ENABLED.get():
        return [], []
    tenant = str(actor.tenant_id)
    with product_identity.actor_scope(actor):
        for kind, error in code_checks.failing(checks)[:64]:
            mark = code_checks.fingerprint(kind, error)
            if mark in tried:
                continue
            tried.add(mark)
            try:
                scope = engine_memory.user_scope(_Request(actor.tenant_id))
                found = await engine_memory.send('recall', {'tenant_id': tenant, 'task_type': MEMORY_TASK,
                                                            'query': memory_key(kind, error)[:1200], **scope})
                rows = found.get('memories') if isinstance(found, dict) else None
            except Exception as exc:  # Memory is an optimisation; any failure keeps the paid path.
                log.warning('Code fix memory unavailable (%s)', type(exc).__name__)
                return [], []
            for row in rows if isinstance(rows, list) else []:
                requests = verified_fix(row, tenant, actor.user_id, mark) if isinstance(row, dict) else None
                if requests:
                    return requests, [mark]
            if len(tried) >= MEMORY_LOOKUPS:
                break
    return [], []


class _Request:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


async def remember(command, actor, turn_id: str, pairs: list[dict]) -> int:
    """Store each fixed error with the diffs that fixed it, the way Tank stores any
    outcome: a $0 local receipt plus transcript, then Hermes /engine/remember."""
    import engine_memory
    import product_identity
    if not engine_memory.ENABLED.get() or not pairs:
        return 0
    mask = getattr(__import__('main'), '_storage_mask', None)
    region = __import__('main').box_region()
    stored = 0
    with product_identity.actor_scope(actor):
        for pair in pairs[:MEMORY_LOOKUPS]:
            outcome = memory_outcome(pair['fingerprint'], pair['diffs'])
            if outcome is None or not pair['key'].startswith(MEMORY_PREFIX + pair['fingerprint'] + '\n'):
                continue
            messages = [{'role': 'user', 'content': pair['key']}]
            masked = mask(messages) if mask else messages
            content = mask(outcome) if mask else outcome
            if content != outcome or masked != messages:
                continue  # Masked text would never verify; don't store a pair that can't be reused.
            ledger = uuid.uuid4()
            async with command.db().acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out,"
                        "task_id,cache_hit,outcome) VALUES($1,$2,$3,'orchestrator',$4,4,'cache:spin-fix-memory',0,0,0,$5,true,'delivered')",
                        ledger, actor.tenant_id, region, MEMORY_TASK, uuid.UUID(turn_id))
                    await conn.execute(
                        "INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content) VALUES($1,$2,$3,$4::jsonb,$5)",
                        ledger, actor.tenant_id, MEMORY_TASK, json.dumps(masked), content)
            from types import SimpleNamespace
            if await engine_memory.remember(_Request(actor.tenant_id), SimpleNamespace(ledger_id=ledger)):
                stored += 1
    return stored
