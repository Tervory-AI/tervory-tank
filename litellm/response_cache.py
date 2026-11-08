"""Expose LiteLLM's actual Redis-cache hit, never a provider prompt-cache hit."""
import os


class ResponseCacheMixin:
    async def async_post_call_response_headers_hook(
            self, data, user_api_key_dict, response, request_headers=None, litellm_call_info=None):
        if os.environ.get('ENGINE_C1_ENABLED') != '1':
            return {}
        enabled = (data.get('cache') or {}).get('use-cache') is True
        hidden = getattr(response, '_hidden_params', {}) or {}
        if enabled and hidden.get('cache_hit') is True:
            return {'x-tervory-cache-layer': 'C1', 'x-litellm-response-cost': '0'}
        return {}


callback = ResponseCacheMixin()
