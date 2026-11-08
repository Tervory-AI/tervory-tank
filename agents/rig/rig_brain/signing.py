"""Bind the verified worker owner to each request from the real SDK to Tank."""
from chassis.user_assertion import HEADER, SignedUser, sign_assertion
from chassis.task_contract import origin
import httpx


def bind_sdk_actor(agent, tank, key, tenant, user, task):
    base = httpx.URL(origin(tank))
    actor = SignedUser(tenant, user, "member")

    def sign(request):
        if ((request.url.scheme, request.url.host, request.url.port) !=
                (base.scheme, base.host, base.port) or
                not request.url.path.startswith("/v1/agents/rig/") or request.method != "POST"):
            raise PermissionError("Rig task scope mismatch")
        # Task scope is part of the signed target, not a mutable extra header.
        request.url = request.url.copy_set_param("task_id", task)
        request.headers[HEADER] = sign_assertion("rig", actor, request.method,
            request.url.raw_path.decode("ascii"), request.read(), key=key)

    # Keep Hermes and its actual SDK client/HTTP transport. Every retry gets a
    # fresh nonce while Tank's paid checkpoint retains the same task identity.
    def attach(client):
        hooks = client._client.event_hooks.setdefault("request", [])
        if sign not in hooks:
            hooks.append(sign)
        return client

    attach(agent.client)
    create = agent._create_openai_client

    def signed_client(*args, **kwargs):
        return attach(create(*args, **kwargs))

    # The pinned SDK creates separate clients for request timeouts/recovery.
    # Retain its real factory and transport; install the same signing hook on
    # every client it creates so later turns cannot lose the verified owner.
    agent._create_openai_client = signed_client
