"""LiteLLM lifecycle adapter for the self-hosted, tenant-isolated Langfuse sink."""
import os
from litellm.integrations.custom_logger import CustomLogger
from trace_sink import TraceSink


class TenantLangfuseCallback(CustomLogger):
    def __init__(self):
        super().__init__()
        self.sink = TraceSink()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # File/batch management has no generated answer. Tank traces each native
        # batch item separately with the same exporter and scoped project keys.
        if os.environ.get('LANGFUSE_ENABLED') == 'true' and str(call_type) in {
                'completion', 'acompletion', 'text_completion', 'atext_completion', 'responses', 'aresponses'}:
            return await self.sink.before(data)
        return data

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        if os.environ.get('LANGFUSE_ENABLED') == 'true' and self.has_context(kwargs):
            await self.sink.after(kwargs, response_obj, start_time, end_time)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        if os.environ.get('LANGFUSE_ENABLED') == 'true' and self.has_context(kwargs):
            await self.sink.after(kwargs, response_obj, start_time, end_time, failed=True)

    @staticmethod
    def has_context(kwargs):
        return 'tank_trace' in (kwargs.get('litellm_params', {}).get('metadata') or kwargs.get('metadata') or {})


callback = TenantLangfuseCallback()
