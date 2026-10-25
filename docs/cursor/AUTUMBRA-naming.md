# Autumbra naming

**Product name:** Autumbra

**Roles (customer-facing and docs/PR copy):**

| Role | Meaning |
|------|---------|
| Autumbra Watch | Observe / triage / propose (JSON air-gap) |
| Autumbra Enforce | Allowlisted act / patch-as-PR (no raw shell) |

Use **Autumbra**, **Autumbra Watch**, and **Autumbra Enforce** in all user-facing copy. Do not use legacy product nicknames in titles, docs, panels, or status reports.

**Internal code path note (not user-facing):**

- Paths may still live under `agents/ghost` until a dedicated rename PR.
- Env / feature flags may still use historical `GHOST_*` / `WRAITH_*` names until that clean rename.
- Internal schema ids (for example `ghost.patch.v1`) are code identifiers, not product names.

**Ship policy:** draft PRs only from agent lanes; merge and deploy only after Zenas (via AMMOSYNC). This note does not claim a merge or deploy.
