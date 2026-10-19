"""OAuth 2.0 authorization server. Clerk is the identity provider. Clients register here."""

from __future__ import annotations

import hashlib
import html
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from connector.store import Store
from connector.tenant import tenant_id_for
from connector.tokens import challenge_matches, code_challenge, code_verifier, sign_access

log = logging.getLogger("tervory.mcp")

CLAUDE_REDIRECT = "https://claude.ai/api/mcp/auth_callback"
SCOPES = ["openid", "profile", "email", "offline_access"]
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 24 * 3600
CODE_TTL = 300
TXN_TTL = 600


@dataclass(frozen=True)
class Settings:
    public_url: str
    issuer: str
    resource_url: str
    tank_url: str
    tank_api_key: str
    clerk_secret_key: str
    clerk_frontend_api: str
    clerk_oauth_client_id: str
    clerk_oauth_client_secret: str
    signing_key: str
    tenant_aliases: str
    redis_url: str

    @property
    def metadata_url(self) -> str:
        return f"{self.issuer}/.well-known/oauth-protected-resource/mcp"


def load_settings() -> Settings:
    public = _origin(os_getenv("MCP_PUBLIC_URL") or "https://mcp.tervory.com")
    frontend = _frontend_api()
    return Settings(
        public_url=public,
        issuer=public,
        resource_url=public + "/mcp",
        tank_url=(os_getenv("TANK_URL") or "http://tank:8000").rstrip("/"),
        tank_api_key=os_getenv("TANK_API_KEY"),
        clerk_secret_key=os_getenv("CLERK_SECRET_KEY"),
        clerk_frontend_api=frontend,
        clerk_oauth_client_id=os_getenv("CLERK_OAUTH_CLIENT_ID"),
        clerk_oauth_client_secret=os_getenv("CLERK_OAUTH_CLIENT_SECRET"),
        signing_key=os_getenv("MCP_TOKEN_SIGNING_KEY"),
        tenant_aliases=os_getenv("TERVORY_TENANT_ALIASES"),
        redis_url=os_getenv("REDIS_URL"),
    )


def os_getenv(name: str) -> str:
    import os

    return os.environ.get(name, "").strip()


def _origin(url: str) -> str:
    return url.strip().rstrip("/")


def _frontend_api() -> str:
    explicit = os_getenv("CLERK_FRONTEND_API")
    if explicit.startswith("https://") and not urlparse(explicit).username:
        return explicit.rstrip("/")
    key = os_getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
    parts = key.split("_", 2)
    if len(parts) != 3 or parts[0] != "pk":
        return ""
    import base64

    pad = "=" * (-len(parts[2]) % 4)
    try:
        host = base64.b64decode(parts[2] + pad).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""
    host = host.strip().rstrip("$")
    if not host or "/" in host or " " in host:
        return ""
    return "https://" + host


def protected_resource(settings: Settings) -> dict[str, Any]:
    return {
        "resource": settings.resource_url,
        "authorization_servers": [settings.issuer],
        "scopes_supported": SCOPES,
        "bearer_methods_supported": ["header"],
    }


def authorization_server(settings: Settings) -> dict[str, Any]:
    base = settings.issuer
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": SCOPES,
    }


def www_authenticate(settings: Settings) -> str:
    return f'Bearer resource_metadata="{settings.metadata_url}", scope="openid profile email offline_access"'


