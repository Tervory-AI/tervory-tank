# Tank provider batches — founder decision, 28 Oct 03:15 PT

Continues on `codex/tank-batch-providers`. The initial `/v1/batches` Anthropic
blocker is superseded by authorization to use LiteLLM's existing pass-through.
The original audit remains in [initial-blocker.md](initial-blocker.md).

Implementation is complete; final proof is in progress. Vertex Gemini uses the existing
LiteLLM batch path with its documented 50% charge multiplier. Anthropic creation
and cancellation will use `/anthropic/v1/messages/batches`; status/results use the same pass-through. Native result rows feed Tank's unchanged
ledger and fallback handlers. No new settings, provider clients or keys.
Standalone Gemini remains unsupported and follows the existing per-item route.
48 offline batch tests pass (batch-tests.txt). The pinned pass-through source audit
also passes (passthrough-audit.txt). No live outcome or paid test is claimed.
