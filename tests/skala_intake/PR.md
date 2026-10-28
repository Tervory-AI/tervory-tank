# Skala intake: Trigger checkers and Tiger playbooks

Work in progress. Based on main 3f469b0 (#391 merged); zenas.scope 1.2.0 is untouched.

## Scope

Package the six existing Trigger code checkers and Tiger's merged playbook code.
Keep current room behavior until founder approval. Use Skala's existing approval,
evaluation and rollback controls. No production actions or automatic approval.

## Decisions I made

- Current main includes Trigger's first build, but not its second-build house-style
  module. The house_style package will preserve the merged stylebook checks.
- All work runs in the saved cloud workspace. Claude opens the PR.

## Proof

Pending implementation and offline verification. No live acceptance is claimed.
