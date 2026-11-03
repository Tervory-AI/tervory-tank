"""Admin Command adapters and origin-bound public API. No widget or page copy."""
from __future__ import annotations

import hashlib
import json
import os
import re
from types import SimpleNamespace
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import command
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenant_db import tenant_scope
from trigger_bot import Bot, obj
from trigger_bot_grounding import exact_origin
from trigger_bot_shared import FailedKeyLimits, PgRateLimits, hash_key, issue_embed_key

router = APIRouter()
failed_keys = FailedKeyLimits()


class Args(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SourceAdd(Args):
    kind: Literal['website', 'rig', 'document']
    title: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    attachment_name: str | None = Field(default=None, max_length=200)
    document_draft_id: UUID | None = None
    expected_digest: str = ''

    @model_validator(mode='after')
    def source(self):
        if self.kind == 'website':
            parsed = urlsplit(self.url or '')
            if not exact_origin(f'{parsed.scheme}://{parsed.netloc}'):
                raise ValueError('https_source_required')
        elif self.url is not None:
            raise ValueError('unexpected_url')
        if self.kind == 'document' and not self.attachment_name:
            raise ValueError('attachment_required')
        return self


class SourceRemove(Args):
    source_id: UUID


class Contact(Args):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=50)

    @model_validator(mode='after')
    def validate_contact(self):
        if self.email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', self.email):
            raise ValueError('email')
        if self.phone and not re.fullmatch(r'[+()\d .-]{3,50}', self.phone):
            raise ValueError('phone')
        if not (self.email or self.phone):
            raise ValueError('contact_required')
        return self


class Ask(Args):
    text: str = Field(min_length=1, max_length=2000)
    contact: Contact | None = None
    quote_product_id: str | None = Field(default=None, max_length=64, pattern=r'^[A-Za-z0-9._-]+$')
    notice_version: str | None = Field(default=None, max_length=64)


class PublicMessage(Ask):
    conversation_id: UUID | None = None
    visitor_id: UUID | None = None

    @model_validator(mode='after')
    def existing(self):
        if self.conversation_id and not self.visitor_id:
            raise ValueError('visitor_required')
        return self


class FAQ(Args):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=8000)


class Feedback(Args):
    message_id: UUID
    status: Literal['good', 'bad']
    correct_answer: str | None = Field(default=None, max_length=8000)


class ConfirmDraft(Args):
    draft_id: UUID
    expected_digest: str = ''
    brief_markdown: str = Field(default='', max_length=16000)


TOOLS = {'source.add': SourceAdd, 'source.remove': SourceRemove, 'sources': Args,
         'ask': Ask, 'faq.add': FAQ, 'feedback': Feedback, 'review': Args, 'stats': Args,
         'lead.confirm': ConfirmDraft, 'quote.confirm': ConfirmDraft}


def runtime():
    import main
    return main


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def authority(actor, operation):
    actor = await command.authorized_actor(actor)
    if not (actor.founder or actor.tenant_admin):
        raise HTTPException(403, 'This tool is not available to this user')
    command.require_tool(actor, 'trigger.bot.' + operation)
    return actor


async def plan(actor, text, task_id):
    match = re.fullmatch(r'\s*(trigger\.bot\.([a-z.]+))\s*(?::\s*(.*))?\s*', text, re.S)
    if not match or match[2] not in TOOLS:
        return None
    await authority(actor, match[2])
    try:
        arguments = {'text': match[3]} if match[2] == 'ask' else json.loads(match[3] or '{}')
        action = command.validate_action(command.PlannedAction(tool=match[1], arguments=arguments), actor)
    except (ValueError, TypeError):
        raise HTTPException(422, 'The action arguments are invalid') from None
    from trigger_routes import code_receipt
    return SimpleNamespace(content=json.dumps({'text': '', 'actions': [action.model_dump(mode='json')]}),
                           ledger_id=await code_receipt(actor.tenant_id, 'command.turn', task_id=task_id))


