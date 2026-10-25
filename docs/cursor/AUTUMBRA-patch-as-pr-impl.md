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
| `agents/ghost/patch_connect.py` | CONNECT: match / threat facts → PatchBrief |
| `POST /ghost/patch/from-match` | Match fixture → connect plan |
| `POST /ghost/patch/from-threat` | Threat-shaped facts → dry-run |
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


## CONNECT (Watch path stub)

Advisory match → ThreatPayload-shaped facts → `PatchBrief` → draft/dry-run dep-bump plan.

| Path | Role |
| --- | --- |
| `agents/ghost/patch_connect.py` | `match_to_patch_brief`, `threat_to_patch_brief`, `connect_match_to_plan` |
| `POST /ghost/patch/from-match` | Tank-keyed: GHOST-2 match JSON → connect plan |
| `POST /ghost/patch/from-threat` | Tank-keyed: ThreatConnect / ThreatPayload-shaped JSON → dry-run |
| `tests/fixtures/autumbra/patch_connect_match.json` | Dogfood pip match (Coolify / tank) |
| `tests/test_ghost_patch_connect.py` | Burns, dry-run, ASGI routes, no merge / no HF |

- Deterministic. **No LLM. No HuggingFace.** Fixtures only until Zenas tops up + go.
- `ThreatConnect` (extra=forbid) validates connect fields when `threat_payload` is not on the branch; when #281 lands, Watch may emit ThreatPayload and this mapper still turns allowlisted patch fields into `PatchBrief`.
- Flag still OFF by default (`GHOST_PATCH_PR_ENABLED`). **Never merges. Never deploys.**

## Cross-links

- Design note: PR #282 / `docs/cursor/GHOST-4-patch-as-pr.md` (historical filename; design-only).
- ThreatPayload burn style (separate PR): `agents/ghost/threat_payload.py` when landed.
- Wraith flag-OFF pattern (separate PR): `agents/ghost/wraith.py` when landed.
