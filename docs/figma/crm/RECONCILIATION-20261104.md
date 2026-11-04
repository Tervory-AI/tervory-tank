# PR #436 — CRM correction/evidence reconciliation

**Reconciled 4 November 2026; documentation only.** Existing branch `codex/crm-design`; source head `314bf2737c49a69c651412c9b339a196225a8f01`; main snapshot `fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab`. GitHub reported the open PR unmergeable, confirming the documentation conflict. A single manually resolved merge commit uses the source PR head and this main snapshot as its parents. It preserves the complete main tree except the explicit documentation/evidence overlay. No force push, main push or PR merge is performed.

## Authority and result

Unique valid evidence remains; do not close #436 as wholly superseded. Preserve its 10 PNGs, two node CSVs, three JSON records, dated audit and historical node/source registers. Do not restore the old replacement SPEC wholesale. The canonical CRM content from main remains an exact prefix of SPEC.md with one scoped reconciliation appendix. The canonical case-study SPEC is byte-identical to the main snapshot. Current approval labels, exact existing wording and founder-review boundaries remain unchanged. No new product words, Figma node writes, screenshots, model/API/payment calls, production SQL, deployment or Skala approval occur in this task.

## Disposition matrix

| PR material | Decision | Exact controlling/provenance evidence |
| --- | --- | --- |
| CRM all-guidance replacement preamble and old dark/navy-fill rules | Discard as controlling instructions; preserve in labelled history | Main CRM SPEC’s 1 Nov founder-review sections stay verbatim; PR source Fix round 4 supersedes its own earlier navy-filled Confirm prose. |
| Fix round 4 contrast, 8px corners, 44px targets, shared headers and Full name records | Retain as unique dated correction evidence, not new approval | `314bf273`, existing `evidence/2026-11-03-fix4/README.md`, 10,981 distinct written IDs, 1,120 distinct created IDs, final-checks.json and seven PNGs. |
| Proposed address-ownership phrases | Retain exact phrases and proposal status | Existing new-words.json has 15 mappings, all Changed after approval, awaiting founder; no proposed phrase is silently promoted to Approved. |
| 16 confirmation-footer 104px clearances | Retain explicit exceptions | final-checks.json spacing equals spacing-exceptions.json; the old report did not prove full 0/8/16/24 compliance. |
| 94 original CRM roots / 99 scrolled review views / two drawer end states | Carry forward IDs and authoring notes in history and correction appendix | Source SPEC sections Changed screen node register and Fix round 2; fixed table-review roots 310:35765 / 310:36136 / 310:36516 / 310:36821, drawer end roots 310:39581 / 310:39786. No live-canvas re-read is claimed. |
| Contacts and Client/customer deduplication | Retain scoped correction record; do not rename canonical text globally | Source SPEC: Contacts source 97:2543 / 97:2800 / 97:3060 / 97:3200, four full-width Client field IDs, hidden account_detail wrappers; Fix round 3 records 116/116 historical field coverage. |
| Record payment required fields vs Mark paid optional fields | Retain source finding; no payment execution | Main confirmation data paths already distinguish PaymentCreateRequest from PatchedPaymentCreateRequest. Source Fix round 2 cites pinned BottleCRM cd7c12a endpoint lines 762–789 and documents defaults; archive keeps exact citation, no new source claim. |
| Business switcher and direct product-heading text writes | Preserve proposal/history; newer shared heading property wins | Approved main MCP-MENU-20261103.md adds Product heading#508:0 to 180:8549 and binds 180:8394 / 180:8476. Do not repeat old direct heading writes. |
| Old second Trigger menu family 266:3212 | Superseded for live reuse; historical IDs retained only | Current main Marketing/Chat bot correction REGISTER.md explicitly says retired 266:3212 is hidden and shared 180:8387 / 180:8467 are used. |
| Case-study revision 3 founder-menu expansion and comparison-switch state | Not applied over canonical founder decisions; retained as historical proposal | Main case-study SPEC founder decision 1 remains unchanged, including its existing menu hierarchy; source PR adds Skala/Tank/Admin children and 28 destinations, which must not overwrite that contract from old screenshots. |
| Four revised product accents | Preserve proposal evidence, discard palette replacement in canonical SPEC | Main keeps Market Lab #6D28D9, Zenas #475569, Trigger #BE185D, Autumbra #A21CAF as proposed. PR proposed #5B21B6 / #3F6212 / #B91C1C / #0E7490; neither set is newly Approved. Old/new board 89:10434 and screenshot remain history. |
| Case-study 24px label line boxes and old 40px desktop targets | Preserve historical observation, not a current menu target instruction | Newer CRM/shared-menu correction records use at least 44px targets. Do not regress them to the old case-study fixed 40px desktop setting. |
| Blanket client-dashboard/sidebar rejection from historical PR discussion | Do not reactivate as a global gate | Current main DASHBOARDS-W4.md says Client dashboard — completed and Restored the approved five-item navigation. Protected 12:2 / 20:2 remain its source; #436 cannot revoke that current approval or replace its menu. |
| 30 Oct audit and three legacy screenshots | Retain unchanged payloads as dated provenance | AUDIT-2026-10-30.md remains tied to f9114e1; old native-SPEC availability and CI are not current acceptance. CRM/Case-study legacy PNGs are not founder-browser tests. |

## Current registers compared

These exact main blobs are recorded in [the manifest](RECONCILIATION-20261104.json). Links below pin the inspected commit, so later updates do not silently change this evidence.

