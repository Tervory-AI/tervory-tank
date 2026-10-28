# Automatic per-client product case-study reports

Branch `codex/case-study-reports`, from `origin/main` at `9769998`.

Implement the founder's 28 October figure list as fixed, complete API templates
for Base, Tiger, Market Lab, Rig, Zenas, Trigger, Tisan, Radix and Autumbra, each
with the shared Tank section. Reuse CORE-1 proof and existing product evidence.
Absent sources return zero and will be listed here. No page changes or model calls.

Report registration follows the existing tenant/product provisioning path and is
idempotent. Client access is limited to its authenticated tenant; founder access
uses the existing founder guard. Tests will cover zero-filled reports, populated
figures, added products, tenant isolation and template completeness.

Implementation, source mapping, exact validation commands and results are pending.
Claude opens the draft PR. Independent review and live acceptance remain pending.