async def prepare(action, actor, state):
    operation = action.tool.removeprefix('trigger.bot.')
    await authority(actor, operation)
    values = dict(action.arguments)
    pool = runtime().pool()
    if operation == 'source.add' and values['kind'] == 'document':
        attachments = [a for m in state['messages'] if m['role'] == 'user'
                       for a in m.get('attachments', []) if a.get('name') == values['attachment_name']]
        if not attachments:
            raise HTTPException(404, 'Attachment not found in this thread')
        attachment = attachments[-1]
        text = attachment.get('text')
        if not isinstance(text, str) and attachment.get('attachment_id'):
            text = await pool.fetchval('''SELECT convert_from(content,'UTF8') FROM tank.command_attachments
                WHERE tenant_id=$1 AND user_id=$2 AND attachment_id=$3 AND thread_id=$4''',
                actor.tenant_id, actor.user_id, UUID(attachment['attachment_id']), UUID(state['thread_id']))
        if not isinstance(text, str) or not text.strip() or len(text) > 200000:
            raise HTTPException(422, 'Attachment unavailable')
        data = {'text': text, 'user_id': actor.user_id}
        draft = uuid4()
        await pool.execute('''INSERT INTO tank.trigger_bot_drafts(tenant_id,id,kind,data)
            VALUES($1,$2,'document',$3::jsonb)''', actor.tenant_id, draft, json.dumps(data))
        values.update(document_draft_id=str(draft), expected_digest=digest(data))
    if operation.endswith('.confirm'):
        row = await pool.fetchrow('SELECT kind,data,state FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND id=$2',
                                  actor.tenant_id, UUID(values['draft_id']))
        if row is None or row['kind'] != operation.split('.')[0] or row['state'] != 'draft':
            raise HTTPException(404, 'Draft unavailable')
        data = obj(row['data'])
        values.update(expected_digest=digest(data), brief_markdown=json.dumps(data, ensure_ascii=False, indent=2))
    return command.validate_action(command.PlannedAction(tool=action.tool, arguments=values), actor)


async def key_for_site(bot, tenant, url):
    origin = '{0.scheme}://{0.netloc}'.format(urlsplit(url))
    await bot.pool.execute('''INSERT INTO tank.trigger_bot_config(tenant_id,enabled,origins)
        VALUES($1,true,$2::jsonb) ON CONFLICT(tenant_id) DO UPDATE SET enabled=true''', tenant, json.dumps([origin]))

    class KeyStore:
        async def put_key(self, owner, key_hash, kind, origins):
            await bot.pool.execute('''INSERT INTO tank.trigger_bot_embed_keys(tenant_id,key_hash,region,origins)
                VALUES($1,$2,$3,$4::jsonb)''', UUID(str(owner)), key_hash, bot.rt.box_region(), json.dumps(origins))
    value = await issue_embed_key(KeyStore(), str(tenant), [origin])
    return 'tb1.' + bot.rt.box_region() + '.' + tenant.hex + '.' + value['publishable_key']


