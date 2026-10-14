"""Session keys for Tiger's browser pool.

One context per agent, tenant, and session. The file path is the isolation
boundary: two tenants never share a file, even when the session string matches.
"""

from __future__ import annotations

import re
from pathlib import Path

IDLE_S = 600
HEAVY_RESOURCES = frozenset({"image", "media", "font"})
_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,128}$")


class SessionKeyError(ValueError):
    """A session key would leave that agent and tenant's directory."""


def blocks_resource(resource_type: str, screenshot: bool) -> bool:
    """Images and fonts stay blocked unless the caller asked for a picture."""
    if screenshot:
        return False
    return resource_type in HEAVY_RESOURCES


def idle_expired(last_used: float, now: float, idle_s: float = IDLE_S) -> bool:
    return (now - last_used) >= idle_s


def session_file(root: str | Path, agent: str, tenant: str, session: str) -> Path:
    """`/data/sessions/<agent>/<tenant>/<session>.json`, or raise."""
    base = Path(root)
    parts = (_part(agent), _part(tenant), _part(session))
    path = base / "sessions" / parts[0] / parts[1] / f"{parts[2]}.json"
    root_dir = base.resolve()
    resolved = path.resolve()
    if resolved != root_dir and root_dir not in resolved.parents:
        raise SessionKeyError("bad session key")
    return path


def _part(value: str) -> str:
    if not isinstance(value, str) or _PART.fullmatch(value) is None:
        raise SessionKeyError("bad session key")
    return value
