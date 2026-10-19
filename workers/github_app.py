"""Short-lived GitHub App installation tokens.

The private key stays in a file Coolify mounts. It is never logged and never copied into a task.
The token can write contents and pull requests and read and write issues. It cannot administer
the repository, change branch protection, or merge.
"""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

# GitHub caps an App JWT at 10 minutes. The installation token GitHub returns lasts one hour.
JWT_TTL_S = 9 * 60
TOKEN_MAX_S = 60 * 60
TOKEN_RE = re.compile(r"ghs_[A-Za-z0-9_]{4,200}")

# Contents write and pull-request write do not include a merge permission of their own.
# Merging is refused in code, and branch protection on main is what blocks a push there.
APP_PERMISSIONS = {
    "contents": "write",
    "pull_requests": "write",
    "issues": "write",
}


class TokenRejected(RuntimeError):
    def __init__(self) -> None:
        super().__init__("refusing a token that is not a short-lived GitHub App installation token")


class MainPushRefused(RuntimeError):
    def __init__(self) -> None:
        super().__init__("the worker token cannot push to main")


class MergeRefused(RuntimeError):
    def __init__(self) -> None:
        super().__init__("the worker token cannot merge")


def assert_installation_token(token: str) -> None:
    if "\n" in token or "\r" in token or not TOKEN_RE.fullmatch(token):
        raise TokenRejected()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def jwt_claims(app_id: str, now: int | None = None) -> dict[str, int | str]:
    if not re.fullmatch(r"[0-9]{1,20}", app_id):
        raise TokenRejected()
    issued = int(time.time() if now is None else now)
    return {"iat": issued - 60, "exp": issued + JWT_TTL_S, "iss": app_id}


def sign_app_jwt(app_id: str, private_key_pem: bytes, now: int | None = None) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    claims = jwt_claims(app_id, now)
    if int(claims["exp"]) - int(claims["iat"]) > 600:
        raise TokenRejected()
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signing = f"{header}.{payload}".encode()
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    signature = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64(signature)}"


def read_private_key(path: str) -> bytes:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(path)
    data = file.read_bytes()
    if b"PRIVATE KEY" not in data:
        raise TokenRejected()
    return data


def installation_token_body(repo: str) -> dict[str, object]:
    name = repo.split("/", 1)[1]
    return {"repositories": [name], "permissions": dict(APP_PERMISSIONS)}


def assert_token_response(body: dict[str, object]) -> str:
    token = str(body.get("token") or "")
    assert_installation_token(token)
    permissions = body.get("permissions") or APP_PERMISSIONS
    if isinstance(permissions, dict):
        extra = set(permissions) - set(APP_PERMISSIONS)
        if extra or "administration" in permissions:
            raise TokenRejected()
    return token


def protected_branch(branch: str) -> bool:
    name = branch.strip()
    if name.startswith("refs/heads/"):
        name = name[len("refs/heads/") :]
    return name.lower() in {"main", "master"}


def assert_push_branch(branch: str) -> str:
    """Only worker/<brief>-<id> may be pushed. main is refused before git is called."""
    if protected_branch(branch):
        raise MainPushRefused()
    name = branch.strip()
    if name.startswith("refs/heads/"):
        name = name[len("refs/heads/") :]
    if not re.fullmatch(r"worker/[A-Za-z0-9][A-Za-z0-9._-]{0,80}", name):
        raise MainPushRefused()
    if name.lower().endswith("/main") or "/main/" in name.lower():
        raise MainPushRefused()
    return name


def merge_pull_request(*_args: object, **_kwargs: object) -> None:
    raise MergeRefused()