def _loopback(url: str) -> tuple[str, str] | None:
    """Port-agnostic loopback identity. localhost and 127.0.0.1 are the same client."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or host not in {"localhost", "127.0.0.1"}:
        return None
    if parsed.username or parsed.password:
        return None
    path = (parsed.path or "/").rstrip("/") or "/"
    return "loopback", path


def redirect_allowed(requested: str, registered: list[str]) -> bool:
    if requested in registered:
        return True
    got = _loopback(requested)
    if got is None:
        return False
    for item in registered:
        if _loopback(item) == got:
            return True
    return False


def _acceptable_redirect(url: str) -> bool:
    if url == CLAUDE_REDIRECT:
        return True
    return _loopback(url) is not None and (_loopback(url) or ("", ""))[1].endswith("/callback")


def _oauth_error(status: int, code: str, description: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "error_description": description})


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ready(settings: Settings) -> str | None:
    if len(settings.signing_key) < 16:
        return "Sign-in is not configured."
    if not settings.clerk_frontend_api or not settings.clerk_oauth_client_id or not settings.clerk_oauth_client_secret:
        return "Sign-in is not configured."
    if not settings.clerk_secret_key:
        return "Sign-in is not configured."
    return None


def register_oauth(app: FastAPI, settings: Settings, store: Store) -> None:
    @app.get("/.well-known/oauth-protected-resource")
    @app.get("/.well-known/oauth-protected-resource/mcp")
    async def resource_metadata() -> JSONResponse:
        return JSONResponse(protected_resource(settings), headers={"cache-control": "no-store"})

    @app.get("/.well-known/oauth-authorization-server")
    async def server_metadata() -> JSONResponse:
        return JSONResponse(authorization_server(settings), headers={"cache-control": "no-store"})

    @app.post("/register")
    async def register(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            return _oauth_error(400, "invalid_client_metadata", "Send a JSON registration.")
        if not isinstance(body, dict):
            return _oauth_error(400, "invalid_client_metadata", "Send a JSON registration.")
        redirects = body.get("redirect_uris")
        if not isinstance(redirects, list) or not redirects or not all(isinstance(item, str) for item in redirects):
            return _oauth_error(400, "invalid_redirect_uri", "Register at least one redirect URI.")
        if any(not _acceptable_redirect(item) for item in redirects):
            return _oauth_error(400, "invalid_redirect_uri", "That redirect URI is not allowed.")
        method = str(body.get("token_endpoint_auth_method") or "none")
        if method != "none":
            return _oauth_error(400, "invalid_client_metadata", "This server registers public clients only.")
        grants = body.get("grant_types") or ["authorization_code", "refresh_token"]
        if not isinstance(grants, list) or "client_credentials" in grants:
            return _oauth_error(400, "invalid_client_metadata", "This server does not issue machine tokens.")
        client_id = str(uuid.uuid4())
        record = {
            "client_id": client_id,
            "redirect_uris": list(redirects),
            "client_name": str(body.get("client_name") or "")[:120],
            "token_endpoint_auth_method": "none",
        }
        await store.put(f"mcp:client:{client_id}", record, 365 * 24 * 3600)
        log.info("client registered")
        return JSONResponse(
            status_code=201,
            content={
                "client_id": client_id,
                "client_id_issued_at": int(time.time()),
                "redirect_uris": record["redirect_uris"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "client_name": record["client_name"],
            },
        )

    @app.get("/authorize", response_model=None)
    async def authorize(request: Request) -> HTMLResponse | JSONResponse:
        problem = _authorize_problem(request)
        if isinstance(problem, JSONResponse):
            return problem
        resource = str(request.query_params.get("resource") or "")
        if resource and resource != settings.resource_url:
            return _oauth_error(400, "invalid_target", "That resource is not this server.")
        txn_id, record = problem
        if not await _client_ok(store, str(record["client_id"]), str(record["redirect_uri"])):
            return _oauth_error(400, "invalid_request", "That client or redirect URI is not registered.")
        await store.put(f"mcp:txn:{txn_id}", record, TXN_TTL)
        host = urlparse(str(record["redirect_uri"])).hostname or ""
        warning = ""
        if host in {"localhost", "127.0.0.1"}:
            warning = "<p>This returns to a program on your own computer. Any local program can listen on that port.</p>"
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect Tervory</title>
<style>
  body {{ margin: 0; background: #F4F6FB; color: #001840; font-family: Inter, "Segoe UI", sans-serif; }}
  main {{ max-width: 32rem; margin: 4rem auto; padding: 0 1.25rem; }}
  h1 {{ font-family: Jost, "Segoe UI", sans-serif; font-weight: 300; font-size: 2rem; }}
  button {{ background: #E80008; color: white; border: 0; border-radius: 999px; padding: 0.7rem 1.2rem; font: inherit; cursor: pointer; }}
</style>
</head>
<body>
<main>
  <h1>Connect Tervory</h1>
  <p>Claude is asking to use your Tervory account.</p>
  <p>After you sign in, you return to <strong>{html.escape(host)}</strong>.</p>
  {warning}
  <form method="post" action="/authorize/continue">
    <input type="hidden" name="txn" value="{html.escape(txn_id)}">
    <button type="submit">Continue to sign in</button>
  </form>
</main>
</body>
</html>"""
        return HTMLResponse(page)

    @app.post("/authorize/continue", response_model=None)
    async def authorize_continue(request: Request) -> RedirectResponse | JSONResponse:
        form = await _form(request)
        txn_id = str(form.get("txn") or "")
        record = await store.get(f"mcp:txn:{txn_id}")
        if not record or record.get("kind") != "authorize":
            return _oauth_error(400, "invalid_request", "This sign-in has expired. Start it again from Claude.")
        blocked = _ready(settings)
        if blocked:
            return _oauth_error(503, "server_error", blocked)
        verifier = code_verifier()
        challenge = code_challenge(verifier)
        record["clerk_verifier"] = verifier
        await store.put(f"mcp:txn:{txn_id}", record, TXN_TTL)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": settings.clerk_oauth_client_id,
                "redirect_uri": f"{settings.public_url}/oauth/clerk/callback",
                "scope": "openid email profile",
                "state": txn_id,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return RedirectResponse(f"{settings.clerk_frontend_api}/oauth/authorize?{query}", status_code=302)

    @app.get("/oauth/clerk/callback", response_model=None)
    async def clerk_callback(request: Request) -> RedirectResponse | JSONResponse:
        txn_id = str(request.query_params.get("state") or "")
        record = await store.pop(f"mcp:txn:{txn_id}")
        if not record or record.get("kind") != "authorize":
            return _oauth_error(400, "invalid_request", "This sign-in has expired. Start it again from Claude.")
        redirect_uri = str(record["redirect_uri"])
        client_state = str(record.get("state") or "")
        if request.query_params.get("error"):
            return RedirectResponse(_client_redirect(redirect_uri, {"error": "access_denied", "state": client_state}), status_code=302)
        code = str(request.query_params.get("code") or "")
        if not code:
            return RedirectResponse(_client_redirect(redirect_uri, {"error": "access_denied", "state": client_state}), status_code=302)
        try:
            identity = await _clerk_identity(request.app.state.http, settings, code, str(record.get("clerk_verifier") or ""))
        except _ClerkProblem:
            log.info("clerk sign-in failed")
            return RedirectResponse(_client_redirect(redirect_uri, {"error": "access_denied", "state": client_state}), status_code=302)
        our_code = secrets.token_urlsafe(32)
        await store.put(
            f"mcp:code:{_hash(our_code)}",
            {
                "client_id": record["client_id"],
                "redirect_uri": redirect_uri,
                "challenge": record["challenge"],
                "user_id": identity["user_id"],
                "org_id": identity["org_id"],
                "tenant_id": identity["tenant_id"],
            },
            CODE_TTL,
        )
        log.info("authorization code issued")
        return RedirectResponse(
            _client_redirect(redirect_uri, {"code": our_code, "state": client_state}),
            status_code=302,
        )

    @app.post("/token")
    async def token(request: Request) -> JSONResponse:
        if "application/x-www-form-urlencoded" not in request.headers.get("content-type", ""):
            return _oauth_error(400, "invalid_request", "Send the form as application/x-www-form-urlencoded.")
        form = await _form(request)
        resource = str(form.get("resource") or "")
        if resource and resource != settings.resource_url:
            return _oauth_error(400, "invalid_target", "That resource is not this server.")
        grant = str(form.get("grant_type") or "")
        client_id = str(form.get("client_id") or "")
        client = await store.get(f"mcp:client:{client_id}")
        if not client:
            return _oauth_error(401, "invalid_client", "Unknown client.")
        if len(settings.signing_key) < 16:
            return _oauth_error(503, "server_error", "Sign-in is not configured.")
        if grant == "authorization_code":
            return await _exchange_code(store, settings, client, form)
        if grant == "refresh_token":
            return await _refresh(store, settings, client, form)
        return _oauth_error(400, "unsupported_grant_type", "Use an authorization code or a refresh token.")