async def execute(operation, args, actor, operation_id):
    bot, tenant = Bot(runtime()), actor.tenant_id
    pool = bot.pool
    if operation == 'source.add':
        content = ''
        if args.kind == 'document':
            row = await pool.fetchrow("SELECT data FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND id=$2 AND kind='document'", tenant, args.document_draft_id)
            data = obj(row['data']) if row else {}
            if data.get('user_id') != actor.user_id or digest(data) != args.expected_digest:
                raise HTTPException(409, 'Confirmed action required')
            content = data['text']
        if args.kind == 'rig' and not await bot.has_rig(tenant):
            raise HTTPException(403, 'Rig is not available for this tenant')
        source = await bot.sources.add(tenant, operation_id, args.kind, args.title, args.url, content)
        await pool.execute('''INSERT INTO tank.trigger_bot_config(tenant_id,enabled)
            VALUES($1,true) ON CONFLICT DO NOTHING''', tenant)
        try:
            await bot.sources.refresh(tenant, source, bot.rig_pages)
        except Exception:
            return {'source_id': str(source), 'status': 'unavailable'}
        result = {'source_id': str(source), 'status': 'ready'}
        if args.kind == 'website':
            result['embed_key'] = await key_for_site(bot, tenant, args.url)
        return result
    if operation == 'source.remove':
        await pool.execute("UPDATE tank.trigger_bot_sources SET status='removed' WHERE tenant_id=$1 AND id=$2", tenant, args.source_id)
        return {'source_id': str(args.source_id), 'status': 'removed'}
    if operation == 'sources':
        rows = await pool.fetch('''SELECT id,kind,title,url,status,checked_at FROM tank.trigger_bot_sources
            WHERE tenant_id=$1 ORDER BY title,id LIMIT 500''', tenant)
        return {'sources': [dict(row) for row in rows]}
    if operation == 'ask':
        return await ask(bot, tenant, args)
    if operation == 'faq.add':
        source = await bot.sources.add(tenant, operation_id, 'faq', args.question, content=json.dumps(args.model_dump()))
        await bot.sources.refresh(tenant, source)
        return {'source_id': str(source), 'status': 'approved'}
    if operation == 'feedback':
        row = await pool.fetchrow('''UPDATE tank.trigger_bot_messages SET feedback=$3 WHERE tenant_id=$1
            AND id=$2 RETURNING question,conversation_id''', tenant, args.message_id, args.status)
        if row is None:
            raise HTTPException(404, 'Message unavailable')
        draft = None
        if args.correct_answer:
            draft = uuid4()
            await pool.execute('''INSERT INTO tank.trigger_bot_drafts(tenant_id,id,conversation_id,kind,data)
                VALUES($1,$2,$3,'faq',$4::jsonb)''', tenant, draft, row['conversation_id'],
                json.dumps({'question': row['question'], 'answer': args.correct_answer}))
        return {'status': args.status, 'faq_draft_id': str(draft) if draft else None}
    if operation == 'review':
        rows = await pool.fetch('''SELECT id,conversation_id,question,answer,retrieved,cited,outcome,feedback
            FROM tank.trigger_bot_messages WHERE tenant_id=$1 AND (answer IS NULL OR feedback='bad')
            ORDER BY created_at DESC LIMIT 100''', tenant)
        return {'messages': [dict(row) for row in rows]}
    if operation == 'stats':
        rows = await pool.fetch('''SELECT date_trunc('week',created_at) AS week,
            count(*) FILTER(WHERE outcome='sources') AS answered_from_sources,
            count(*) FILTER(WHERE outcome='faq') AS faq_answers,
            count(*) FILTER(WHERE outcome='handed_over') AS handovers,
            count(*) FILTER(WHERE feedback='bad') AS bad_answers
            FROM tank.trigger_bot_messages WHERE tenant_id=$1 GROUP BY 1 ORDER BY 1 DESC LIMIT 52''', tenant)
        return {'weeks': [dict(row) for row in rows]}
    if operation.endswith('.confirm'):
        return await confirm_draft(bot, actor, operation, args, operation_id)
    raise HTTPException(404)


async def ask(bot, tenant, args, **session):
    result = await bot.ask(tenant, args.text, contact=args.contact.model_dump(exclude_none=True) if args.contact else None, **session)
    if args.quote_product_id and args.contact:
        active = await bot.pool.fetchval("SELECT 1 FROM tank.trigger_bot_sources WHERE tenant_id=$1 AND kind='rig' AND status='ready'", tenant)
        if active:
            product = await bot.rig_read(tenant, args.quote_product_id)
            if product.get('id') == args.quote_product_id:
                draft = uuid4()
                data = {'product_id': args.quote_product_id, 'contact': args.contact.model_dump(exclude_none=True),
                        'notice_version': args.notice_version}
                await bot.pool.execute('''INSERT INTO tank.trigger_bot_drafts(tenant_id,id,conversation_id,kind,data)
                    VALUES($1,$2,$3,'quote',$4::jsonb)''', tenant, draft, UUID(result['conversation_id']), json.dumps(data))
                result['quote_draft_id'] = str(draft)
    return result


