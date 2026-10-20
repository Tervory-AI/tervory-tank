"""Every model call is a Tank /v1/route call. Providers are not on this path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from workers.egress import Policy
from workers.settings import Settings


class TankRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class RouteResult:
    content: str
    cost_usd: float
    ledger_id: str
    tokens_in: int
    tokens_out: int


def route_body(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    issue: int,
    max_tokens: int | None,
) -> dict[str, Any]:
    if not messages:
        raise TankRefused("a model call needs a message")
    body: dict[str, Any] = {
        "tenant_id": settings.tenant_id,
        "agent": "workers",
        "task_type": settings.task_type,
        "skill": f"worker.{issue}",
        "messages": messages,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    return body


def normalize_messages(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise TankRefused("messages must be a list")
    messages: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TankRefused("a message must be an object")
        role = item.get("role")
        content = item.get("content")
        if not isinstance(role, str) or not role:
            raise TankRefused("a message needs a role")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                else:
                    raise TankRefused("only text can be sent to Tank")
            text = "\n".join(parts)
        else:
            raise TankRefused("only text can be sent to Tank")
        messages.append({"role": role, "content": text})
    return messages


def assert_tank_destination(settings: Settings) -> str:
    url = settings.route_url()
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    policy = Policy(tank_host=settings.tank_host, tank_port=settings.tank_port, proxy_port=settings.proxy_port)
    policy.check(host, port)
    if parsed.path != "/v1/route":
        raise TankRefused("model calls go to /v1/route")
    return url


def parse_route_response(payload: dict[str, Any]) -> RouteResult:
    content = payload.get("content")
    if not isinstance(content, str):
        raise TankRefused("Tank did not return text")
    try:
        cost = float(payload.get("cost_usd") or 0)
    except (TypeError, ValueError) as exc:
        raise TankRefused("Tank cost was not a number") from exc
    ledger = str(payload.get("ledger_id") or "")
    if not ledger:
        raise TankRefused("Tank did not return a ledger id")
    return RouteResult(
        content=content,
        cost_usd=cost,
        ledger_id=ledger,
        tokens_in=int(payload.get("tokens_in") or 0),
        tokens_out=int(payload.get("tokens_out") or 0),
    )


def openai_completion(result: RouteResult) -> dict[str, Any]:
    return {
        "id": "chatcmpl-worker",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result.tokens_in,
            "completion_tokens": result.tokens_out,
            "total_tokens": result.tokens_in + result.tokens_out,
        },
    }
