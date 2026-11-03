# Trigger LanguageTool 1.1.0 migration

The runtime replacement shipped separately in #536. This change supplies the
compatible versioned checker and stages its evals through the existing intake.
It never approves a package, changes the approved pointer or modifies lifecycle
gates. Existing 1.0.0 files remain byte-for-byte unchanged.

## Observed production state, 1 November 2026

- Trigger deployment `fbqof1e8cvx1koflfig9dwd9` finished at commit
  `c5d6b10ed52e4b25afe8537d2da856cf8f27abcf`.
- Deployment workflow [41288028793](https://github.com/Tervory-AI/tervory-tank/actions/runs/41288028793)
  passed both deployment and live checks.
- All 14 Coolify applications reported `running:healthy`; each latest deployment
  was `finished`. This observation does not establish skill compatibility.
- A read-only query confirmed `trigger.languagetool@1.0.0` is approved.
- A real authenticated adapter request with synthetic text `This are a test.`
  returned HTTP 200, LanguageTool 6.8, build `1980-02-01 00:00:00 +0000`,
  premium false, and rules `PLURAL_VERB_AFTER_THIS` and `THIS_NNS`.
- The adapter reported image
  `meyay/languagetool:6.8-14@sha256:80de71abb2d797511240c3b47e0b4d1ed855ada49c92c8d2ee152f9aa1725aec`
  and config SHA-256
  `68cccc1515e9059d464cc50d17b7d7b981dd0ac66b3680e9a743a9c454e706f4`.
  The new package pins both values; the approved old package correctly refuses
  this image. Container health alone therefore does not restore approved checks.

The local candidate checker was also executed against the deployed adapter through
a Docker-exec HTTP bridge (the real key stayed inside Tank). Version 1.1.0
returned the expected rules for `This are a test.`, no issues for
`This is a test.`, and zero model calls. Version 1.0.0 rejected that same live
replacement image. This verifies candidate compatibility without approving it,
writing a production ledger row or changing production approval state.

## Review and rollout

This PR changes Tank packages/intake, which deploys Tank and its ZA copy on merge.
It has no room/runtime config changes. The Trigger runtime prerequisite already
shipped in its separate PR, as required by AGENTS.md rule 11.

After review and authorized merge, verify the new package's recorded evals and
source evidence. Approving 1.1.0 is a separate founder action: do not approve it
merely because its package exists or its tests pass. Until approval the active
1.0.0 checker continues to reject the replacement image. After authorized
approval, verify approved checker execution with synthetic text and zero model
calls. Then inspect the current deployment targets before rerunning failed
workflow 41282709186: it skips only applications deployed on current main, so
apps on older commits may restart even when healthy. Recheck all 14 latest
deployments and live checks afterward. No data loads are part of this repair.

Rollback of the skill alone is insufficient: 1.0.0 requires its exact 6.8-13
image, currently unavailable upstream. Restore a verified copy of that image
before attempting service restoration with the old skill. A rollback against
the replacement runtime must fail closed; never relabel image provenance.
