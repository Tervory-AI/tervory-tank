"""C5 on every provider in the LiteLLM rosters, off unless ENGINE_C5_ALL_PROVIDERS_ENABLED=true.

Main already orders every prompt fixed text first and books provider-reported
cache tokens (prompt_cache.py). That is unchanged. When the setting is the
literal ``true`` this module adds, per call:

* the documented cache behaviour of the provider that serves the alias
  (automatic or markers, minimum length, time to live, read and write price);
* a read/write rate from the provider's own price page when the roster has
  none, so a cache hit on xAI, Z.ai, MiniMax or StepFun is priced instead of
  being booked as unpriced (the roster rate always wins when present);
* a per-tenant ``prompt_cache_key`` for the providers whose documentation
  names it (OpenAI, xAI). It is a hash, never a tenant id, and it keeps one
  tenant's cache apart from another's (OpenAI: "helps prevent cache-hit
  probing across users");
* receipt lines: cached tokens, the discount, the rate source and a hash of
  the cacheable prefix as each provider format sees it, so a prefix that stops
  being byte-identical between calls is visible on the receipt.

Tank still never adds a cache marker itself. Markers stay where they are, per
deployment, in litellm/config.yaml. Every provider below that caches without
markers does so automatically, and DashScope's open Qwen 3.5 routes and the
Hugging Face router publish no prompt cache at all.

Unset, blank or any other value: no lookup, no extra request field, no extra
receipt line. The answer object passes through untouched.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

SETTING = 'ENGINE_C5_ALL_PROVIDERS_ENABLED'
CHECKED = '2026-11-09'
MEMORY_HEAD = 'Tenant memory, most recent facts first.'
# The messages of the last dispatch in this request's context, for its receipt line.
_SENT: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar('c5_sent', default=None)


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


@dataclass(frozen=True)
class Provider:
    """What one provider's own documentation says about its prompt cache."""
    name: str
    mode: str                        # automatic | markers | none | provider_reported | not_applicable
    wire: str                        # openai | anthropic | gemini: how the prefix reaches the provider
    sources: tuple[str, ...]
    min_tokens: int | None = None    # None: the documentation states no minimum
    ttl: str | None = None           # None: not stated
    # USD per token for a cache read, per served model (matched by prefix of the native id).
    read_usd: dict[str, float] = field(default_factory=dict)
    # Multipliers of the input rate, used only when no per-model price is listed.
    read_x: float | None = None
    write_x: float | None = None
    routing_key: bool = False        # documentation names prompt_cache_key for cache routing/isolation
    usage_field: str = 'prompt_tokens_details.cached_tokens'
    note: str = ''


