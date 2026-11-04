"""C3/C6: receipt-derived board states and tenant-owned human feedback."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from command import identity
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, model_validator


def state(row) -> str:
    value = dict(row)
    status, outcome = value.get('status'), value.get('receipt_outcome')
    if value.get('feedback') == 'rejected' or outcome == 'unverified' or (status == 'failed' and outcome in {'sent', 'delivered'}):
        return 'unverified'
    if status == 'done':
        return 'delivered' if outcome == 'delivered' else 'unverified'
    return status if status in {'queued', 'running', 'failed'} else 'unverified'


class Verdict(BaseModel):
    feedback: Literal['accepted', 'wrong']
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode='after')
    def require_note(self):
        if self.feedback == 'wrong' and not (self.note or '').strip():
            raise ValueError('Explain what was wrong.')
        if self.note is not None:
            self.note = self.note.strip()
        return self


def install(app, tank):
    @app.get('/v1/task-board')
    async def board(actor=Depends(identity)):  # noqa: B008
        await __import__('tenant_regions').local(tank, actor.tenant_id)
        rows = await tank.list_tasks(actor.tenant_id)
        return [{**row, 'status': row['board_state']} for row in rows]

    @app.post('/v1/tasks/{task_id}/feedback')
    async def feedback(task_id: UUID, body: Verdict, actor=Depends(identity)):  # noqa: B008
        await __import__('tenant_regions').local(tank, actor.tenant_id)
        async with tank.pool().acquire() as conn:
            ledger = await conn.fetchval('SELECT ledger_id FROM tank.tasks WHERE id=$1 AND tenant_id=$2', task_id, actor.tenant_id)
        if ledger is None:
            raise HTTPException(404, 'No delivered task for this workspace.')
        result = await tank.ledger_feedback(ledger, tank.Feedback(tenant_id=actor.tenant_id,
            feedback=body.feedback, note=body.note, by=actor.user_id))
        task = await tank.get_task(task_id, actor.tenant_id)
        return {**result, 'task_id': str(task_id), 'board_state': task['board_state']}
