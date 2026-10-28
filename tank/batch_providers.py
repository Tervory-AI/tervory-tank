"""Batch capabilities of the pinned LiteLLM v1.106.4, without provider credentials.

Only providers authorized in this lane: OpenAI (existing), Vertex Gemini.
Rates are the fraction charged, not the fraction saved. Other providers do not
inherit a discount. Sources and pinned adapter evidence are in
 tests/tank_batch_providers/PR.md.
"""
from typing import Any


def charge_multiplier(provider: str, native: str) -> float | None:
    # OpenAI Batch: https://platform.openai.com/docs/guides/batch
    if provider == 'openai':
        return 0.5
    # Google's Gemini batch pricing is 50% of standard input and output prices.
    # Do not apply Gemini pricing to Model Garden or Anthropic-on-Vertex models.
    if provider == 'vertex_ai' and native.startswith('gemini-'):
        return 0.5
    return None


def supports(prices: dict[str, Any]) -> bool:
    return charge_multiplier(prices['provider'], prices['native']) is not None
