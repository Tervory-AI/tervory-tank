"""Trigger B1 runtime. Private tenant storage; one engine for visitors and Command."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import re
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from tenant_db import tenant_scope
from trigger_bot_engine import respond
from trigger_bot_grounding import Passage
from trigger_bot_sources import Sources
from trigger_bot_shared import SmtpMailer


def obj(value):
    return json.loads(value) if isinstance(value, str) else value


class Bot:
    def __init__(self, runtime):
        self.rt = runtime
        self.pool = runtime.pool()
        self.sources = Sources(self.pool, runtime.box_region())

    async def has_rig(self, tenant):
        return bool(await self.pool.fetchval("SELECT 1 FROM tank.tenant_squad WHERE tenant_id=$1 AND agent='rig'", tenant))

    async def rig_read(self, tenant, product_id=None, question=''):
        if not await self.has_rig(tenant):
            raise HTTPException(403, 'Rig is not available for this tenant')
        if product_id and not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', product_id):
            raise ValueError('product_id')
        path = '/v1/rig/products/' + product_id if product_id else '/v1/rig/search'
        params = [('tenant_id', str(tenant))]
        if not product_id:
            params += [('q', question[:200]), ('limit', '50')]
        response = self.rt._rig_response(await self.rt._rig_call('GET', path, params, None, timeout=30), tenant)
        if response.status_code != 200:
            raise ValueError('rig_unavailable')
        data = json.loads(response.body)
        return data.get('data', data)

    async def rig_pages(self, tenant, question):
        data = await self.rig_read(tenant, question=question)
        rows = data.get('results', [])
        return [self.product_page(row) for row in rows if isinstance(row, dict) and row.get('url') and row.get('id')]

    @staticmethod
    def product_page(row):
        # Copy only actual product facts. Never invent currency/price or a URL.
        fields = {k: row[k] for k in ('id', 'sku', 'name', 'brand', 'description', 'price', 'currency', 'stock', 'availability', 'attributes') if k in row}
        return {'text': json.dumps(fields, ensure_ascii=False, default=str), 'url': row['url'],
                'title': str(row.get('name') or row.get('sku') or row['id']),
                'sku': str(row.get('sku') or row['id']), 'product_id': str(row['id'])}

    async def retrieve(self, tenant, question):
        rig_source = await self.pool.fetchval("""SELECT id FROM tank.trigger_bot_sources WHERE tenant_id=$1
            AND kind='rig' AND status='ready' AND checked_at>now()-interval '7 days' LIMIT 1""", tenant)
        if rig_source is not None:
            # Query the actual catalogue for each question, not just an initial capped import.
            for page in await self.rig_pages(tenant, question):
                point = uuid5(rig_source, 'product:' + page['product_id'])
                await self.sources.index.put(tenant, self.rt.box_region(), point, page['text'])
                await self.pool.execute('''INSERT INTO tank.trigger_bot_passages
                    (tenant_id,id,source_id,text,url,title,kind,sku,product_id)
                    VALUES($1,$2,$3,$4,$5,$6,'rig',$7,$8) ON CONFLICT(tenant_id,id)
                    DO UPDATE SET text=EXCLUDED.text,url=EXCLUDED.url,title=EXCLUDED.title,sku=EXCLUDED.sku''',
                    tenant, point, rig_source, page['text'], page['url'], page['title'], page['sku'], page['product_id'])
        return await self.sources.search(tenant, question)

    async def live_rig(self, tenant, passage):
        row = await self.pool.fetchrow('''SELECT product_id FROM tank.trigger_bot_passages
            WHERE tenant_id=$1 AND id=$2 AND source_id=$3''', tenant, passage.id, passage.source_id)
        if not row or not row['product_id']:
            return None
        try:
            data = await self.rig_read(tenant, row['product_id'])
            page = self.product_page(data)
            if page['product_id'] != row['product_id']:
                return None
            return replace(passage, text=page['text'], url=page['url'], sku=page['sku'])
        except (ValueError, KeyError, HTTPException):
            return None

    async def voice(self, tenant):
        # Existing Trigger voice endpoint owns canonical storage and scope.
        from trigger_routes import room
        value = await room('voice', {'tenant_id': str(tenant)})
        return value.get('voice', value)

    async def route(self, tenant, messages):
        return await self.rt.run_route(self.rt.RouteRequest(tenant_id=tenant, agent='trigger',
            task_type='trigger.bot.answer', home_region=self.rt.box_region(),
            messages=[self.rt.Message(**m) for m in messages]))

    async def receipt(self, tenant, task):
        from trigger_routes import code_receipt
        return await code_receipt(tenant, task)

    async def ask(self, tenant, text, *, conversation_id=None, visitor_id=None, contact=None):
        visitor_id = visitor_id or uuid4()
        conversation_id = conversation_id or uuid4()
        config = await self.pool.fetchrow('SELECT * FROM tank.trigger_bot_config WHERE tenant_id=$1', tenant)
        if not config or not config['enabled']:
            raise HTTPException(409, 'Bot is not configured for this tenant')
        await self.pool.execute('''INSERT INTO tank.trigger_bot_conversations(tenant_id,id,visitor_id)
            VALUES($1,$2,$3) ON CONFLICT DO NOTHING''', tenant, conversation_id, visitor_id)
        async with self.pool.acquire() as conn, conn.transaction():
            conversation = await conn.fetchrow('''SELECT * FROM tank.trigger_bot_conversations
                WHERE tenant_id=$1 AND id=$2 AND visitor_id=$3 FOR UPDATE''', tenant, conversation_id, visitor_id)
            if conversation is None:
                raise HTTPException(404, 'Conversation unavailable')
            if conversation['status'] == 'bot':
                try:
                    result = await respond(tenant, text, retrieve=self.retrieve, route=self.route,
                                           live_rig=self.live_rig, receipt=self.receipt, voice=self.voice)
                except Exception:
                    result = {'state': 'handed_over', 'answer': None, 'sources': [], 'retrieved': [],
                              'cited': [], 'outcome': 'handed_over', 'ledger_id': str(await self.receipt(tenant, 'trigger.bot.answer'))}
            else:
                result = {'state': conversation['status'], 'answer': None, 'sources': [], 'retrieved': [],
                          'cited': [], 'outcome': 'handed_over', 'ledger_id': str(await self.receipt(tenant, 'trigger.bot.answer'))}
            message_id = uuid4()
            await conn.execute('''INSERT INTO tank.trigger_bot_messages
                (tenant_id,id,conversation_id,question,answer,retrieved,cited,outcome,ledger_id)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)''', tenant, message_id, conversation_id, text,
                result['answer'], [UUID(x) for x in result['retrieved']], [UUID(x) for x in result['cited']],
                result['outcome'], UUID(result['ledger_id']))
            await conn.execute('''UPDATE tank.trigger_bot_conversations SET status=$4,updated_at=now()
                WHERE tenant_id=$1 AND id=$2 AND visitor_id=$3''', tenant, conversation_id, visitor_id, result['state'])
        draft = await self.lead_draft(tenant, conversation_id, text, contact)
        result.update(message_id=str(message_id), conversation_id=str(conversation_id), visitor_id=str(visitor_id))
        if draft:
            result['lead_draft_id'] = str(draft)
        if result['state'] == 'handed_over':
            result['notification'] = await self.notify(tenant, conversation_id, config['handover_email'], text)
        return result

    async def lead_draft(self, tenant, conversation, text, contact):
        if not contact:
            # Explicit labels only; never infer a person's identity from prose.
            contact = dict((key.lower(), value.strip()) for key, value in re.findall(r'(?im)^(Name|Email|Phone):\s*([^\n]+)', text))
        if not contact or not contact.get('name') or not (contact.get('email') or contact.get('phone')):
            return None
        draft = uuid4()
        values = {'first_name': contact['name'], 'email': contact.get('email'), 'phone': contact.get('phone'),
                  'description': text, 'assigned_to': [], 'contacts': [], 'teams': []}
        await self.pool.execute('''INSERT INTO tank.trigger_bot_drafts(tenant_id,id,conversation_id,kind,data)
            VALUES($1,$2,$3,'lead',$4::jsonb)''', tenant, draft, conversation, json.dumps(values))
        return draft

    async def notify(self, tenant, conversation, recipient, text):
        # Claim before SMTP. Interrupted/uncertain sends are never automatically replayed.
        marker = uuid5(conversation, 'handover-mail')
        claimed = await self.pool.fetchval('''INSERT INTO tank.trigger_bot_drafts
            (tenant_id,id,conversation_id,kind,data,state) VALUES($1,$2,$3,'handover','{}','sending')
            ON CONFLICT DO NOTHING RETURNING id''', tenant, marker, conversation)
        if claimed is None:
            return 'already_claimed'
        status = 'unconfigured'
        sender = SmtpMailer.from_env()
        if sender is not None and recipient:
            try:
                await sender.send({'to': recipient, 'subject': 'trigger.bot.handover',
                                   'text': json.dumps({'conversation_id': str(conversation), 'question': text}, ensure_ascii=False)})
                status = 'sent'
            except Exception:
                status = 'uncertain'
        await self.pool.execute('UPDATE tank.trigger_bot_drafts SET state=$3 WHERE tenant_id=$1 AND id=$2', tenant, marker, status)
        return status


async def refresh_loop(runtime):
    while True:
        try:
            admin = runtime._admin_pool or runtime.pool()
            with tenant_scope(None, administrative=True):
                rows = await admin.fetch('''SELECT tenant_id,id FROM tank.trigger_bot_sources
                    WHERE status<>'removed' AND next_check<=now() ORDER BY next_check LIMIT 50''')
            for row in rows:
                with tenant_scope(row['tenant_id']):
                    bot = Bot(runtime)
                    try:
                        await bot.sources.refresh(row['tenant_id'], row['id'], bot.rig_pages)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # Retry maintenance later; never expose another tenant or search elsewhere.
        await asyncio.sleep(3600)
