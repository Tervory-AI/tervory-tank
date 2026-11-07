"""Tank's internal memory corridor; outcomes come only from tenant-owned receipts."""
import hashlib
import json
import uuid

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from hermes.auth import identify
from hermes.records import ClaimTooLong


class Recall(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    task_type: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=2000)


class Outcome(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    ledger_id: uuid.UUID


def register(app, records):
    def ready(key):
        # DECISION reuse Tank's existing server credential, never impersonate a
        # founder or allow an agent to write another agent's collection.
        if identify(key) is not None:
            raise HTTPException(403, 'Tank service credential required')
        store = records()
        if store is None or 'tank' not in store.agents:
            raise HTTPException(503, 'memory store unreachable')
        return store

    @app.post('/engine/recall')
    async def recall(body: Recall, x_tank_key: str = Header(default='')):
        store = ready(x_tank_key)
        rows = await store.recall('tank', str(body.tenant_id), body.query, None, 32, 'client', user_id=body.user_id)
        rows = [row for row in rows if row.get('tenant_id') == str(body.tenant_id)
                and (row.get('kind') != 'engine.outcome' or row.get('meta', {}).get('task_type') == body.task_type)]
        rows.sort(key=lambda row: (row.get('kind') != 'engine.outcome', row.get('updated_at', row.get('created_at', ''))), reverse=True)
        return {'memories': rows[:8]}

    @app.post('/engine/remember')
    async def remember(body: Outcome, x_tank_key: str = Header(default='')):
        store = ready(x_tank_key)
        # The caller supplies no claim or authority. Re-read the completed,
        # masked transcript and keep both sides of the join tenant sealed.
        row = await store.pool.fetchrow("""SELECT l.task_type,t.messages,t.content FROM tank.ledger l
            JOIN tank.transcripts t ON t.ledger_id=l.id AND t.tenant_id=l.tenant_id
            WHERE l.tenant_id=$1 AND l.id=$2 AND l.outcome='delivered'
              AND l.feedback IS DISTINCT FROM 'rejected'""", body.tenant_id, body.ledger_id)
        if row is None:
            raise HTTPException(404, 'No delivered receipt for this tenant')
        if not body.user_id or not body.user_id.strip():
            raise HTTPException(422, 'Personal memory requires user_id')
        messages = json.loads(row['messages']) if isinstance(row['messages'], str) else row['messages']
        question = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
        claim = 'Request excerpt:\n' + question[:1500] + '\nOutcome excerpt:\n' + row['content'][:3000]
        identity = uuid.uuid5(body.tenant_id, hashlib.sha256((row['task_type'] + (body.user_id or '') + claim).encode()).hexdigest())
        existing = await store.get('tank', str(body.tenant_id), str(identity))
        if existing is not None:
            return {'id': str(identity), 'remembered': True}
        args = ('tank', str(body.tenant_id), claim, ['urn:tervory:ledger:' + str(body.ledger_id)])
        kwargs = dict(row_id=str(identity), kind='engine.outcome', confidence=.5,
                      meta={'task_type': row['task_type'], 'automatic': True, **({'user_id': body.user_id} if body.user_id else {})})
        try:
            await store.save(*args, **kwargs)
        except ClaimTooLong:
            # Retain the receipt even when it exceeds the pinned encoder's
            # context. Never silently truncate a vector to claim a match.
            await store.save(*args, **kwargs, index=False)
        return {'id': str(identity), 'remembered': True}
