# GHOST-4: Patch-as-PR (advisory match → dependency bump)

> Written 24 Oct 2026. Dogfood slice from Ghost & Wraith Build Plan. **Design note only — not shipped code.** **No auto-merge. No auto-deploy. No Wraith rename. Founder gate stays on every production change.**

## Why
GHOST-2 matches advisories to inventory and opens Ghost issues. GHOST-3 bounds LLM triage into `ThreatPayload` (`propose_shield` | `open_match` | `write_brief`). The next honest step is a **structured path from a high-confidence match to a dependency bump PR** that CI can prove — still never merged by Ghost.

Today a match can propose a Shield (founder taps **Shield**) or leave a freeform brief. Patch-as-PR is the allowlisted, later action for "bump this lockfile package" once triage (or a deterministic matcher) says the fix is a version pin, not an edge rule.

## Trigger
1. GHOST-2 advisory watcher matches inventory (OSV / GHSA / CISA KEV / NVD — legitimate feeds only).
2. Severity / confidence bar before any worker brief is written:
   - **severity:** Critical or High, or any KEV hit on a dogfood site; Medium only when `confidence ≥` bar (default draft: `0.8`).
   - **confidence:** from version-range match quality + inventory freshness (stale inventory = no auto brief).
3. Site / app must be on the Ghost dogfood allowlist. No third-party or client repos in this slice.

## Worker brief (structured, not freeform shell)
Output is a JSON brief for the workers — same burn rules as ThreatPayload: fixed error string on reject, never echo dirty input. Allowlisted package ecosystems only (those already in GHOST-2 inventory):

| Field | Rule |
| --- | --- |
| `schema_version` | `ghost.patch.v1` |
| `action` | `open_dep_bump_pr` only (this note) |
| `site` / `repo` | Dogfood allowlist (owned Tervory repos / sites) |
| `ecosystem` | `npm` \| `pip` (lockfiles already inventoried: `package-lock.json` / `pnpm-lock.yaml`, `requirements*.txt`) |
| `package` | Exact name from inventory row |
| `from_version` / `to_version` | Semver / PEP440 strings from advisory fix range |
| `cve_ids` / `advisory_ids` | `CVE-…` and/or GHSA/OSV ids |
| `reason` | ≤300 chars; burns on injection / shell markers |
| `confidence` | 0..1 |
| extras | Forbidden (no shell, no arbitrary paths, no deploy flags) |

Triage may already emit `write_brief` / `open_match`. **`open_dep_bump_pr` is not in ThreatPayload today** — it is a later allowlisted action; this PR does not add it to code.

## Action: dependency bump PR only
1. Worker (or a future Ghost-owned path) opens a **draft or ready PR** that bumps the named package in the lockfile / requirements on the affected owned repo.
2. **CI must run** on that PR. No PASS claim without green checks on the live PR.
3. Ghost **never merges**. Ghost **never deploys**. Ghost does not toggle claim/join or auto-enforce on live.
4. Founder (or AMMOSYNC after Zenas) merges and deploys — same gate as every other Tank change.

## Explicit stop line
| In scope (design) | Out — founder decision gate |
| --- | --- |
| Match → brief → open bump PR | Auto-merge of the bump PR |
| CI required before any PASS talk | Production deploy from Ghost |
| Dogfood repos first | Auto-execute without founder tap |

**Stop before auto-merge.** Shipping the matcher/brief/PR opener is future code; enabling merge or Coolify deploy from Ghost is explicitly rejected in this phase.

## Relation to GHOST-3 ThreatPayload
- `propose_shield` → existing Shields Up proposal; founder taps **Shield**. Unchanged.
- `open_match` / `write_brief` → triage may surface the advisory; human or worker reads it.
- Patch-as-PR sits **after** a validated match (and optionally after triage): an allowlisted `open_dep_bump_pr` brief, not a freeform shell and not a shield apply.
- This design note does **not** extend `threat_payload.py` or `/ghost/triage/accept`. Cross-link only: see `docs/cursor/GHOST-3-threat-payload.md` when that lands on `main`.

## Dogfood / honesty
- Dogfood sites first (Ghost inventory allowlist). No client code in scope.
- This PR is **design only**. No PASS, no "patch loop live", no time-to-patch SLO claimed until a real bump PR on a dogfood repo is green under founder merge.
- Empty metrics stay **None yet**, not zero-as-proof (same panel honesty as GHOST-3).

## Out of scope here
- Auto-execute without founder tap
- Auto-merge / auto-deploy
- Implementing `open_dep_bump_pr` in Tank or Ghost code
- Dual-LLM / NeMo bunker
- Dark-web collectors (research lane later; threat intel only)
- Wraith agent rename
- Claim/join style toggles that auto-enforce on live
- Inventing Coolify / key blockers