- [docs/figma/crm/SPEC.md](https://github.com/Tervory-AI/tervory-tank/blob/fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab/docs/figma/crm/SPEC.md) — blob `1ba728bf7e6e11e1c8cf02507ed36889e9bda1f9`.
- [docs/figma/case-studies/SPEC.md](https://github.com/Tervory-AI/tervory-tank/blob/fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab/docs/figma/case-studies/SPEC.md) — blob `e80ed53eb86346028747ed2ecd967f8682068843`.
- [docs/figma/MCP-MENU-20261103.md](https://github.com/Tervory-AI/tervory-tank/blob/fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab/docs/figma/MCP-MENU-20261103.md) — blob `ed139ca3d9e5b9e471e79ebe47fff25bb95777a0`.
- [docs/figma/crm/evidence/2026-11-03-corrections/REGISTER.md](https://github.com/Tervory-AI/tervory-tank/blob/fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab/docs/figma/crm/evidence/2026-11-03-corrections/REGISTER.md) — blob `5439bdd4143785494b6078b1ffd045c70a5162c2`.
- [docs/figma/DASHBOARDS-W4.md](https://github.com/Tervory-AI/tervory-tank/blob/fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab/docs/figma/DASHBOARDS-W4.md) — blob `888f269aa58044c52215ea36ed60da5ffbb6c568`.

## Preserved authoring evidence

PNG files are the original PR-head bytes, not newly captured live-canvas images. All 10 PNG hashes and dimensions, all preserved evidence blob IDs, and archived text payload hashes are in the manifest. The screenshots may show a superseded surface or wording; they document that source revision only.

| File | Recorded frame / scope | Evidence |
| --- | --- | --- |
| [180-8387.png](evidence/2026-11-03-fix4/180-8387.png) | 180:8387 | 241 × 900; `4105fe8ec73c274c00519e852f102f98719a59b09fdc36a711255412c758d8b1` |
| [310-36136.png](evidence/2026-11-03-fix4/310-36136.png) | 310:36136 | 1440 × 900; `d708cee25346b4ed05403ce492ca80c3e1d9a97892a2e7e928130e933b45cfc3` |
| [310-36821.png](evidence/2026-11-03-fix4/310-36821.png) | 310:36821 | 375 × 812; `6118fa6775f8d1e00a2c1a796728c8699eb6cf45e51b96a8428c8e449ac967b8` |
| [94-417.png](evidence/2026-11-03-fix4/94-417.png) | 94:417 | 1440 × 900; `c43449100ca198db64cdccd8d9008f59435918a5ed7d7f81e21dd54d63622914` |
| [94-682.png](evidence/2026-11-03-fix4/94-682.png) | 94:682 | 375 × 812; `8dfa9d6e36160b9f96310be4c7b400a3c44a6fbc15499a1c12d605ed32252728` |
| [98-9050.png](evidence/2026-11-03-fix4/98-9050.png) | 98:9050 | 375 × 812; `714ed95cb7aab4cc0c0a8a18f0fd38caf988fee362b30ed70f172b3352d82fab` |
| [98-9181.png](evidence/2026-11-03-fix4/98-9181.png) | 98:9181 | 375 × 812; `428b8a9f2528b64ecf8bc94520149fb5a8c369918d0171561963bdd3312a2bb1` |
| [case-study-accents.png](evidence/case-study-accents.png) | Legacy 28–30 Oct authoring | 1036 × 344; `cdc0417b1de13a058cc2336f51bff5da6b02fb7787c62deace5d05caf42858c5` |
| [case-study-tiger-filled.png](evidence/case-study-tiger-filled.png) | Legacy 28–30 Oct authoring | 1440 × 900; `afe1fab7f02128cfba15a0cbe76189788fadc2a2479ab09d53352370d6cfb361` |
| [crm-leads-desktop.png](evidence/crm-leads-desktop.png) | Legacy 28–30 Oct authoring | 1440 × 900; `4221730ba6c91b30e28466bf7adfd560980984d07cd8129b7b79137b033658c4` |

## Focused validation and limits

Run `python3 docs/figma/crm/validate_pr436_evidence.py`. It checks exact canonical text preservation, the archived source payloads, every preserved evidence hash/PNG CRC, CSV ID counts/uniqueness, the 15 still-pending proposed labels, the 16 declared spacing exceptions, relative references in the reconciliation/appendix, and existing Figma node-ID syntax. It performs no network access, Figma write or runtime work.

Original screenshot files and evidence records remain byte-identical to the PR head; README.md gains a dated provenance note only. Focused results are recorded in VALIDATION-20261104.json. No full local application suite is run for this documentation-only reconciliation. Final-head hosted CI is the result of record; its actual result is reported in the PR/chat rather than copying old green checks.

Hosted CI on reconciliation head c4bed027 flagged the public Figma document identifier in the preserved final-checks.json as a generic API key. The exact historical finding is recorded in .gitleaksignore, following the repository's existing Figma-identifier fingerprint convention; no value, path or rule exemption is added. The identifier is the one in the founder-supplied design URL and grants no access. A redundant SHA-1 Git-blob check was removed from the validator; canonical text integrity remains checked with SHA-256.

One remaining design acceptance item: founder visual acceptance of the explicitly pending CRM correction/address-wording proposals. This does not block completing the requested documentation conflict resolution. No approval is inferred from CI or screenshots.
