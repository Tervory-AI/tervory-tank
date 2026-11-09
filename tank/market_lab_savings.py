"""Market Lab reuses Tank's prices, tokenizer, tenant actors and canonical ledger."""
import json
import os
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from tenant_db import tenant_path


class Reference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    tenant_id: UUID
    run_id: UUID
    operation: str=Field(min_length=1,max_length=80,pattern=r'^[a-z][a-z0-9_.]*$')
    input: dict
    output: dict


async def reference(tank, body):
    from agent_skills import input_encoding, baseline_cost
    encode=input_encoding().encode_ordinary
    tin=len(encode(json.dumps(body.input,ensure_ascii=False,sort_keys=True)))
    tout=len(encode(json.dumps(body.output,ensure_ascii=False,sort_keys=True)))
    async with tank.pool().acquire() as conn, conn.transaction():
        home=await conn.fetchval('SELECT home_region FROM tank.tenants WHERE tenant_id=$1',body.tenant_id)
        if home!=tank.box_region():
            raise HTTPException(403,'This request must stay on its home server.')
        # Reuse the task's explicit paid comparison, never select a serving model
        # or assume the most expensive roster entry is the client's default.
        rate=await conn.fetchrow('''SELECT rate.model,rate.input_usd,rate.output_usd,rate.updated_at
            FROM (SELECT * FROM tank.policy WHERE task_type='market.research'
                  AND (tenant_id=$1 OR tenant_id IS NULL) ORDER BY tenant_id NULLS LAST LIMIT 1) p
            LEFT JOIN tank.proof_prices serving ON serving.model=p.model
            JOIN tank.proof_prices rate ON rate.model=coalesce(
              (SELECT override_model FROM tank.baseline_settings WHERE task_type='market.research'),
              p.baseline_model,tank.standard_model_for(serving.family)) AND rate.active
            ''',body.tenant_id)
        task_type = 'market_lab.' + body.operation
        await conn.execute('''INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out)
            VALUES($1,$2,$3,'market_lab',$4,3,'code',0,0,0) ON CONFLICT(id) DO NOTHING''',
            body.run_id,body.tenant_id,tank.box_region(),task_type)
        own=await conn.fetchval("SELECT id FROM tank.ledger WHERE id=$1 AND tenant_id=$2 AND agent='market_lab'",body.run_id,body.tenant_id)
        if own is None:
            raise HTTPException(409,'Receipt identity is not available')
    comparable=body.output.get('status') not in {'failed','error'}
    roster=[] if not rate else [{'model_name':rate['model'],'model_info':{
        'input_cost_per_token':float(rate['input_usd']),'output_cost_per_token':float(rate['output_usd'])}}]
    cost=baseline_cost(roster,rate['model'],tin,tout) if rate and comparable else None
    return {'ledger_id':str(body.run_id),'would_have_cost':cost,'baseline_model':rate['model'] if rate else None,
        'comparison_status':'cl100k_reference' if cost is not None else 'unpriced',
        'reference_tokens_in':tin,'reference_tokens_out':tout,'priced_at':rate['updated_at'] if rate else None}


def install(router,tank):
    import command
    from ghost_routes import call_room
    async def room_key(x_tank_key: str=Header(default='')):
        if not command.key_matches(x_tank_key,os.environ.get('TANK_KEY_MARKET_LAB','')):
            raise HTTPException(401,'Room key required')

    @router.post('/v1/market-lab/internal/savings',dependencies=[Depends(room_key)])
    @tenant_path('body')
    async def price(body: Reference):
        return JSONResponse(jsonable_encoder(await reference(tank,body)),headers={'Cache-Control':'private, no-store'})

    class Action(BaseModel):
        model_config=ConfigDict(extra='forbid')
        tenant_id: UUID | None=None
        question: str=Field(default='',max_length=2000)
        home_region: str | None=None
        paid_run_id: UUID | None=None

    @router.post('/v1/market-lab/actions/{operation}')
    @tenant_path('actor')
    async def action(operation: str,body: Action,actor=Depends(command.identity)):
        tool={'ask':'market_lab.ask','research':'market_lab.research','refresh':'market_lab.refresh'}.get(operation)
        if not tool:
            raise HTTPException(404,'Not found')
        actor=await command.authorized_actor(actor)
        command.require_tool(actor,tool)
        if body.tenant_id is not None and body.tenant_id!=actor.tenant_id:
            raise HTTPException(403,'This workspace is not available')
        if body.home_region is not None and body.home_region!=tank.box_region():
            raise HTTPException(403,'This request must stay on its home server.')
        if operation!='refresh' and not body.question.strip():
            raise HTTPException(422,'A question is required')
        response=await call_room('POST','market_lab','/market/'+('refresh' if operation=='refresh' else 'ask'),
            body={'tenant_id':str(actor.tenant_id),'question':body.question,**({'paid_run_id':str(body.paid_run_id)} if body.paid_run_id else {})})
        if response.status_code==409:
            raise HTTPException(409,response.json().get('detail'))
        if response.status_code!=200:
            raise HTTPException(503,'Market Lab could not complete this request')
        result=response.json()
        receipt=result.get('run_receipt')
        if receipt:
            result.update(ledger_ids=receipt['ledger_ids'],cost_usd=receipt['cost'])
        elif operation=='refresh':
            # Confirming the queue write is code-only. The worker later leaves
            # its separate run receipt; command reconciliation needs this ID now.
            async with tank.pool().acquire() as conn:
                ident=await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out)
                    VALUES($1,$2,'market_lab','market_lab.refresh.queued',3,'code',0,0,0) RETURNING id""",actor.tenant_id,tank.box_region())
            result.update(ledger_ids=[str(ident)],cost_usd=0)
        return JSONResponse(result,headers={'Cache-Control':'private, no-store'})
