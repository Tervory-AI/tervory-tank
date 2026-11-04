# Base shipped-feature inventory

Baseline: origin/main d5d3ea2e, checked on 4 November 2026. This inventory follows
merged history and executable code, not the presence or absence of other PRs.

## Fixes found by this pass

A real long-page failure was found in the older wiring suite: the unbounded
email regex could exceed 180 seconds on a 400 KB unbroken token. Added candidate
`base.scrape_site/1.3.1` and bounded the shared evidence matcher. Existing approved
packages stay unchanged. Five large-page cases check retained later-page contacts,
source/date, the HTML cap and a deadline; original eight candidate eval cases and
must-refuse checks remain intact. Normal Skala approval is still required.
The historical 1.2.0 HTML-cap fixture now uses whitespace-separated filler to test
its original cap contract without invoking the separately covered legacy regex bug.

Fixed the flat-image fixture in `tests/test_base_engine_terms_approved.py`:
with TMPDIR inside this checkout, default ancestor discovery found host skills.
The child now uses the explicit image SKILLS_DIR, including when absent. No
runtime skill selection changed. Initial baseline: 503 passed, this one failed.
The local security precheck now bounds Semgrep jobs (default 2), passed into
the same pinned container via its supported --jobs option, to avoid
oversubscribing the shared test host. No
rule, target, severity, exception or scanner requirement is changed. The first
scans timed out at 900 seconds and are not counted as passes. Local scanner
processes now have a 3600-second wall budget on the shared host; hosted GitHub CI
keeps its 900-second budget. A complete clean report remains mandatory.
Claude can use this section at the top of the PR.

## Shipped surface and offline coverage

| Feature | Merged evidence / current code | Existing offline path |
| --- | --- | --- |
| Official FFL reference, monthly changes, collector inclusion, reference adoption and persistent blocked-source handling | #440, #450 and subsequent main; `tank/base_reference_status.py`, `agents/base/engines/ffl/reference.py`, `tank/base_repository.py` | `test_base_atf_download`, `test_base_reference_adopt`, `test_base_reference_file`, `test_base_database` |
| Upload/enrich batch, task collection and tenant-owned records | `tank/base_product.py`, `agents/base/pipeline.py`, `tank/base_repository.py` | `test_base_workflow`, `test_base_product`, `test_base_database` |
| Records UI, search, per-contact page/date, complete contact CSV, formula protection and unknown cost | #450; `workspace/app/base`, `tank/base_evidence.py`, `tank/base_metrics.py` | `test_base_product`, `test_base_page`, `test_base_unknown_cost`, `test_base_product_origin`, `test_base_proxy_boundary` |
| HTML-only email/phone quality and contact provenance | #623/#647; `tank/skills/base.contacts`, `tank/base_evidence.py` | `test_base_contact_quality`, `test_base_wave4` |
| Own-site social presence, MIT pinned technology signals, online sales and newest-year evidence | #647 and earlier shipped skills; `tank/skills/base.socials`, `tank/skills/base.site_signals`, `tank/base_evidence.py` | `test_base_readiness`, `test_base_site_signals`, `test_base_contact_quality` |
| Verified find filters, saved immutable lists, list enumeration/show/export and CRM handoff | main B4; `tank/base_lists.py`, `tank/base_list_crm.py`, `tank/command.py` | `test_base_lists` |
| Product extraction, provenance, product filters and separate product CSV | #603/#623; `tank/skills/base.extract`, `tank/base_lists.py`, `tank/base_metrics.py`, Base download route | `test_base_products`, `test_base_list_products` |
| Ledger-linked list costs, unknown missing/shared allocation and fixed-point decimal CSV | #623; `tank/base_metrics.py` | `test_base_list_costs` |
| Founder state campaigns, sequential dispatch, progress and evidence report | #647; `tank/base_campaign_commands.py`, `tank/base_repository.py` | `test_base_readiness`, `test_base_database` |
| Saved 200-record reproducible human audit, checked upload, Wilson interval, histogram and explicit field/source reliability | #603/#647; `tank/base_audit.py`, `tank/base_audit_commands.py`, `tank/base_reliability.py` | `test_base_audit`, `test_base_audit_commands`, `test_base_source_reliability`, `test_base_readiness` |
| Apollo-only uploaded CSV comparison, field agreement, ambiguity and ownership guards; $0 existing card | #647; `tank/base_compare.py`, `tank/command.py` | `test_base_wave4` |
| FFL manifest/package and neutral vertical scaffolder, unchanged FFL bytes | #647; `agents/base/engines/ffl/manifest.json`, `agents/base/engines/scaffold.py` | `test_base_wave4`, existing FFL tests |
| Founder trial, measured receipts and source-generated review candidates | main; `tank/base_product.py`, `agents/base/trials`, gold-source helpers | `test_base_trial_launch`, `test_base_gold_sources`, `test_base_gold_nightly`, `test_base_database` |
| Existing Base vault/plugin controls and protected Workspace proxy | `workspace/app/base`, existing shared vault routes | `test_base_page`, `test_base_product_origin`, `test_base_proxy_boundary` |
| Base case-study report API, figures, saved Apollo scoreboard and tenant/period/audit projection | `tank/case_studies.py`, `tank/case_study_sources.py`, existing Workspace API | `test_case_study_reports`, `test_case_study_apollo_scoreboard` |

## Approval boundaries

- `base.contacts/1.4.0` is shipped as a minor **candidate**, not implicitly approved.
  Evaluate it and use the existing founder Skala approval flow before runtime pinning.
- FFL engine SOT and compliance flags remain empty. No Google Places, paid feeds,
  carrier lookup, GPL fingerprints or review-content fetch is added.
- [Base case-study audit frames](../figma/base-audit/REGISTER.md) are Proposed,
  not approved. List these frames for review; do not build a new audit page or copy.
- The founder sheet will describe the completed shipped behavior. It will never
  assert that an endpoint from another branch must remain missing.

## Offline verification

- Final complete Base, command/token, earlier wiring and 55-row acceptance run:
  **783 passed, zero skips**, 16 existing warnings, 555.20 seconds. External
  sockets/models are blocked; real PostgreSQL is disposable and loopback-only.
  Worker responses are scripted fixtures; browser cases execute real Base code.
- The sheet has **55 founder rows and 55 corresponding fixture cases**, plus the
  exact one-row/one-case and command/settings validation check.
- Focused large-page/cap checks: **13 passed**. Flat-image correction: **16 passed**.
- Security-policy focused rerun: **59 passed and 34 subtests passed**. Earlier
  complete security suite: **64 passed and 56 subtests passed**.
- A concurrent final run stopped on local HTTP/browser timeouts (479 passed);
  the complete serial rerun above passed the same paths without changes to their
  assertions. Initial Semgrep wall timeouts are not passes.
- Security precheck remains mandatory before every push, without any
  gitleaks/Semgrep exception. CI and push results will be recorded after completion. The first job-cap attempt
  used an environment variable unsupported by the pinned CLI; it was corrected to
  its explicit --jobs option before the final precheck.