M = 1e-6
PROVIDERS: dict[str, Provider] = {p.name: p for p in (
    Provider('openai', 'automatic', 'openai', (
        'https://developers.openai.com/api/docs/guides/prompt-caching',
        'https://developers.openai.com/api/docs/pricing'),
        min_tokens=1024, ttl='30m default, 12h option (2.5x write)', read_x=0.1, write_x=1.25, routing_key=True,
        usage_field='prompt_tokens_details.cached_tokens, cache_write_tokens',
        note='GPT-6.1 Sol reads at 0.05x. LiteLLM marks system messages (litellm/config.yaml).'),
    Provider('anthropic', 'markers', 'anthropic', (
        'https://platform.claude.com/docs/en/build-with-claude/prompt-caching',
        'https://platform.claude.com/docs/en/about-claude/pricing'),
        min_tokens=512, ttl='5m, refreshed on each hit; 1h option (2x write)', write_x=1.25,
        usage_field='cache_read_input_tokens, cache_creation_input_tokens',
        note='Reads 0.1x Haiku 5.5, 0.05x Sonnet/Opus 5.5, 0.025x Fable 5.1. Markers set by LiteLLM, max 4.'),
    Provider('gemini', 'automatic', 'gemini', (
        'https://ai.google.dev/gemini-api/docs/caching',),
        min_tokens=4096, ttl=None, usage_field='usageMetadata.cachedContentTokenCount',
        note='Implicit cache on by default; explicit caches bill storage and are never created by Tank.'),
    Provider('deepseek', 'automatic', 'openai', (
        'https://api-docs.deepseek.com/guides/kv_cache',
        'https://api-docs.deepseek.com/quick_start/pricing/'),
        ttl='best effort, hours to days', usage_field='prompt_cache_hit_tokens'),
    Provider('moonshot', 'automatic', 'openai', (
        'https://platform.kimi.ai/docs/guide/context-caching',
        'https://platform.kimi.ai/docs/pricing/chat'),
        ttl='5m default, refreshed on each hit; 1h option', read_x=0.1,
        note='Cache writes are charged; no write rate is published per token, so writes stay unpriced.'),
    Provider('xai', 'automatic', 'openai', (
        'https://docs.x.ai/developers/advanced-api-usage/prompt-caching',
        'https://docs.x.ai/developers/advanced-api-usage/prompt-caching/usage-and-pricing',
        'https://docs.x.ai/docs/pricing'),
        routing_key=True, read_usd={'grok-4.7': .5 * M, 'grok-4.6': .5 * M, 'grok-4.5': .3 * M,
                                    'grok-4.3': .2 * M, 'grok-build-0.1': .2 * M},
        note='No write charge is documented. x-grok-conv-id or prompt_cache_key raises the hit rate.'),
    Provider('zai', 'automatic', 'openai', (
        'https://docs.z.ai/guides/capabilities/cache',
        'https://docs.z.ai/guides/overview/pricing'),
        read_usd={'glm-5.3': .26 * M, 'glm-5.2': .26 * M, 'glm-5.1': .26 * M, 'glm-5': .2 * M,
                  'glm-4.7': .11 * M, 'glm-4.6': .11 * M},
        note='Cached input storage is "limited-time free" on the price page.'),
    Provider('minimax', 'automatic', 'openai', (
        'https://platform.minimax.io/docs/api-reference/text-prompt-caching',
        'https://platform.minimax.io/docs/guides/pricing-paygo'),
        min_tokens=512, read_usd={'minimax-m3.1-flash': .015 * M, 'minimax-m3': .06 * M},
        note='M3 rate is the <=512k Standard tier. No write price is listed.'),
    Provider('stepfun', 'automatic', 'openai', (
        'https://platform.stepfun.ai/docs/en/guides/developer/prompt-cache',
        'https://platform.stepfun.ai/docs/en/guides/pricing/details'),
        min_tokens=256, ttl='LRU, shorter at peak', read_usd={'step-3.5-flash': .02 * M, 'step-3.7-flash': .04 * M},
        usage_field='cached_tokens'),
    Provider('dashscope', 'none', 'openai', (
        'https://www.alibabacloud.com/help/en/model-studio/context-cache',),
        note='qwen3.5-27b, -122b-a10b and -397b-a17b are in neither the explicit nor the implicit cache list.'),
    Provider('hf-router', 'none', 'openai', (
        'https://huggingface.co/docs/inference-providers/index',),
        note='The Hugging Face router publishes no prompt-cache price; any reported hit stays unpriced.'),
    Provider('perplexity', 'provider_reported', 'openai', (
        'https://docs.perplexity.ai/docs/getting-started/pricing',
        'https://docs.perplexity.ai/docs/agent-api/models'),
        usage_field='cache_read_input_tokens, cache_read_cost',
        note='Presets pick the model; cache reads are billed at that model rate and the receipt keeps the provider total.'),
    Provider('local', 'not_applicable', 'openai', (), note='Tervory CPU; $0 per token.'),
    Provider('build', 'not_applicable', 'openai', (), note='Build-only subscription route; $0 per token.'),
)}


