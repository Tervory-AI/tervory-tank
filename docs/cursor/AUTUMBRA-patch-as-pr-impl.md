# Autumbra: patch-as-PR implementation

> Written 24 Oct 2026. Implementation of the design note in PR #282 (`docs/cursor/GHOST-4-patch-as-pr.md`). **Draft PRs only. Never merges. Never deploys. Flag OFF by default.**

## Naming

**Product: Autumbra (Watch/Enforce). Internal: Ghost/Wraith.** User-facing copy uses Autumbra; room code lives under `agents/ghost` and env flags may keep the `GHOST_*` prefix.

## Modules

| Path | Role |
| --- | --- |
| `agents/ghost/patch_brief.py` | `ghost.patch.v1` schema, burn-on-fail, severity bar |
| `agents/ghost/patch_pr.py` | Draft dep-bump PR planner/opener (no merge API) |
| `POST /ghost/patch/accept` | Tank-keyed intake in `agents/ghost/app.py` |
| `tests/test_ghost_patch_pr.py` | Schema burns, severity gate, flag OFF dry-run, mocked draft open |

## Flag (default OFF)

- `GHOST_PATCH_PR_ENABLED` or alias `PATCH_PR_ENABLED` must be `1` / `true` / `yes` / `on` to call GitHub.
- Otherwise `open_dep_bump_pr` returns `{mode: "dry_run", note: "Flag OFF. No PR opened."}`.
- Missing token with flag ON also dry-runs (no invented credentials).

## Severity bar

- Critical / High / `known_exploited` → pass
- Medium → only if `confidence >= 0.8`
- Low → never

## Stop line

| In scope | Out |
| --- | --- |
| Accept structured brief | Auto-merge |
| Open **draft** dep-bump PR | Production deploy |
| CI must run on that PR | Calling GitHub merge API |

**Autumbra never merges. Autumbra never deploys.** Merge only after Zenas via AMMOSYNC.

## Cross-links

- Design note: PR #282 / `docs/cursor/GHOST-4-patch-as-pr.md` (historical filename; design-only).
- ThreatPayload burn style (separate PR): `agents/ghost/threat_payload.py` when landed.
- Wraith flag-OFF pattern (separate PR): `agents/ghost/wraith.py` when landed.
