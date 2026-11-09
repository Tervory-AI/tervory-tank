"""Gate before (finish): a tenant's own cap per code task (ENGINE_CODE_TENANT_CAPS_ENABLED).

tank.code_task_caps holds at most one row per tenant: a token cap and/or a dollar
cap for each code task. Preflight's budget (ENGINE_CODE_PREFLIGHT_ENABLED) applies
it; the platform-wide caps ENGINE_CODE_BUDGET_TOKENS and ENGINE_CODE_BUDGET_USD
stay the ceiling, so a tenant can only tighten them. No row, or the setting not
literally `true`, keeps today's behaviour. Tenant administrators read and change
their own row at /v1/command/code/caps; the authenticated tenant is the only key.
"""

import os
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

SETTING = 'ENGINE_CODE_TENANT_CAPS_ENABLED'
USD = r'^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?$'


class Caps(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    max_tokens: int | None = Field(default=None, ge=1, le=999_999_999_999)
    max_usd: str | None = Field(default=None, pattern=USD)


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


def combine(platform: dict, own) -> dict:
    """The tenant's caps under the platform ceiling, per measure."""
    cap = dict(platform)
    if own is None:
        return cap
    if own['max_tokens'] is not None:
        cap['tokens'] = min(int(own['max_tokens']), cap['tokens']) if 'tokens' in cap else int(own['max_tokens'])
    if own['max_usd'] is not None:
        cap['usd'] = min(Decimal(own['max_usd']), cap['usd']) if 'usd' in cap else Decimal(own['max_usd'])
    return cap


async def own(conn, tenant_id):
    return await conn.fetchrow('SELECT max_tokens,max_usd FROM tank.code_task_caps WHERE tenant_id=$1', tenant_id)


async def effective(conn, tenant_id, platform: dict) -> dict:
    """Called by preflight with its already-validated platform caps."""
    if not enabled():
        return platform
    return combine(platform, await own(conn, tenant_id))


def view(platform, row) -> dict:
    def shown(cap):
        return {'tokens': cap.get('tokens'), 'usd': str(cap['usd']) if 'usd' in cap else None}
    mine = {'tokens': row['max_tokens'] if row else None, 'usd': str(row['max_usd']) if row and row['max_usd'] is not None else None}
    if platform is None:
        return {'tenant': mine, 'platform': 'invalid', 'effective': None}
    return {'tenant': mine, 'platform': shown(platform), 'effective': shown(combine(platform, row))}


def switched_on():
    """Runs before authentication and body parsing: switched off, the path does not exist."""
    if not enabled():
        raise HTTPException(404, 'Not Found')


def build_router():
    import command
    import code_preflight

    router = APIRouter(prefix='/code/caps', dependencies=[Depends(switched_on)])

    def platform():
        try:
            return code_preflight.budget()
        except code_preflight.SettingError:
            return None

    @router.api_route('', methods=['GET', 'PUT', 'POST', 'PATCH', 'DELETE'])
    async def caps(request: Request, actor: command.Actor = Depends(command.identity)) -> dict:
        if request.method not in ('GET', 'PUT'):
            raise HTTPException(405, 'Method Not Allowed')
        if not (actor.tenant_admin or actor.founder):
            raise HTTPException(403, 'Only a tenant administrator can read or change code caps')
        async with command.db().acquire() as conn:
            if request.method == 'GET':
                return view(platform(), await own(conn, actor.tenant_id))
            try:
                body = Caps.model_validate(await request.json())
            except (ValueError, ValidationError):
                raise HTTPException(422, 'Send max_tokens (whole number) and/or max_usd (decimal text), or both null') from None
            if body.max_usd is not None and Decimal(body.max_usd) <= 0:
                raise HTTPException(422, 'max_usd must be above zero')
            if body.max_tokens is None and body.max_usd is None:
                await conn.execute('DELETE FROM tank.code_task_caps WHERE tenant_id=$1', actor.tenant_id)
            else:
                await conn.execute(
                    'INSERT INTO tank.code_task_caps(tenant_id,max_tokens,max_usd,updated_by) VALUES($1,$2,$3,$4) '
                    'ON CONFLICT(tenant_id) DO UPDATE SET max_tokens=EXCLUDED.max_tokens,max_usd=EXCLUDED.max_usd,'
                    'updated_by=EXCLUDED.updated_by,updated_at=now()', actor.tenant_id, body.max_tokens,
                    Decimal(body.max_usd) if body.max_usd is not None else None, actor.user_id)
            return view(platform(), await own(conn, actor.tenant_id))

    return router
