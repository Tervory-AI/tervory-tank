"""Code-only voice/feedback planning and durable Command confirmation binding."""
import json
import re
from contextvars import ContextVar
from uuid import UUID

from fastapi import HTTPException

CONFIRMED = ContextVar('trigger_confirmed_action', default=None)
VOICE_TOOLS = ['trigger.voice.show', 'trigger.voice.set', 'trigger.voice.rollback']
VOICE_PREFIX = re.compile(r'\s*trigger(?:\.voice\.|[, ]+voice[ .]+)(show|set|rollback)\b\s*:?[ \t]*(.*)', re.I | re.S)


async def plan(actor, text: str, task_id):
    from command import authorized_actor, require_tool, db, unpack
    match = VOICE_PREFIX.fullmatch(text)
    if match:
        actor = await authorized_actor(actor)
        op, source = match[1].lower(), match[2]
        tool = 'trigger.voice.' + op
        require_tool(actor, tool)
        if op == 'set':
            args = {'text': source}
        elif op == 'rollback':
            if not source.strip().isdigit():
                raise HTTPException(422, 'A voice version is required')
            args = {'target': int(source.strip())}
        elif re.fullmatch(r'version \d+', source.strip(), re.I):
            args = {'target': int(source.strip().split()[1])}
        else:
            if source.strip() and not source.strip().isdigit():
                raise HTTPException(422, 'History offset must be a number')
            args = {'offset': int(source.strip() or '0')}
        return {'text': '', 'actions': [{'tool': tool, 'arguments': args}]}
    match = re.fullmatch(r'\s*trigger[, .]+(accept|reject|changes)(?:\s+last draft)?\s*:?[ \t]*(.*)', text, re.I | re.S)
    if not match:
        return None
    actor = await authorized_actor(actor)
    require_tool(actor, 'trigger.feedback')
    async with db().acquire() as conn:
        raw = await conn.fetchval("SELECT state FROM tank.command_threads WHERE tenant_id=$1 AND user_id=$2 AND state->>'active_turn'=$3", actor.tenant_id, actor.user_id, str(task_id))
    cards = [c for c in unpack(raw or {}).get('cards', {}).values()
             if c.get('tool') == 'trigger.write' and c.get('status') == 'confirmed' and c.get('result', {}).get('write_id')]
    if not cards:
        raise HTTPException(404, 'Writing record unavailable')
    last = max(cards, key=lambda c: c.get('started_at', ''))
    status = {'accept': 'accepted', 'reject': 'rejected', 'changes': 'changes_requested'}[match[1].lower()]
    args = {'write_id': last['result']['write_id'], 'status': status, 'changes': match[2]}
    return {'text': '', 'actions': [{'tool': 'trigger.feedback', 'arguments': args}]}


async def prepare(action, actor, state):
    from command import PlannedAction, validate_action
    from trigger_routes import room
    args = dict(action.arguments)
    if action.tool in {'trigger.voice.set', 'trigger.voice.rollback'}:
        if action.tool.endswith('.set'):
            user_text = next((m['content'] for m in reversed(state['messages']) if m['role'] == 'user'), '')
            match = VOICE_PREFIX.fullmatch(user_text)
            source = match[2] if match and match[1].lower() == 'set' else user_text
            if args['text'].strip() != source.strip():
                raise HTTPException(422, 'Voice text must match the user source')
        preview = await room('voice/preview', {'tenant_id': str(actor.tenant_id), 'text': args.get('text', ''), 'target': args.get('target')})
        args.update(expected_revision=preview['expected_revision'], preview_hash=preview['preview_hash'],
                    brief_markdown=json.dumps(preview['voice'], ensure_ascii=False, indent=2))
    elif action.tool == 'trigger.feedback':
        args['brief_markdown'] = json.dumps({k: args[k] for k in ('write_id', 'status', 'changes')}, ensure_ascii=False)
    else:
        return action
    return validate_action(PlannedAction(tool=action.tool, arguments=args), actor)


async def dispatch_confirmed(action, actor, thread_id, card_id):
    from command import db, unpack, dispatch_action
    async with db().acquire() as conn:
        raw = await conn.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1 AND tenant_id=$2 AND user_id=$3', thread_id, actor.tenant_id, actor.user_id)
    card = unpack(raw or {}).get('cards', {}).get(str(card_id), {})
    if card.get('status') != 'executing' or card.get('payload') != action.model_dump(mode='json'):
        raise HTTPException(409, 'Confirmed action required')
    token = CONFIRMED.set((actor.tenant_id, actor.user_id, UUID(str(card_id)), action.tool, action.arguments))
    try:
        return await dispatch_action(action, actor)
    finally:
        CONFIRMED.reset(token)


def confirmation(actor, tool, body):
    bound = CONFIRMED.get()
    if not bound or bound[:2] != (actor.tenant_id, actor.user_id) or bound[3:] != (tool, body):
        raise HTTPException(409, 'Confirmed action required')
    return bound[2]