async def confirm_draft(bot, actor, operation, args, operation_id):
    row = await bot.pool.fetchrow('''UPDATE tank.trigger_bot_drafts SET state='executing',operation_id=$3
        WHERE tenant_id=$1 AND id=$2 AND state='draft' AND kind=$4 RETURNING data''',
        actor.tenant_id, args.draft_id, operation_id, operation.split('.')[0])
    if not row:
        raise HTTPException(409, 'Draft unavailable')
    data = obj(row['data'])
    if digest(data) != args.expected_digest:
        raise HTTPException(409, 'Confirmed action required')
    try:
        if operation == 'lead.confirm':
            from trigger_crm import confirmed_bot_lead
            result = await confirmed_bot_lead(actor, args.draft_id, data)
        else:
            if not await bot.has_rig(actor.tenant_id):
                raise HTTPException(403, 'Rig is not available for this tenant')
            response = await bot.rt._rig_call('POST', '/internal/trigger/bot-quote',
                [('tenant_id', str(actor.tenant_id))], json.dumps({'tenant_id': str(actor.tenant_id),
                'home_region': bot.rt.box_region(), 'data': data}).encode(), timeout=60)
            if response.status_code != 200:
                raise HTTPException(503, 'Rig did not answer.')
            result = response.json()
        await bot.pool.execute("UPDATE tank.trigger_bot_drafts SET state='confirmed',result=$3::jsonb WHERE tenant_id=$1 AND id=$2", actor.tenant_id, args.draft_id, json.dumps(result))
        return {'draft_id': str(args.draft_id), 'state': 'confirmed'}
    except Exception:
        await bot.pool.execute("UPDATE tank.trigger_bot_drafts SET state='uncertain' WHERE tenant_id=$1 AND id=$2", actor.tenant_id, args.draft_id)
        raise


@router.post('/v1/trigger/bot/{operation}')
async def command_bot(operation: str, request: Request, actor: command.Actor = Depends(command.identity)):
    if operation not in TOOLS:
        raise HTTPException(404)
    actor = await authority(actor, operation)
    try:
        body = await bounded_body(request, 32000)
        if body.pop('tenant_id', str(actor.tenant_id)) != str(actor.tenant_id):
            raise HTTPException(403, 'Tenant mismatch')
        args = TOOLS[operation].model_validate(body)
    except (ValueError, TypeError):
        raise HTTPException(422, 'The action arguments are invalid') from None
    from trigger_commands import confirmation
    operation_id = confirmation(actor, 'trigger.bot.' + operation, args.model_dump(mode='json', exclude_none=True))
    result = await execute(operation, args, actor, operation_id)
    if 'ledger_id' not in result:
        result['ledger_id'] = str(await Bot(runtime()).receipt(actor.tenant_id, 'trigger.bot.' + operation))
    return result


async def bounded_body(request, cap):
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > cap:
            raise HTTPException(413)
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError('object_required')
    return body


async def authenticate(request):
    peer = request.client.host if request.client else 'unknown'
    reserved = failed_keys.reserve(peer)
    if reserved is None:
        raise HTTPException(429)
    key = request.headers.get('x-bot-key', '')
    match = re.fullmatch(r'tb1\.(us-east|za)\.([0-9a-f]{32})\.(rk_pub_[0-9a-f]{48})', key)
    origin = request.headers.get('origin', '')
    if not match or match[1] != runtime().box_region() or not exact_origin(origin):
        raise HTTPException(403)
    tenant = UUID(hex=match[2])
    with tenant_scope(tenant):
        row = await runtime().pool().fetchrow('''SELECT origins FROM tank.trigger_bot_embed_keys
            WHERE tenant_id=$1 AND key_hash=$2 AND region=$3 AND NOT revoked''', tenant, hash_key(match[3]), match[1])
    if row is None or origin not in obj(row['origins']):
        raise HTTPException(403)
    failed_keys.release(reserved)
    return tenant, origin, peer


@router.post('/v1/bot/messages')
async def public_message(request: Request):
    tenant, origin, peer = await authenticate(request)
    with tenant_scope(tenant):
        limited = await PgRateLimits(runtime().pool()).consume(str(tenant), peer, '/v1/rig/ask')
        if limited.retry_after:
            raise HTTPException(429, headers={'Retry-After': str(limited.retry_after)})
        try:
            args = PublicMessage.model_validate(await bounded_body(request, 16000))
        except (ValueError, TypeError):
            raise HTTPException(422) from None
        result = await ask(Bot(runtime()), tenant, args, conversation_id=args.conversation_id, visitor_id=args.visitor_id)
    # No model name, raw retrieval text, peer address or internal draft data.
    result = {k: v for k, v in result.items() if k not in {'retrieved', 'cited', 'outcome', 'notification'}}
    return JSONResponse(result, headers={'Access-Control-Allow-Origin': origin, 'Vary': 'Origin', 'Cache-Control': 'no-store'})