def provider(prices: dict[str, Any]) -> Provider | None:
    """The documented provider behind a roster row (prices from main._batch_price)."""
    kind, native = prices.get('provider', ''), prices.get('native', '')
    lowered = native.lower()
    if kind == 'chatgpt':
        return PROVIDERS['build']
    if kind != 'openai':
        # LiteLLM's own provider prefix names the provider (anthropic/, xai/, gemini/ ...).
        return PROVIDERS.get(kind)
    # openai/ is also LiteLLM's OpenAI-compatible client: the served id names the provider.
    if lowered in {'local', 'local-large'} or lowered.startswith('tervory-own-'):
        return PROVIDERS['local']
    if '/' in native or ':' in native:
        return PROVIDERS['hf-router']
    for prefix, name in (('gpt-', 'openai'), ('minimax-', 'minimax'), ('glm-', 'zai'),
                         ('step-', 'stepfun'), ('qwen', 'dashscope')):
        if lowered.startswith(prefix):
            return PROVIDERS[name]
    return None


def _model_rate(table: dict[str, float], native: str) -> float | None:
    lowered = native.lower()
    # Longest prefix first, so glm-5.3 never takes the glm-5 rate.
    for key in sorted(table, key=len, reverse=True):
        if lowered == key or lowered.startswith(key + '-') or lowered.startswith(key + ':'):
            return table[key]
    return None


def fill(prices: dict[str, Any]) -> dict[str, Any]:
    """Roster prices plus documented cache rates where the roster has none. Off: unchanged."""
    if not enabled() or not prices:
        return prices
    found = provider(prices)
    out = dict(prices)
    out['rate_source'] = 'roster' if prices.get('cache_read') is not None else None
    if found is None or prices.get('input') is None:
        return out
    if prices.get('cache_read') is None:
        rate = _model_rate(found.read_usd, prices.get('native', ''))
        if rate is None and found.read_x is not None:
            rate = float(Decimal(str(prices['input'])) * Decimal(str(found.read_x)))
        if rate is not None:
            out['cache_read'] = rate
            out['rate_source'] = 'provider_docs'
    if prices.get('cache_write') is None and found.write_x is not None:
        out['cache_write'] = float(Decimal(str(prices['input'])) * Decimal(str(found.write_x)))
    return out


