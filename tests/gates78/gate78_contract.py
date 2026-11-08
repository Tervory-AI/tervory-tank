"""Shared acceptance requirements. Product suites map these to real entry paths.

DECISION Gate 7 is memory and identity; Gate 8 is the brain/task lifecycle.
DECISION A successful foundation run never certifies a product gate.
"""
from __future__ import annotations

PRODUCTS = (
    "autumbra", "base", "market-lab", "radix", "rig", "skala",
    "tiger", "tisan", "workspace", "zenas", "trigger", "opli",
)

REQUIREMENTS = {
    "G7.owner_crud": "Owner can remember, recall, list, get, edit and forget through the product entry point.",
    "G7.same_tenant": "Another user cannot read, alter, publish or forget personal records; denied mutations leave state unchanged.",
    "G7.other_tenant": "Another tenant cannot read, alter, publish or forget records, including through guessed IDs.",
    "G7.tenant_wide": "Only declared tenant-wide kinds are shared; an owner on that kind still makes the row personal.",
    "G7.required_owner": "Personal writes without a verified owner are refused; body/meta cannot widen scope.",
    "G7.signed_actor": "Real sign-in verification and Tank/product assertion verification bind tenant, user and role; body/header impersonation fails.",
    "G7.assertion_rejection": "Wrong key, audience, tenant, method, target/body, missing/expired/future assertion are refused.",
    "G7.replay": "Concurrent/restarted workers reject reused nonces; replay cannot restore forgotten data.",
    "G7.sql_before_vector": "User/tenant predicates restrict SQL candidates before vector search and limit; empty scope returns no rows.",
    "G7.database_role": "Exercise the deployed restricted database role and existing RLS guard where applicable; superuser-only proof is insufficient.",
    "G7.controls": "View/edit/forget/off use verified identity; no identity means no personal memory or controls, while authorised plain tasks still run.",
    "G7.no_content_leak": "Foreign content and secrets are absent from responses, cached answers, receipts and captured logs.",
    "G7.runtime_contract": "Shipped adapter/client calls real Hermes with the product key; runtime imports and actual routes work without proposal patches.",
    "G8.default_off": "With new settings unset, no memory/cache writes, added brain work or rescheduling; deployment profiles remain opt-in.",
    "G8.task_path": "Every paid/model endpoint runs its real task/worker path with recall before execution, a receipt and remember after.",
    "G8.free_first": "Existing code/free steps precede brain/Tank fallback; Opli and Workspace reuse Tank, without inventing a product brain.",
    "G8.exact_repeat": "Eligible exact business repeat (fresh run ID) makes no provider call; receipt cost/tokens are zero with would-have-cost.",
    "G8.misses": "Meaningful input changes, another user and another tenant miss; ineligible task types never reuse an answer.",
    "G8.correction": "A correction changes the next relevant answer for its owner, never another user's answer.",
    "G8.forget": "Forget invalidates derived reusable answers; deleted or superseded content cannot return on repeat.",
    "G8.memory_off": "Off prevents recall/remember/reuse for that user, without changing another user's setting or path.",
    "G8.outage": "Recall/list/remember outages produce truthful unavailable receipts; a post-payment write failure never repeats the paid call.",
    "G8.auth_not_outage": "Authentication/scope failures are not treated as storage outages or allowed to return private cached answers.",
    "G8.receipts": "Actual captured provider calls reconcile with per-run cost/tokens/savings; remembered product fields are meaningful, not hardcoded empty.",
    "G8.retry_concurrency": "Retries and concurrent requests preserve ownership, receipt accounting and the product's existing idempotency contract.",
    "G8.product_regressions": "All original Gate 7/8 requirements and product-specific browser/CLI/worker flows are retained and mapped.",
}

# These are shared regressions, not substitutes for any product's request path.
CORE_TARGETS = (
    "tests/test_hermes_user_scope.py",
    "tests/test_hermes_signed_identity.py",
    "tests/test_product_user_assertions.py",
    "tests/test_agent_memory_records.py::test_schema_empty_reapply_and_agent_role",
    "tests/test_hermes_user_scope_ingress.py",
    "tests/test_memory_runtime_packaging.py",
    "tests/test_oidc_memory_ingress_harness.py",
    "tests/gates78/test_stack.py",
)
