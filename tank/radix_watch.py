"""Explicit watch commands use code to propose the ordinary Confirm card."""
import json
import re

from fastapi import HTTPException


async def code_plan(actor, messages, task_id=None):
    last = messages[-1] if messages else {}
    if last.get('role') != 'user' or not re.match(r'\s*radix\.(?:deploy\.override|active\.scan|watch|unwatch|watches|changes)\b', last.get('content', ''), re.I):
        return None
    # Import only for Radix commands, so other turns never load main through this planner.
    from command import db, require_tool, unpack, validate_action, PlannedAction
    from main import RouteRequest, _record_local
    source = last
    if task_id:
        async with db().acquire() as conn:
            raw = await conn.fetchval('''SELECT state FROM tank.command_threads
              WHERE tenant_id=$1 AND user_id=$2 AND state->>'active_turn'=$3''',
              actor.tenant_id, actor.user_id, str(task_id))
        source = next((m for m in reversed(unpack(raw or {}).get('messages', [])) if m.get('role') == 'user'), last)
    match = re.fullmatch(r'\s*(radix\.(?:deploy\.override|active\.scan|watch|unwatch|watches|changes))\s*:?\s*(.*?)\s*', source.get('content', ''), re.I)
    if not match:
        raise HTTPException(422, 'The action arguments are invalid')
    tool, tail = match[1].lower(), match[2]
    require_tool(actor, tool)
    parts = tail.split()
    if tool == 'radix.deploy.override' and len(parts) == 2:
        args = {'app':parts[0], 'finding_id':parts[1]}
    elif tool == 'radix.active.scan' and len(parts) == 1:
        args = {'url': parts[0]}
    elif tool == 'radix.watch' and len(parts) in {2, 3} and (len(parts) == 2 or parts[2].lower() == 'now'):
        args = {'domain': parts[0], 'interval': parts[1].lower(), 'run_now': True}
    elif tool in {'radix.unwatch', 'radix.changes'} and len(parts) == 1:
        args = {'domain': parts[0]}
    elif tool == 'radix.watches' and not parts:
        args = {}
    else:
        raise HTTPException(422, 'The action arguments are invalid')
    action = validate_action(PlannedAction(tool=tool, arguments=args), actor)
    return await _record_local(RouteRequest(tenant_id=actor.tenant_id, agent='radix',
        task_type='command.turn', messages=[{'role': 'user', 'content': tool}]), {}, model='code', rung=3,
        content=json.dumps({'text': '', 'actions': [action.model_dump(mode='json')]}), task_id=task_id)
