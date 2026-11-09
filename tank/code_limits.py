"""Per-task code tool context bounds; summaries are local deterministic excerpts."""
from __future__ import annotations

import json
import asyncio
import os
import re

from fastapi import HTTPException
from anyio import CapacityLimiter, to_thread

SETTING = 'ENGINE_CODE_TOOL_LIMITS_ENABLED'
CAPS_SETTING = 'ENGINE_CODE_OUTPUT_CAPS_ENABLED'
LIMITER = CapacityLimiter(1)
WORKERS: set[asyncio.Task] = set()
LOCAL_SECONDS = 10
BINARY_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


class PreparationError(HTTPException):
    def __init__(self):
        super().__init__(503,'Local output preparation is busy. No model call was made.')


def enabled():
    return os.environ.get(SETTING, '').strip() == 'true'


def caps_enabled():
    return os.environ.get(CAPS_SETTING, '').strip() == 'true'


def serialize(rows):
    return json.dumps(rows, ensure_ascii=False, separators=(',', ':'))


DIAGNOSTIC = re.compile(r'\berror\b|\bfailed\b|\b\w*(?:Error|Exception)\b|^E |^Traceback|\b[A-Z]{1,5}[0-9]{2,5}\b',re.I)


def diagnostic_text(result):
    if result.name != 'run_command':
        return result.output
    try:
        envelope = json.loads(result.output)
    except (ValueError,RecursionError):
        return result.output
    if not isinstance(envelope,dict) or not isinstance(envelope.get('result'),dict):
        return result.output
    output = envelope['result'].get('output')
    if not isinstance(output,str):
        return result.output
    lines = output.splitlines()
    selected = set()
    for index,line in enumerate(lines):
        if DIAGNOSTIC.search(line):
            selected.update(range(max(0,index-1),min(len(lines),index+3)))
    if not selected:
        return result.output
    return '[local diagnostic lines with adjacent context; other text omitted]\n' + '\n'.join(lines[index] for index in sorted(selected))


def excerpt(encoding, tokens, keep):
    if len(tokens) <= keep:
        return encoding.decode(tokens)
    # Decode each edge independently so a cut through a Unicode character
    # drops only the incomplete character, never inventing replacement text.
    head = keep // 2
    first = encoding.decode_bytes(tokens[:head]).decode('utf-8', errors='ignore')
    last = encoding.decode_bytes(tokens[-(keep-head):]).decode('utf-8', errors='ignore') if keep > head else ''
    return first + '\n[local excerpt: middle omitted; request a narrower tool result]\n' + last


def envelope_result(output):
    try:
        envelope = json.loads(output)
    except (ValueError,RecursionError):
        return None
    if isinstance(envelope,dict) and isinstance(envelope.get('result'),dict):
        return envelope['result']
    return None


def summary_text(result):
    """Deterministic local summary per tool; no model. Unknown shapes keep diagnostics."""
    body = envelope_result(result.output)
    if body is None:
        return diagnostic_text(result)
    if result.name == 'run_command' and body.get('code') == 0 and isinstance(body.get('output'),str):
        lines = body['output'].splitlines()
        return (f'[local summary: command succeeded; {len(lines)} output lines; last lines follow]\n'
                + '\n'.join(lines[-SUMMARY_LINES:]))
    if result.name == 'list_files' and isinstance(body.get('files'),list):
        names = [name for name in body['files'] if isinstance(name,str)]
        folders = {}
        for name in names:
            folder = name.rsplit('/',1)[0] + '/' if '/' in name else './'
            folders[folder] = folders.get(folder,0) + 1
        return (f'[local summary: {len(names)} files in {len(folders)} folders]\n'
                + '\n'.join(f'{folder} {count}' for folder,count in sorted(folders.items())))
    if result.name == 'search' and isinstance(body.get('matches'),list):
        grouped = {}
        for match in body['matches']:
            if isinstance(match,dict) and isinstance(match.get('file'),str):
                grouped.setdefault(match['file'],[]).append(match)
        rows = []
        for name in sorted(grouped):
            hits = grouped[name]
            rows.append(f'{name}: {len(hits)} matches, lines ' + ','.join(str(hit.get('line')) for hit in hits[:SUMMARY_LINES]))
            rows.extend(f'  {hit.get("line")}: {str(hit.get("text",""))[:200]}' for hit in hits[:3])
        return f'[local summary: {sum(map(len,grouped.values()))} matches in {len(grouped)} files]\n' + '\n'.join(rows)
    if result.name == 'git' and isinstance(body.get('output'),str) and not body['output'].startswith('diff '):
        states = {}
        for line in body['output'].splitlines():
            states[line[:2].strip() or '?'] = states.get(line[:2].strip() or '?',0) + 1
        return '[local summary: changed files by status] ' + ', '.join(f'{state} {count}' for state,count in sorted(states.items()))
    return diagnostic_text(result)


