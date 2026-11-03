# DC campaign readiness and social evidence

Checked origin/main first at 981ac096; no main merge. Work remains on
codex/base-w4, PR #647. F5 is complete with the existing pinned MIT detector.
No GPL data, paid feed, review-content source, SOT or compliance flag was added.

## What the offline path proves

The test installs a disposable reference snapshot with DC as the smallest group,
confirms the real campaign adapter, submits exactly one DC job to a recorded room
transport, persists recorded worker evidence, runs the real collector and state
completion, reads records JSON, draws/reviews the human audit, and downloads the
campaign report. All database writes are to isolated loopback fixtures; outbound
HTTP and models are blocked. The worker's web/model enrichment is represented by
recorded fixtures, not a claim that a live model or site was called.

Two separate populations are tested: three DC records, and 200 DC records. These
are synthetic test counts, not current DC licence totals. The first exports real
fixture evidence with unknown audit metrics; the second produces 0.9 accuracy,
a Wilson 95% interval, and source scores from explicit field checks. Another
tenant cannot read the campaign, report or link. Source scores are platform-wide
aggregate counts only, as in the existing source-reliability endpoint; their
updated_at timestamps are included in the JSON cells.

The existing audit policy requires at least 200 verified records in ONE campaign,
enforced by both base_audit.py and schema.sql. A smaller live DC campaign can
finish and download its report but cannot draw this audit. Its accuracy and
interval remain blank; no sample, verdict or score is invented. This gate does
not lower that policy or rewrite its schema constraints. The 200-record fixture
proves the positive path without claiming that live DC meets the prerequisite.

## Exact founder steps in /chats

Use the founder's US workspace. Confirm every proposed card, including reads.
Values in angle brackets below come from prior results or the uploaded file's
stored reference; they are not literal IDs to submit.

1. Ask: `Run base.campaign.start with {"name":"DC readiness","states":["DC"],"types":[],"include_collectors":false}`. Confirm. This uses the existing reference campaign/worker path and its normal runtime cost ladder. The command handling receipt is $0; enrichment receipts remain separate. Copy campaign_id from Summary.
2. Ask: `Run base.campaign.show with {"campaign_id":"<campaign_id>"}`. Confirm. Repeat this read until Summary's states have finished and collection has caught up. Check verified_records. Failed states and missing observations remain visible/unknown.
3. If verified_records is below 200, download with step 8; the current audit policy cannot measure this campaign. Do not substitute a larger fixture count or claim accuracy. Otherwise ask: `Run base.audit.start with {"campaign_id":"<campaign_id>","seed":42}`. Confirm and copy audit_id from Summary. This saves a reproducible 200-record snapshot.
4. Ask: `Run base.audit.csv with {"campaign_id":"<campaign_id>","audit_id":"<audit_id>"}`. Confirm and open Result. This is the existing review form; its original columns and evidence stay unchanged.
5. Check the sampled evidence on its stated pages/dates. Set every row's verdict to correct, wrong or unsure. For source scoring, add optional columns website_verdict, phone_verdict, email_verdict and socials_verdict. Fill only fields you explicitly checked, using correct, wrong or unsure; leave absent/unreviewed fields blank. Do not change record IDs or any original evidence cells. Source scores are never inferred from the overall verdict.
6. Upload that checked CSV to the same chat. Ask: `Run base.audit.review with campaign_id <campaign_id>, audit_id <audit_id>, and attachment_id from my uploaded checked CSV`. Confirm. The code reader resolves the owned upload; the planner receives its stored ID without file contents. Explicit field columns are parsed by code and the original evidence still passes the existing immutable-snapshot validation.
7. Ask `base.campaign.show` again with the same campaign_id and Confirm. Summary now contains measurement.accuracy, confidence_interval and source_scores. The interval is Wilson at 95%; unsure fields do not count as correct or wrong. An overall record verdict alone does not establish a source's accuracy.
8. Ask: `Run base.campaign.csv with {"campaign_id":"<campaign_id>"}`. Confirm and open Result. The file is base-campaign.csv. It contains contact/social values with their individual source URLs and dates, source-backed identity dates when available, and the latest reviewed audit's accuracy, interval, sample size and review date. source_scores is JSON containing source/field counts, accuracy, Wilson lower bound and update date. Missing evidence or audit measurements stays blank/empty.

No live founder session or browser completion is claimed by the offline run.
The missing approved audit-page Figma frame remains listed in WAVE4.md; this
work adds no page or card label.

## F4 findings and compatibility

Each social link from the business's recorded HTML is retained in field_observations
with the page URL/date, then projected as an independently sourced socials.items
entry, stored by the collector and returned by records JSON. Pinterest and Yelp
presence links were recognized by base.socials but could fall out of the HTML
projection/CSV. They now survive through that same evidence path. This does not
fetch Yelp reviews or any profile page. Share/login links are not promoted to
profiles merely because a candidate list contains them.

The six existing network CSV columns keep their order and values. When additional
verified social profiles exist, three trailing other_socials columns carry the
links, matching source URLs and dates in order. Otherwise the existing main-list
CSV remains byte-identical. Each semicolon-separated item aligns with its source
and checked_at item. SOT/compliance flags stay empty.

## Review locations

- tank/base_campaign_commands.py: campaign argument contracts, confirmed existing execution path, tenant-scoped consistent read, $0 command receipts, sourced report CSV.
- tank/base_audit_commands.py: optional explicit per-field verdict columns in an owned uploaded CSV; original evidence validation retained.
- tank/command.py: founder campaign catalogue, adapters, and confirmed-dispatch binding for campaign start.
- tank/main.py: campaign router registration only.
- workspace/app/base/download/route.ts: campaign report download; existing audit/list/product/batch branches retained.
- tank/base_evidence.py: Pinterest/Yelp profile recognition and share-link guard.
- tank/base_metrics.py: conditional complete social export with individual source/date alignment.
- tests/test_base_readiness.py: both DC populations, confirmed start, collection, records JSON, audit/review, actual source aggregation, report metadata and tenant isolation; malformed field-column refusals.
- tests/base_campaign_download.cjs: download path, private response headers and upstream errors.
- docs/base/WAVE4.md: founder-confirmed F5 completion.
