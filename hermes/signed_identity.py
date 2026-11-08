"""Hermes uses the existing v1 signed-user protocol and durable nonce store."""
from fastapi import HTTPException, Request
from hermes.records import Records
from hermes.user_assertion import HEADER, PostgresNonces, verify_assertion


async def verify_personal_identity(*, request: Request, records: Records | None, key: str,
                                   body_tenant: str | None, body_user: str | None) -> tuple[str, str]:
    if records is None or not records.agents:
        raise HTTPException(503, "memory store unreachable")
    # Production always provisions agent_tank. Disposable SQL fixtures use their
    # own isolated schema; never create a new schema or choose one from a request.
    agent = "tank" if "tank" in records.agents else min(records.agents)
    store = getattr(request.app.state, "hermes_nonces", None)
    if store is None or store.pool is not records.pool:
        store = request.app.state.hermes_nonces = PostgresNonces(records.pool, records.schema(agent).removeprefix("agent_"))
    tenant = str(body_tenant or request.headers.get("X-Tervory-Tenant", ""))
    target = request.scope.get("raw_path", request.url.path.encode()).decode("ascii")
    if request.scope.get("query_string"):
        target += "?" + request.scope["query_string"].decode("ascii")
    try:
        actor = await verify_assertion(request.headers.get(HEADER, ""), key=key,
            product="hermes", tenant_id=tenant, method=request.method, target=target,
            body=await request.body(), consume_nonce=store.claim)
    except PermissionError:
        raise HTTPException(401, "Signed user required for memory") from None
    if body_user is not None and actor.user_id != str(body_user):
        raise HTTPException(403, "user does not match signed identity")
    if request.headers.get("X-Tervory-Tenant", actor.tenant_id) != actor.tenant_id:
        raise HTTPException(403, "tenant does not match signed identity")
    if request.headers.get("X-Tervory-User", actor.user_id) != actor.user_id:
        raise HTTPException(403, "user does not match signed identity")
    return actor.tenant_id, actor.user_id
