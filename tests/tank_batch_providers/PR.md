# Tank provider batches

Started from main `a99f3cb` on `codex/tank-batch-providers`.
Scope: extend Tank's existing LiteLLM batch path using providers supported by the
pinned LiteLLM v1.106.4. Preserve reservations, per-item caps, fallback semantics,
and exclusion of interactive, MoA and below-minimum requests. No provider clients,
new keys/settings, UI, paid tests or production changes.

Provider/version research and implementation are pending. No live acceptance is
claimed. All tests will be offline. Claude opens the PR; founder merges.