def _authorize_problem(request: Request) -> tuple[str, dict[str, Any]] | JSONResponse:
    params = request.query_params
    if params.get("response_type") != "code":
        return _oauth_error(400, "unsupported_response_type", "Use response_type=code.")
    client_id = str(params.get("client_id") or "")
    redirect_uri = str(params.get("redirect_uri") or "")
    state = str(params.get("state") or "")
    challenge = str(params.get("code_challenge") or "")
    method = str(params.get("code_challenge_method") or "")
    if not client_id or not redirect_uri or not state:
        return _oauth_error(400, "invalid_request", "client_id, redirect_uri, and state are required.")
    if method != "S256" or not challenge:
        return _oauth_error(400, "invalid_request", "PKCE S256 is required.")
    txn_id = secrets.token_urlsafe(24)
    return txn_id, {
        "kind": "authorize",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "challenge": challenge,
    }


async def _form(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8", errors="replace")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


async def _exchange_code(store: Store, settings: Settings, client: dict[str, Any], form: dict[str, str]) -> JSONResponse:
    code = str(form.get("code") or "")
    verifier = str(form.get("code_verifier") or "")
    redirect_uri = str(form.get("redirect_uri") or "")
    record = await store.pop(f"mcp:code:{_hash(code)}")
    if not record or record.get("client_id") != client.get("client_id"):
        return _oauth_error(400, "invalid_grant", "That code is no longer valid.")
    if redirect_uri != record.get("redirect_uri"):
        return _oauth_error(400, "invalid_grant", "That code is no longer valid.")
    if not redirect_allowed(redirect_uri, list(client.get("redirect_uris") or [])):
        return _oauth_error(400, "invalid_grant", "That code is no longer valid.")
    if not challenge_matches(verifier, str(record.get("challenge") or "")):
        return _oauth_error(400, "invalid_grant", "That code is no longer valid.")
    # The authorize step stored the client id before the client record was re-checked.
    if not redirect_allowed(str(record.get("redirect_uri") or ""), list(client.get("redirect_uris") or [])):
        return _oauth_error(400, "invalid_grant", "That code is no longer valid.")
    return await _issue(store, settings, client, record)


async def _refresh(store: Store, settings: Settings, client: dict[str, Any], form: dict[str, str]) -> JSONResponse:
    presented = str(form.get("refresh_token") or "")
    key = f"mcp:refresh:{_hash(presented)}"
    record = await store.get(key)
    if not record or record.get("client_id") != client.get("client_id"):
        return _oauth_error(400, "invalid_grant", "The refresh token is no longer valid.")
    if record.get("replaced_by"):
        await _revoke_family(store, str(record.get("family") or ""))
        return _oauth_error(400, "invalid_grant", "The refresh token is no longer valid.")
    fresh = await _issue(store, settings, client, record)
    if fresh.status_code != 200:
        return fresh
    try:
        import json

        issued = json.loads(bytes(fresh.body))
    except (ValueError, TypeError):
        return fresh
    new_hash = _hash(str(issued.get("refresh_token") or ""))
    record["replaced_by"] = new_hash
    await store.put(key, record, REFRESH_TTL)
    log.info("refresh rotated")
    return fresh


async def _issue(store: Store, settings: Settings, client: dict[str, Any], record: dict[str, Any]) -> JSONResponse:
    user_id = str(record["user_id"])
    org_id = str(record["org_id"])
    tenant_id = tenant_id_for(org_id, settings.tenant_aliases)
    if tenant_id != str(record.get("tenant_id") or tenant_id):
        return _oauth_error(400, "invalid_grant", "That code is no longer valid.")
    access = sign_access(
        secret=settings.signing_key,
        issuer=settings.issuer,
        audience=settings.resource_url,
        user_id=user_id,
        org_id=org_id,
        tenant_id=tenant_id,
        ttl_s=ACCESS_TTL,
    )
    refresh = secrets.token_urlsafe(32)
    family = str(record.get("family") or uuid.uuid4())
    digest = _hash(refresh)
    await store.put(
        f"mcp:refresh:{digest}",
        {
            "client_id": client["client_id"],
            "user_id": user_id,
            "org_id": org_id,
            "tenant_id": tenant_id,
            "family": family,
            "replaced_by": "",
        },
        REFRESH_TTL,
    )
    members = await store.get(f"mcp:family:{family}") or {"hashes": []}
    hashes = [item for item in members.get("hashes") or [] if isinstance(item, str)]
    if digest not in hashes:
        hashes.append(digest)
    await store.put(f"mcp:family:{family}", {"hashes": hashes}, REFRESH_TTL)
    return JSONResponse(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": ACCESS_TTL,
            "refresh_token": refresh,
            "scope": "openid profile email offline_access",
        }
    )