SUMMARY_LINES = 20
TASK_TYPES = ('command.code.plan', 'command.code.fix', 'command.code.edit', 'command.code.explore', 'command.code.start')


def task_type(body):
    """Classify one code turn locally. The route task type stays command.code."""
    from code_gate import command_error
    if body.mode == 'plan':
        return 'command.code.plan'
    if any(result.name == 'run_command' and command_error(result.output) not in (None,'invalid-command-result')
           for result in body.tool_results):
        return 'command.code.fix'
    if any(result.name == 'propose_edit' for result in body.tool_results):
        return 'command.code.edit'
    return 'command.code.explore' if body.tool_results else 'command.code.start'


async def task_cap(tenant_id, kind):
    """The task type's tenant/platform max_tokens_out, else command.code's. Never a model choice."""
    from main import load_policy
    try:
        policy = await load_policy(kind,tenant_id)
    except HTTPException as error:
        if error.status_code != 404:
            raise
        policy = await load_policy('command.code',tenant_id)
    limit = policy.get('max_tokens_out')
    if type(limit) is not int or limit < 1:
        raise HTTPException(422, 'This task needs a positive tool-output token limit.')
    return limit


async def offload(work):
    """Run local CPU work on the shared single preparation slot, as context() does."""
    owner = object()
    await LIMITER.acquire_on_behalf_of(owner)
    worker = asyncio.create_task(run_work(work,owner,LIMITER))
    WORKERS.add(worker)
    worker.add_done_callback(finished)
    return await asyncio.shield(worker)


async def run_work(work, owner, limiter):
    try:
        return await to_thread.run_sync(work)
    finally:
        limiter.release_on_behalf_of(owner)


def render(results, limit, encoding, summarize=False):
    if type(limit) is not int or limit < 1:
        raise HTTPException(422, 'This task needs a positive tool-output token limit.')
    if any(BINARY_CONTROL.search(result.output) for result in results):
        raise HTTPException(422,'Request text diagnostics instead of binary tool output.')
    rows = [{'name': result.name, 'output': result.output} for result in results]
    original = json.dumps(rows, ensure_ascii=False)
    before = len(encoding.encode(original))
    if before <= limit:
        return original, {'tokens_before':before, 'tokens_after':before, 'limit':limit, 'summarized':False}
    vectors = [encoding.encode(summary_text(result) if summarize else diagnostic_text(result)) for result in results]
    keep = max(1, limit // max(1,len(rows)))
    while keep:
        shortened = serialize([{'name':row['name'], 'output':excerpt(encoding,tokens,keep)}
                               for row,tokens in zip(rows,vectors)])
        after = len(encoding.encode(shortened))
        if after <= limit:
            return shortened, {'tokens_before':before, 'tokens_after':after, 'limit':limit, 'summarized':True}
        keep //= 2
    # A cap smaller than the structural envelope is not a reason to spend.
    raise HTTPException(422, 'The local tool result envelope exceeds this task token limit. Request fewer or narrower results.')


def prepare(results, limit):
    from agent_skills import input_encoding
    from code_sessions import code_text
    from types import SimpleNamespace
    cleaned = [SimpleNamespace(name=result.name, output=ANSI.sub('',code_text(result.output))) for result in results]
    return render(cleaned,limit,input_encoding())


async def context(tenant_id, task_type, results):
    from main import load_policy
    # Reuse the existing tenant override and task policy; no model is selected.
    # Tank still enforces min(request.max_tokens, policy.max_tokens_out).
    try:
        async with asyncio.timeout(LOCAL_SECONDS):
            policy = await load_policy(task_type,tenant_id)
            owner = object()
            await LIMITER.acquire_on_behalf_of(owner)
            # The request may time out or disconnect while native tokenization
            # continues. Only that worker may release its slot. Queued requests
            # are cancellable before creating a worker, so they cannot pile up
            # abandoned CPU jobs behind it.
            worker = asyncio.create_task(run_preparation(results,policy.get('max_tokens_out'),owner,LIMITER))
            WORKERS.add(worker)
            worker.add_done_callback(finished)
            return await asyncio.shield(worker)
    except TimeoutError:
        raise PreparationError() from None


async def run_preparation(results, limit, owner, limiter):
    try:
        return await to_thread.run_sync(prepare,results,limit)
    finally:
        limiter.release_on_behalf_of(owner)


def finished(worker):
    WORKERS.discard(worker)
    # If the caller already received a safe timeout, consume a later local
    # exception without logging private source or diagnostics.
    if not worker.cancelled():
        worker.exception()
