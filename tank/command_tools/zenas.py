"""zenas command declarations; argument classes remain exported by command."""
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid')

class RetrieveArgs(Arguments):
    jurisdiction: Literal['us','za','both']
    query: str = Field(default='', max_length=24000)
    citation: str = Field(default='', max_length=1000)
    as_at: str | None = Field(default=None, max_length=10)

class ApplyArgs(Arguments):
    card_id: UUID
    features: dict[str, Any] = Field(default_factory=dict)
    question: str = Field(default='', max_length=24000)

class PlainArgs(Arguments):
    text: str = Field(min_length=1, max_length=24000)
    citations: list[str] = Field(default_factory=list, max_length=100)
    jurisdiction: Literal['us','za','both']


TOOLS = {'zenas': ['zenas.ask', 'zenas.matters', 'zenas.draft', 'zenas.review', 'zenas.playbook.add', 'zenas.playbooks', 'zenas.watch.add', 'zenas.watch.list', 'zenas.watch.enable', 'zenas.watch.disable']}
TOOLS['zenas'] += ['zenas.receipts', 'zenas.retrieve', 'zenas.apply', 'zenas.compose', 'zenas.plain']
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = frozenset([])
REQUEST_BODY_TOOLS = frozenset([])
CONFIRMED = frozenset(['zenas.draft', 'zenas.playbook.add'])

def adapters(command):
    return {
        'zenas.ask': command.Adapter('POST', '/v1/zenas/answers', command.ZenasAskArgs, 'Ask a civil law question', True, 'paid_run'),
        'zenas.matters': command.Adapter('POST', '/v1/zenas/matters', command.MatterArgs, 'Create a matter'),
        'zenas.draft': command.Adapter('POST', '/v1/zenas/drafts', command.ZenasDraftArgs, 'Draft a document', True, 'paid_run'),
        'zenas.playbook.add': command.Adapter('POST', '/v1/zenas/playbooks', command.ZenasPlaybookAddArgs, 'Add a review guide'),
        'zenas.playbooks': command.Adapter('GET', '/v1/zenas/playbooks', command.EmptyArgs, 'List review guides'),
        'zenas.watch.add': command.Adapter('POST', '/v1/zenas/regulations/watches', command.ZenasWatchAddArgs, 'zenas.watch.add'),
        'zenas.watch.list': command.Adapter('GET', '/v1/zenas/regulations/watches', command.EmptyArgs, 'zenas.watch.list'),
        'zenas.watch.enable': command.Adapter('POST', '/v1/zenas/regulations/watches/{watch_id}', command.ZenasWatchIdArgs, 'zenas.watch.enable'),
        'zenas.watch.disable': command.Adapter('POST', '/v1/zenas/regulations/watches/{watch_id}', command.ZenasWatchIdArgs, 'zenas.watch.disable'),
        'zenas.review': command.Adapter('POST', '/v1/zenas/contract-reviews', command.ReviewArgs, 'Review a contract', True, 'paid_run'),
        'zenas.receipts': command.Adapter('GET', '/v1/zenas/receipts', command.EmptyArgs, 'Receipts'),
        'zenas.retrieve': command.Adapter('POST', '/v1/zenas/ladder/retrieve', RetrieveArgs, 'Retrieve law'),
        'zenas.apply': command.Adapter('POST', '/v1/zenas/ladder/apply', ApplyArgs, 'Apply law', True, 'paid_run'),
        'zenas.compose': command.Adapter('POST', '/v1/zenas/ladder/compose', ApplyArgs, 'Compose memo', True, 'paid_run'),
        'zenas.plain': command.Adapter('POST', '/v1/zenas/ladder/plain', PlainArgs, 'Plain language', True, 'paid_run'),
    }


async def code_plan(actor,messages,task_id):
    import json
    import re
    from types import SimpleNamespace

    from fastapi import HTTPException
    if not messages or messages[-1].get('role')!='user':return None
    match=re.fullmatch(r'(zenas\.[a-z_.]+)(?:\s+(\{.*\}))?\s*',messages[-1].get('content','').strip(),re.DOTALL)
    if not match or match[1] not in TOOLS['zenas']:return None
    import command
    actor=await command.authorized_actor(actor)
    command.require_tool(actor,match[1])
    try:
        arguments=json.loads(match[2] or '{}')
        action=command.validate_action(command.PlannedAction(tool=match[1],arguments=arguments),actor)
    except (ValueError,TypeError):
        raise HTTPException(422,'Invalid command') from None
    from trigger_routes import code_receipt
    receipt=await code_receipt(actor.tenant_id,'command.turn',task_id=task_id,agent='zenas')
    return SimpleNamespace(content=json.dumps({'text':'','actions':[action.model_dump(mode='json')]}),ledger_id=receipt)
