"""Private writing lessons, using Tank's existing training-pair writer."""
import json
from uuid import UUID, uuid4

from fastapi import HTTPException


def obj(value):
    return json.loads(value) if isinstance(value, str) else value


async def record(actor, brief: str, result: dict) -> dict:
    from main import pool, box_region
    from training import save_pair
    draft = result.get('text')
    if not isinstance(draft, str):
        return result
    write_id = uuid4()
    report = result.get('report', {'delegated_to': 'zenas', 'notice': result.get('notice')})
    output = {'draft': draft, 'checker_results': report, 'feedback': {'status': 'pending', 'changes': ''}}
    async with pool().acquire() as conn, conn.transaction():
        await conn.execute('INSERT INTO tank.trigger_writes(id,tenant_id,user_id,brief,draft,checker_results) VALUES($1,$2,$3,$4,$5,$6::jsonb)', write_id, actor.tenant_id, actor.user_id, brief, draft, json.dumps(report))
        await save_pair(conn, tenant=actor.tenant_id, agent='trigger', task='trigger.write',
                        value={'brief': brief, 'voice_revision': result.get('voice_revision')}, output=output,
                        approved_by='', source='trigger.write', ref=str(write_id), client_matter=True, public=False)
        await conn.execute("UPDATE tank.training_pairs SET active=false WHERE tenant_id=$1 AND region=$2 AND source='trigger.write' AND source_ref=$3", actor.tenant_id, box_region(), str(write_id))
    return {**result, 'write_id': str(write_id)}


async def feedback(actor, write_id: UUID, status: str, changes: str, operation_id: UUID) -> dict:
    from main import pool, box_region
    async with pool().acquire() as conn, conn.transaction():
        row = await conn.fetchrow('SELECT * FROM tank.trigger_writes WHERE id=$1 AND tenant_id=$2 FOR UPDATE', write_id, actor.tenant_id)
        if row is None:
            raise HTTPException(404, 'Writing record unavailable')
        previous = await conn.fetchval('SELECT status FROM tank.trigger_feedback WHERE tenant_id=$1 AND operation_id=$2', actor.tenant_id, operation_id)
        if previous:
            return {'status': previous, 'write_id': str(write_id)}
        await conn.execute('INSERT INTO tank.trigger_feedback(tenant_id,write_id,status,changes,user_id,operation_id) VALUES($1,$2,$3,$4,$5,$6)', actor.tenant_id, write_id, status, changes, actor.user_id, operation_id)
        await conn.execute('UPDATE tank.trigger_writes SET feedback_status=$3 WHERE tenant_id=$1 AND id=$2', actor.tenant_id, write_id, status)
        # Reuse the existing receipt feedback fields consumed by case studies.
        # A foreign/repeated card cannot borrow another tenant's receipt.
        await conn.execute("""UPDATE tank.ledger l
            SET feedback=$4,feedback_note=$5,feedback_at=now(),feedback_by=$6
            WHERE l.tenant_id=$1 AND l.region=$2 AND l.task_type='trigger.write'
            AND EXISTS (SELECT 1 FROM tank.command_threads t
                CROSS JOIN LATERAL jsonb_each(t.state->'cards') c
                WHERE t.tenant_id=l.tenant_id AND c.value->>'tool'='trigger.write'
                AND c.value->>'status'='confirmed'
                AND c.value->'result'->>'write_id'=$3
                AND c.value->'result'->>'ledger_id'=l.id::text)""",
            actor.tenant_id, box_region(), str(write_id), status, changes, actor.user_id)

        await conn.execute("""UPDATE tank.training_pairs SET output=jsonb_set(output,'{feedback}',$4::jsonb),
            active=$5,approved_by=$6,polarity=$7,public=false,client_matter=true
            WHERE tenant_id=$1 AND region=$2 AND source='trigger.write' AND source_ref=$3""",
            actor.tenant_id, box_region(), str(write_id), json.dumps({'status': status, 'changes': changes}),
            status == 'accepted', actor.user_id if status == 'accepted' else '',
            'positive' if status == 'accepted' else 'negative')
    return {'status': status, 'write_id': str(write_id), 'text': changes, 'model_calls': 0}
