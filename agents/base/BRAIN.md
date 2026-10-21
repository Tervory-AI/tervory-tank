# Base Hermes pilot (AGENT-1)

Implementation branch: `cursor/agent-1-hermes-brain`. Work stays in
`agents/base/`, `agents/_brain/`, `tank/agent_skills.py`, additive Tank schema,
the explicitly authorized Skala run guard, room documentation and tests.

Nous Research Hermes Agent v0.22.2 is pinned to release commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
Its [MIT licence](https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/LICENSE)
permits commercial use and modification; retain the upstream copyright and
licence in the brain image. No model provider credentials belong in this room.

The first `agent.base.think` policy copies the existing `tier0.answer` serving
model once, with a separate baseline and no cache or automatic promotion. The
request's model name cannot change policy. Missing model policy or usage cost
fails visibly and leaves a failed ledger receipt. A failed call is never retried
by the route itself.

Implementation and cloud pilot evidence are being added in this draft. It is
not ready for deployment or review yet.
