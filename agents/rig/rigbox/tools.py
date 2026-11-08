"""Existing product actions for Tank Command/MCP, with room-owned identity."""
import hmac
import os
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field, ValidationError
from chassis.tenant_db import activate_tenant

from .api import AskIn, CompareIn, QuoteIn, SetupIn, SwapIn
from .rooms import require_owner
from .service import RigError
from .three_d.contracts import Job, Review, Strict
from .savings import Receipts, latest, public, publish, view, measured

router = APIRouter(prefix='/v1/rig/internal/tools')
ADMIN = {'receipts', 'receipt', 'suggest', 'forge.submit', 'forge.poll', 'forge.approve'}


class Call(Strict):
    tenant_id: UUID
    actor: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    administrator: bool = False
    arguments: dict = Field(default_factory=dict)


class Search(Strict):
    q: str = Field(default='', max_length=200)
    limit: int = Field(default=12, ge=1, le=24)


class Identity(Strict):
    id: UUID


class Approve(Identity):
    review: Review


@router.post('/{operation}')
async def call(operation: str, body: Call, request: Request):
    expected, presented = os.environ.get('TANK_KEY', ''), request.headers.get('x-tank-key', '')
    if not expected or not presented or not hmac.compare_digest(expected.encode(), presented.encode()):
        raise RigError('unauthorized', 'Room authorization is required.', 401)
    require_owner(body.tenant_id)
    if operation in ADMIN and not body.administrator:
        raise RigError('forbidden', 'Administrator authorization is required.', 403)
    tenant = str(body.tenant_id)
    activate_tenant(tenant)
    latest.set(None)
    service = request.app.state.rig
    try:
        if operation == 'search':
            data = Search.model_validate(body.arguments)
            result = await service.search(tenant, data.q, data.limit)
        elif operation in {'product', 'setups', 'graph'}:
            result = await getattr(service, operation)(tenant, **SetupIn.model_validate(body.arguments).model_dump())
        elif operation == 'ask':
            result = await service.ask(tenant, **AskIn.model_validate(body.arguments).model_dump())
        elif operation == 'compare':
            result = await service.compare(tenant, **CompareIn.model_validate(body.arguments).model_dump())
        elif operation == 'swap':
            data = SwapIn.model_validate(body.arguments)
            result = await service.swap(tenant, data.setup, data.role)
        elif operation == 'quote':
            result = await service.quote(tenant, QuoteIn.model_validate(body.arguments).model_dump(exclude_none=True))
        elif operation == 'receipts' and not body.arguments:
            result = await view(service, tenant)
        elif operation == 'receipt':
            result = await view(service, tenant, Identity.model_validate(body.arguments).id)
            if not result['receipts']:
                raise RigError('not_found', 'No such receipt.', 404)
        elif operation == 'suggest' and not body.arguments:
            result = await service.suggest(tenant)
        elif operation.startswith('cart.'):
            from .cart_api import action, cart
            from .commerce import CommerceError
            async def execute(owner):
                try:
                    return await action(cart(request), owner, operation[5:], body.arguments)
                except CommerceError as exc:
                    raise RigError(str(exc), 'The cart action could not be completed.', 409) from None
            result = await measured(service, 'rig.' + operation, execute)(tenant)
        elif operation.startswith('forge.'):
            from .three_d.api import engine
            value = engine(request)
            if operation == 'forge.submit':
                # Command arguments never choose a tenant, job ownership or a
                # caller-supplied provider. The existing Job contract does the rest.
                if 'tenant_id' in body.arguments:
                    raise ValueError('Server-owned identity')
                result = await value.submit(tenant, Job.model_validate({**body.arguments, 'tenant_id': tenant}))
            elif operation == 'forge.poll':
                result = await value.poll(tenant, Identity.model_validate(body.arguments).id)
            elif operation == 'forge.approve':
                data = Approve.model_validate(body.arguments)
                result = await value.approve(tenant, data.id, data.review, body.actor)
            else:
                raise ValueError('Unknown action')
        else:
            raise ValueError('Unknown action')
    except (ValidationError, ValueError, TypeError):
        raise RigError('invalid', 'The request is not valid.', 422) from None
    answer = {'result': result}
    receipt = latest.get()
    if receipt is not None and receipt['tenant_id'] == tenant:
        await publish(service, receipt)
        receipt = (await Receipts(service.store).rows(tenant, identity=receipt['id']))[0]
        answer['receipt'] = public(receipt)
        if receipt.get('ledger_id'):
            answer['ledger_id'] = receipt['ledger_id']
    return answer
