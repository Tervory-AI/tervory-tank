# Autumbra naming

**Product name:** Autumbra

**Roles (customer-facing):**

| Role | Meaning | Internal code |
|------|---------|---------------|
| Autumbra Watch | Observe / triage / propose (JSON air-gap) | Ghost |
| Autumbra Enforce | Allowlisted act / patch-as-PR (no raw shell) | Wraith |

**Code today (do not rename in this PR):**

- Paths stay under `agents/ghost` (and related Ghost packages) until a dedicated rename PR.
- Env / feature flags stay `GHOST_*` / `WRAITH_*` until that clean rename.

**Docs / PR copy going forward:** prefer Autumbra (Watch / Enforce). Ghost and Wraith remain fine as internal code names in comments, tickets, and flag names.

**Ship policy:** draft PRs only from agent lanes; merge and deploy only after Zenas (via AMMOSYNC). This note does not claim a merge or deploy.
