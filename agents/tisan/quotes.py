"""Tenant-bound quote requests. Submission itself records tacit approval.

Only structured contact/item identifiers are accepted; there is no arbitrary
payload, payment data, customer notes, or email copy supplied by callers.
"""
from __future__ import annotations

import asyncio
import json
import smtplib
import socket
from email.headerregistry import Address
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

State = Literal['draft', 'submitted', 'acknowledged', 'quoted', 'accepted', 'declined']
MOVES = {
    'draft': {'submitted'}, 'submitted': {'acknowledged'},
    'acknowledged': {'quoted'}, 'quoted': {'accepted', 'declined'},
    'accepted': set(), 'declined': set(),
}
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] if _HERE.name == 'tisan' else _HERE
EMAIL_WORDING = _ROOT / 'docs/figma/tisan/QUOTE-EMAILS.md'


class Refused(ValueError):
    """Invalid state move; no write was made."""


class Missing(LookupError):
    """No request in the supplied tenant."""


class Contact(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    email: str = Field(min_length=3, max_length=254)

    @field_validator('email')
    @classmethod
    def email_address(cls, value: str) -> str:
        if any(c in value for c in '\r\n'):
            raise ValueError('invalid_email')
        address = Address(addr_spec=value)
        if not address.username or not address.domain or address.addr_spec != value:
            raise ValueError('invalid_email')
        return value


class Item(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    item_id: UUID = Field(strict=False)
    quantity: int = Field(ge=1, le=10000)


class RequestData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contact: Contact
    items: list[Item] = Field(min_length=1, max_length=100)


class Create(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    data: RequestData


class Move(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    state: State


def transition(before: str, after: str) -> None:
    if after not in MOVES.get(before, set()):
        raise Refused('invalid_transition')


def identity(tenant_id: UUID | str, actor: str) -> UUID:
    tenant = UUID(str(tenant_id))
    if not actor.strip() or len(actor) > 256 or any(c in actor for c in '\r\n'):
        raise Refused('invalid_actor')
    return tenant


class Quotes:
    def __init__(self, pool: Any):
        self.pool = pool

    async def create(self, tenant_id: UUID | str, actor: str, data: Any,
                     *, submitted: bool = False) -> dict:
        tenant = identity(tenant_id, actor)
        # Revalidate even when called without the HTTP models.
        payload = RequestData.model_validate(data).model_dump(mode='json')
        request_id = uuid4()
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow('''INSERT INTO agent_tisan.quote_requests
                (tenant_id,id,contact,items,state) VALUES ($1,$2,$3::jsonb,$4::jsonb,'draft') RETURNING *''',
                tenant, request_id, json.dumps(payload['contact']), json.dumps(payload['items']))
            await self._event(conn, tenant, request_id, None, 'draft', actor)
            if submitted:
                row = await self._move(conn, tenant, request_id, actor, 'submitted')
        return dict(row)

    async def read(self, tenant_id: UUID | str, request_id: UUID) -> dict:
        tenant = UUID(str(tenant_id))
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow('''SELECT * FROM agent_tisan.quote_requests
                WHERE tenant_id=$1 AND id=$2''', tenant, request_id)
            if row is None:
                raise Missing
            events = await conn.fetch('''SELECT from_state,to_state,actor,happened_at
                FROM agent_tisan.quote_events WHERE tenant_id=$1 AND request_id=$2 ORDER BY id''',
                tenant, request_id)
        return {**dict(row), 'events': [dict(event) for event in events]}

    async def list(self, tenant_id: UUID | str, limit: int = 100) -> list[dict]:
        tenant = UUID(str(tenant_id))
        if not 1 <= limit <= 200:
            raise Refused('invalid_limit')
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''SELECT * FROM agent_tisan.quote_requests
                WHERE tenant_id=$1 ORDER BY created_at DESC,id DESC LIMIT $2''', tenant, limit)
        return [dict(row) for row in rows]

    async def move(self, tenant_id: UUID | str, request_id: UUID, actor: str, state: str) -> dict:
        tenant = identity(tenant_id, actor)
        async with self.pool.acquire() as conn, conn.transaction():
            return dict(await self._move(conn, tenant, request_id, actor, state))

    async def _move(self, conn, tenant, request_id, actor, state):
        row = await conn.fetchrow('''SELECT * FROM agent_tisan.quote_requests
            WHERE tenant_id=$1 AND id=$2 FOR UPDATE''', tenant, request_id)
        if row is None:
            raise Missing
        transition(row['state'], state)
        updated = await conn.fetchrow('''UPDATE agent_tisan.quote_requests
            SET state=$3,updated_at=clock_timestamp() WHERE tenant_id=$1 AND id=$2 RETURNING *''',
            tenant, request_id, state)
        await self._event(conn, tenant, request_id, row['state'], state, actor)
        return updated

    @staticmethod
    async def _event(conn, tenant, request_id, before, after, actor):
        await conn.execute('''INSERT INTO agent_tisan.quote_events
            (tenant_id,request_id,from_state,to_state,actor) VALUES ($1,$2,$3,$4,$5)''',
            tenant, request_id, before, after, actor)

    async def send_acknowledgement(self, tenant_id: UUID | str, request_id: UUID,
                                   *, transport=None) -> dict:
        tenant = UUID(str(tenant_id))
        # Verify ownership even when wording/configuration is absent.
        await self.read(tenant, request_id)
        letter = approved_letter()
        if letter is None:
            return {'mail': 'wording_missing'}
        if transport is None:
            # Tiger uses this same transport; no new SMTP implementation.
            try:
                from agents.rig.rigbox.reserve import SmtpMailer
            except ModuleNotFoundError:
                from quote_smtp import SmtpMailer
            transport = SmtpMailer.from_env()
            if transport is None:
                return {'mail': 'not_configured'}
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow('''UPDATE agent_tisan.quote_requests SET mail_state='sending'
                WHERE tenant_id=$1 AND id=$2 AND mail_state='pending'
                AND state IN ('submitted','acknowledged') RETURNING *''', tenant, request_id)
        if row is None:
            return {'mail': 'not_pending'}
        contact = row['contact']
        if isinstance(contact, str):
            contact = json.loads(contact)
        try:
            async with asyncio.timeout(30):
                await transport.send({**letter, 'to': contact['email'],
                    'message_id': f'<tisan.{tenant}.{request_id}@tervory.com>'})
        except (smtplib.SMTPDataError, smtplib.SMTPRecipientsRefused,
                smtplib.SMTPSenderRefused, smtplib.SMTPAuthenticationError,
                smtplib.SMTPConnectError, smtplib.SMTPHeloError,
                smtplib.SMTPNotSupportedError, ConnectionRefusedError, socket.gaierror):
            status = 'pending'
        except Exception:
            # A timeout/disconnect after DATA may mean accepted. Never auto-resend.
            status = 'uncertain'
        else:
            status = 'sent'
        async with self.pool.acquire() as conn:
            await conn.execute('''UPDATE agent_tisan.quote_requests SET mail_state=$3
                WHERE tenant_id=$1 AND id=$2 AND mail_state='sending' ''', tenant, request_id, status)
        return {'mail': status}


def approved_letter() -> dict[str, str] | None:
    """Consume a future approved fenced JSON acknowledgement, verbatim.

    QUOTE-EMAILS.md must contain exactly one ```json block with an
    acknowledgement object containing subject and text. No default copy,
    substitutions, environment override or caller-selected file exists.
    """
    try:
        raw = EMAIL_WORDING.read_text(encoding='utf-8')
        if raw.count('```json\n') != 1:
            return None
        block = raw.split('```json\n', 1)[1].split('\n```', 1)
        if len(block) != 2:
            return None
        value = json.loads(block[0])['acknowledgement']
        if set(value) != {'subject', 'text'}:
            return None
        if not all(isinstance(v, str) and v.strip() for v in value.values()):
            return None
        if any(c in value['subject'] for c in '\r\n'):
            return None
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return None


def mount(app: Any, guard) -> None:
    """Private room API, using the existing verified-founder and room-key guard."""
    from contextlib import asynccontextmanager
    from fastapi import Header, HTTPException, Query

    prior = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        async with prior(instance):
            schema = Path(__file__).with_name('schema.sql').read_text()
            async with instance.state.pool.acquire() as conn:
                await conn.execute(schema[schema.index('-- J4:'):])
            yield

    app.router.lifespan_context = lifespan

    def store():
        return Quotes(app.state.pool)

    async def result(operation):
        try:
            return await operation
        except Missing:
            raise HTTPException(404, 'not_found') from None
        except Refused:
            raise HTTPException(409, 'invalid_transition') from None

    @app.post('/quotes', status_code=201)
    async def create_quote(body: Create, x_tank_key: str = Header(default=''),
                           x_tervory_admin: str = Header(default='')):
        guard(x_tank_key, x_tervory_admin)
        return await result(store().create(body.tenant_id, x_tervory_admin,
                            body.data.model_dump(mode='json'), submitted=True))

    @app.get('/quotes')
    async def list_quotes(tenant_id: UUID, limit: int = Query(default=100, ge=1, le=200),
                          x_tank_key: str = Header(default=''),
                          x_tervory_admin: str = Header(default='')):
        guard(x_tank_key, x_tervory_admin)
        return await result(store().list(tenant_id, limit))

    @app.get('/quotes/{request_id}')
    async def read_quote(request_id: UUID, tenant_id: UUID,
                         x_tank_key: str = Header(default=''),
                         x_tervory_admin: str = Header(default='')):
        guard(x_tank_key, x_tervory_admin)
        return await result(store().read(tenant_id, request_id))

    @app.post('/quotes/{request_id}/state')
    async def move_quote(request_id: UUID, body: Move,
                         x_tank_key: str = Header(default=''),
                         x_tervory_admin: str = Header(default='')):
        guard(x_tank_key, x_tervory_admin)
        return await result(store().move(body.tenant_id, request_id, x_tervory_admin, body.state))

    @app.post('/quotes/{request_id}/email')
    async def email_quote(request_id: UUID, tenant_id: UUID,
                          x_tank_key: str = Header(default=''),
                          x_tervory_admin: str = Header(default='')):
        guard(x_tank_key, x_tervory_admin)
        return await result(store().send_acknowledgement(tenant_id, request_id))