async def _revoke_family(store: Store, family: str) -> None:
    members = await store.pop(f"mcp:family:{family}") or {}
    for digest in members.get("hashes") or []:
        if isinstance(digest, str):
            await store.pop(f"mcp:refresh:{digest}")


def _client_redirect(redirect_uri: str, query: dict[str, str]) -> str:
    sep = "&" if "?" in redirect_uri else "?"
    return redirect_uri + sep + urlencode({key: value for key, value in query.items() if value})


class _ClerkProblem(Exception):
    pass


async def _clerk_identity(http: httpx.AsyncClient, settings: Settings, code: str, verifier: str) -> dict[str, str]:
    token_url = f"{settings.clerk_frontend_api}/oauth/token"
    try:
        exchanged = await http.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.public_url}/oauth/clerk/callback",
                "client_id": settings.clerk_oauth_client_id,
                "client_secret": settings.clerk_oauth_client_secret,
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
            timeout=8,
        )
    except httpx.HTTPError:
        raise _ClerkProblem() from None
    if exchanged.status_code != 200:
        raise _ClerkProblem()
    try:
        token_body = exchanged.json()
    except ValueError:
        raise _ClerkProblem() from None
    access = str(token_body.get("access_token") or "")
    if not access:
        raise _ClerkProblem()
    try:
        info = await http.get(
            f"{settings.clerk_frontend_api}/oauth/userinfo",
            headers={"Accept": "application/json", "Authorization": f"Bearer {access}"},
            timeout=8,
        )
    except httpx.HTTPError:
        raise _ClerkProblem() from None
    if info.status_code != 200:
        raise _ClerkProblem()
    try:
        profile = info.json()
    except ValueError:
        raise _ClerkProblem() from None
    user_id = str(profile.get("sub") or "")
    if not user_id.startswith("user_"):
        raise _ClerkProblem()
    org_id = _org_from_profile(profile)
    if not org_id:
        org_id = await _one_org(http, settings, user_id)
    if not org_id.startswith("org_"):
        raise _ClerkProblem()
    return {"user_id": user_id, "org_id": org_id, "tenant_id": tenant_id_for(org_id, settings.tenant_aliases)}


