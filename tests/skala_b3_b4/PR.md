# Skala B3/B4: model revalidation and retirement probation

Work in progress, based on main 585a900. Cloud only; no GitHub API.
Claude opens the PR. Every finished repository file is committed and pushed.

## Decisions I made

- A model change must be captured transactionally, including policy upserts and
  graduations. Revalidation reuses the existing Skala eval endpoint implementation.
- Superseded approvals remain staging during probation; retirement never removes
  package files. The 30-day gate requires a continuous clean window.
- No automatic approval and no model calls outside the eval inputs themselves.

## Proof

Pending implementation and offline tests. No live acceptance claimed.
