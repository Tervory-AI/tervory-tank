# SKALA-2: approvals that cannot go backwards, and one-click "Approve all ready"

> Written 20 Oct 2026. Approving base.find_site 1.5.0 (81.8%) would have retired the approved 1.7.0 (100%). There is no Retire button for staging and candidate versions. #208 adds 28 new patch versions that each need approval.

**Files you may change:**
- `tank/skala.py`;
- `tank/main.py` (skala approve, retire and rollback routes only);
- `tank/schema.sql` (additive);
- `workspace/app/skala/` and `workspace/app/api/skala/route.ts`;
- tests.

Do not change skill code or eval files.

1. **Approve only moves forward.** A version can be approved only if it is a newer version than the current approved one AND its latest eval score is at least the approved one's on the same cases. Otherwise the route returns 409 with a plain reason shown on the row ("1.5.0 is older than approved 1.7.0", "scores 81.8%, below approved 100%"). The Zenas made-up-case gate still applies.
2. **Rollback is separate.** "Roll back to X" works on a retired version that was once approved, with a confirm step, and records who and when.
3. **Retire works on candidate and staging versions** and never touches the approved one. When a version is approved, the skill's older never-approved versions are retired automatically.
4. **One row per skill:** the approved version plus the newest pending one. Everything else sits under a collapsed "History".
5. **"Approve all ready":** lists every version that passes rule 1, has at least 5 eval cases including a refusal, and passes its gate. The founder confirms the list once, and each approval is logged separately.
6. **Model-using skills:** an eval run counts only if every case passes on 3 consecutive runs. The row shows "3/3 runs".

## Done when
CI green. Tests:
- 1.5.0 is refused while 1.7.0 is approved;
- rollback works only with the confirm step;
- retiring a staging version leaves the approved one alone;
- approving a newer version retires the older candidates;
- "Approve all ready" approves exactly the listed set;
- a model skill passing 2 of 3 runs stays in staging.

Screenshots at 375px and 1440px.