def _org_from_profile(profile: dict[str, Any]) -> str:
    for key in ("org_id", "organization_id"):
        value = profile.get(key)
        if isinstance(value, str) and value.startswith("org_"):
            return value
    org = profile.get("org") or profile.get("organization")
    if isinstance(org, dict):
        value = org.get("id")
        if isinstance(value, str) and value.startswith("org_"):
            return value
    return ""


async def _one_org(http: httpx.AsyncClient, settings: Settings, user_id: str) -> str:
    try:
        response = await http.get(
            f"https://api.clerk.com/v1/users/{user_id}/organization_memberships",
            headers={"Accept": "application/json", "Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=8,
        )
    except httpx.HTTPError:
        raise _ClerkProblem() from None
    if response.status_code != 200:
        raise _ClerkProblem()
    try:
        body = response.json()
    except ValueError:
        raise _ClerkProblem() from None
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list) or len(rows) != 1:
        raise _ClerkProblem()
    org = rows[0].get("organization") if isinstance(rows[0], dict) else None
    org_id = org.get("id") if isinstance(org, dict) else ""
    if not isinstance(org_id, str) or not org_id.startswith("org_"):
        raise _ClerkProblem()
    return org_id


# Authorize must confirm the client before showing the page. The sync helper
# above cannot read the store, so the route checks it here.
async def _client_ok(store: Store, client_id: str, redirect_uri: str) -> bool:
    client = await store.get(f"mcp:client:{client_id}")
    if not client:
        return False
    return redirect_allowed(redirect_uri, list(client.get("redirect_uris") or []))