def routing_key(tenant_id: Any, task_type: str) -> str:
    """Stable per tenant and task; a hash, so no tenant id leaves Tervory."""
    raw = json.dumps(['tervory-c5-v1', str(tenant_id), task_type], separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def request_options(rt: Any, req: Any, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Extra gateway fields for this call. Off, or a provider without a documented key: none."""
    if not enabled():
        return {}
    _SENT.set([{'role': m['role'], 'content': m['content']} for m in messages])
    try:
        prices = await rt._batch_price(model)
    except (HTTPException, KeyError):
        # An unpriced alias simply gets no cache key.
        return {}
    found = provider(prices)
    if found is None or not found.routing_key:
        return {}
    return {'prompt_cache_key': routing_key(req.tenant_id, req.task_type)}


# ---------- the cacheable prefix, as each provider format sees it ----------

def split(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """(fixed system text, tenant memory, the request) in the order Tank sends them."""
    count = 0
    while count < len(messages) and messages[count].get('role') == 'system':
        count += 1
    lead = messages[:count]
    fixed = [m for m in lead if not str(m.get('content', '')).startswith(MEMORY_HEAD)]
    memory = [m for m in lead if str(m.get('content', '')).startswith(MEMORY_HEAD)]
    return fixed, memory, messages[count:]


def wire(fmt: str, messages: list[dict[str, Any]]) -> bytes:
    """Bytes of the leading system text in one provider's request shape.

    openai: chat messages, as Tank sends them (OpenAI, xAI, DeepSeek, Kimi, GLM, MiniMax, StepFun).
    anthropic: the ``system`` text blocks LiteLLM builds from system messages.
    gemini: the ``systemInstruction`` parts LiteLLM builds from system messages.
    """
    if fmt == 'openai':
        body: Any = [{'role': m['role'], 'content': m['content']} for m in messages]
    elif fmt == 'anthropic':
        body = {'system': [{'type': 'text', 'text': m['content']} for m in messages]}
    elif fmt == 'gemini':
        body = {'systemInstruction': {'parts': [{'text': m['content']} for m in messages]}}
    else:
        raise ValueError(fmt)
    return json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()


def prefix(fmt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    fixed, memory, _ = split(messages)
    fixed_bytes, both = wire(fmt, fixed), wire(fmt, [*fixed, *memory])
    return {'format': fmt, 'fixed_sha256': hashlib.sha256(fixed_bytes).hexdigest(),
            'fixed_bytes': len(fixed_bytes), 'prefix_sha256': hashlib.sha256(both).hexdigest(),
            'prefix_bytes': len(both), 'memory_messages': len(memory)}


# ---------- receipt ----------

def line(prices: dict[str, Any], c5: dict[str, Any], tokens_in: int) -> dict[str, Any]:
    found = provider(prices) if prices else None
    saved = c5.get('saved_usd')
    return {
        'provider': found.name if found else None,
        'mode': found.mode if found else None,
        'min_tokens': found.min_tokens if found else None,
        'below_minimum': bool(found and found.min_tokens and tokens_in < found.min_tokens),
        'ttl': found.ttl if found else None,
        'read_usd_per_token': prices.get('cache_read'),
        'write_usd_per_token': prices.get('cache_write'),
        'rate_source': prices.get('rate_source'),
        'cached_tokens': int(c5.get('cached_tokens') or 0),
        'cache_write_tokens': int(c5.get('cache_write_tokens') or 0),
        'discount_usd': saved,
        'sources': list(found.sources) if found else [],
        'checked': CHECKED,
    }


def reuse(cost_usd: float | None, *, shared_saved: float = 0., shared_served: bool = False,
          prompt_saved: float | None = 0., cached_tokens: int = 0) -> dict[str, Any]:
    """Per call: what came from the shared store and the prompt cache, against would-have-cost."""
    known = cost_usd is not None and prompt_saved is not None
    would = (Decimal(str(cost_usd)) + Decimal(str(shared_saved)) + Decimal(str(prompt_saved))) if known else None
    return {'cost_usd': cost_usd, 'would_have_cost_usd': float(would) if would is not None else None,
            'shared_store': {'served': shared_served, 'saved_usd': shared_saved},
            'prompt_cache': {'cached_tokens': cached_tokens, 'saved_usd': prompt_saved},
            'saved_usd': float(would - Decimal(str(cost_usd))) if would is not None else None}


async def write_detail(rt: Any, req: Any, ledger_id: Any, detail: dict[str, Any]) -> None:
    async with rt.pool().acquire() as conn:
        await conn.execute('''INSERT INTO tank.engine_receipts(tenant_id,region,task_type,ledger_id,detail)
            VALUES($1,$2,$3,$4,$5::jsonb) ON CONFLICT(tenant_id,ledger_id)
            DO UPDATE SET detail=tank.engine_receipts.detail || EXCLUDED.detail''',
            req.tenant_id, rt.box_region(), req.task_type, ledger_id, json.dumps(detail))


async def receipt(rt: Any, req: Any, answer: Any) -> Any:
    """Add the C5 line and the reuse line to a foreground answer. Off: the same object back."""
    if not enabled() or not isinstance(answer, rt.RouteResponse) or answer.rung in {3, 4}:
        return answer
    messages, _ = _SENT.get(), _SENT.set(None)
    try:
        prices = fill(await rt._batch_price(answer.model))
    except (HTTPException, KeyError):
        # An unpriced alias: the line says so instead of guessing.
        prices = {}
    c5 = (answer.engine or {}).get('cache_layers', {}).get('C5', {})
    c5_line = line(prices, c5, answer.tokens_in)
    if messages is not None:
        found = provider(prices) if prices else None
        c5_line['prefix'] = prefix(found.wire if found else 'openai', messages)
    detail = {'prompt_cache': c5_line,
              'reuse': reuse(answer.cost_usd, prompt_saved=c5.get('saved_usd', 0.),
                             cached_tokens=c5_line['cached_tokens'])}
    await write_detail(rt, req, answer.ledger_id, detail)
    return answer.model_copy(update={'engine': {**(answer.engine or {}), **detail}})
