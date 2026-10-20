"""Local OpenAI-shaped proxy. Aider talks to loopback. Loopback talks only to Tank."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from workers.settings import Settings
from workers.tank_route import (
    assert_tank_destination,
    normalize_messages,
    openai_completion,
    parse_route_response,
    route_body,
)

TankSend = Callable[[str, dict[str, Any], str], Awaitable[dict[str, Any]]]


def read_key(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text or "\n" in text or len(text) > 500:
        raise RuntimeError("Tank key file is missing or unusable")
    return text


async def forward_chat(
    body: dict[str, Any],
    settings: Settings,
    *,
    issue: int,
    key: str,
    send: TankSend,
) -> dict[str, Any]:
    url = assert_tank_destination(settings)
    messages = normalize_messages(body.get("messages"))
    max_tokens = body.get("max_tokens")
    if max_tokens is not None and (not isinstance(max_tokens, int) or isinstance(max_tokens, bool)):
        raise RuntimeError("max_tokens must be a whole number")
    payload = route_body(settings, messages, issue=issue, max_tokens=max_tokens)
    response = await send(url, payload, key)
    return openai_completion(parse_route_response(response))


def models_document() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": "tank", "object": "model", "owned_by": "tank"}]}
