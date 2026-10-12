"""tier0.classify: Classifies a request into the agent that should handle it: tier0, base, tiger, market_lab, radix, tisan or zenas. Label only."""

TEMPLATE = '{text}'


async def run(payload: dict, ctx) -> dict:
    text = str(payload.get("text", "")).strip()
    if not text:
        return {"text": "", "error": "empty input"}
    content = await ctx.model(
        [{"role": "user", "content": TEMPLATE.format(text=text)}],
        task_type="route.request", max_tokens=16,
    )
    return {"text": content.strip()}
