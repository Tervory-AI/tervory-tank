# ZA Laws.Africa preparation — blocked at the required documentation check

Branch: `codex/zenas-za-laws-africa`.
Started from fetched main `a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0` on 28 October 2026. The branch was pushed immediately. The fetched main history contains no `#372` merge; no unmerged PR was imported and no PR was merged here.

**Not ready for Friday. This commit contains this blocker/proof document only. No product code has changed.**

## Exact blocker

Required source: https://developers.laws.africa/ (Content API v3 documentation).

The managed cloud's enforced network policy does not permit `developers.laws.africa`. The HTTPS request failed at the proxy's CONNECT step, before reaching the documentation:

```text
curl: (56) CONNECT tunnel failed, response 403
HTTP 000
```

The saved proxy response starts:

```text
HTTP/1.1 403 Forbidden
server: envoy
```

Missing: cloud network access to **`developers.laws.africa`** for the mandatory public documentation check. No API token is needed to perform that documentation check. No secret was read, entered, generated, or requested.

Rule 9 in `docs/build/MILESTONES-28OCT-1NOV.md` says: **“If something blocks you (a missing setting value, missing Figma text, a file you may not change), stop at that point and report exactly what is missing. Do not ask, do not guess, do not work around it.”** Implementation stops here. No alternative endpoint, undocumented request shape, invented API recording, or assumed commercial licence has been substituted.

## Documentation verification still required

| Required fact | Status |
| --- | --- |
| Content API v3 authorization scheme | Not verified against the docs. Existing code sends `Bearer`; its correctness is not claimed. |
| National works listing and current consolidated expression endpoints | Not verified. |
| Pagination shape and termination | Not verified. |
| Changed-since filter, ordering, and synchronization semantics | Not verified. |
| Rate limits, throttling responses, and retry rules | Not verified. |
| Commercial-use licence and required attribution | Not verified. |

The requested verbatim documentation quotations and their precise page URLs cannot be supplied until the source is readable. The repository's existing authentication documentation reference is https://developers.laws.africa/get-started/authentication; that reference is not evidence that the page has been read or that the current implementation is correct.

## Current code findings, not completed fixes

- `agents/zenas/pool/adapters/za_common.py:23`: `bearer_headers` constructs the existing `Bearer` authorization header. It was not changed without verifying the required scheme.
- `agents/zenas/pool/adapters/za_akn.py:21`: `ACTS` contains eleven fixed instruments. `LawsAfricaAdapter.fetch` fetches an individual expression; it has no full national works listing or listing pagination.
- `agents/zenas/pool/adapters/za_akn.py:112`: `_frbr_date` takes the first parseable FRBR date. `parse_akn` uses that date for both document date and effective-from date; the required consolidation/point-in-time semantics still need checking against recorded API data.
- `agents/zenas/pool/catalogue.py:341`: the Laws.Africa catalogue is generated from that fixed list. The current catalogue statements are not a substitute for the requested licence/attribution verification.
- `agents/zenas/docker-compose.za.yml:16` and `:56`: `LAWS_AFRICA_API_TOKEN` is forwarded to the optional `pool-loader` service, **not** the normal `agent-zenas` service that must handle the screen's load request. Setting the resource variable alone is therefore not sufficient with the current Compose wiring.
- `agents/zenas/pool/catalogue.py:369`: SAFLII has a catalogue entry. Its live configuration was not inspected or changed; no claim is made that it is disabled on the ZA box.

No civil/criminal scope policy, page copy, layout, source switch, live setting, database, or Boston configuration was changed.

## Commands and results

Cloud working directory: `/workspace/tervory-tank`.

```sh
pwd
git status --short
git branch --show-current
git fetch founder main
git log -8 --oneline founder/main
git switch -c codex/zenas-za-laws-africa founder/main
git push -u founder codex/zenas-za-laws-africa
```

Results: cloud path confirmed; clean starting worktree; main fetched successfully at `a99f3cb`; new branch created from it and pushed. Git reports the repository redirect to `Tervory-AI/tervory-tank`. No GitHub API was used.

```sh
curl --silent --show-error --location --max-time 20 --dump-header /tmp/zenas-laws-africa-docs.headers --output /tmp/zenas-laws-africa-docs.html --write-out 'HTTP %{http_code}\n' https://developers.laws.africa/ && head -15 /tmp/zenas-laws-africa-docs.headers && head -12 /tmp/zenas-laws-africa-docs.html
```

Result: exit **56**, proxy CONNECT **403**, origin HTTP **000**. The subsequent `head` commands did not run because curl failed. The proxy headers were then read with:

```sh
cat /tmp/zenas-laws-africa-docs.headers
git log -1 --format='%H %s' founder/main
git log --oneline founder/main --grep='#372'
```

Results: proxy response quoted above; main `a99f3cb` (`#368`); no `#372` match in fetched main history.

Runtime status and `/etc/codex/network-policy.json` confirmed restricted, enforced HTTP policy, with no allowance for the documentation host. No policy or proxy setting was changed.

No implementation tests were run: no implementation or recorded-response fixtures were created. The requested offline cases remain outstanding: complete paginated listing, changed-work synchronization, rate-limit back-off, invalid token, no-token state, ZA-only credential handling, SAFLII disabled, and a civil ZA answer with its section/version/link/attribution. No tests, source-link availability, synchronization, live load, or Friday acceptance are claimed as passing.

## Friday checklist — acceptance plan, pending implementation

Before this can become a key-only activation, finish the documentation verification and implementation, run all requested offline tests, incorporate `#372` from main when merged, deploy the reviewed work, confirm the normal ZA room receives the setting by name, and verify nightly task configuration. These are unresolved prerequisites, not founder activation steps already completed.

Once those prerequisites are complete, the founder's activation and checks are:

1. Open Coolify resource **`agent-zenas-za`** on the **ZA box**. Set **`LAWS_AFRICA_API_TOKEN`** there only. The value must never be copied to Boston, a URL, a log, a test, or this document. Apply the setting to the running room using Coolify.
2. Open **`/zenas/feeds`** on the ZA-serving Workspace. Verify the displayed region is ZA and SAFLII remains off. Select the Laws.Africa feed and press its existing **“Load now”** control. The final feed selection must be confirmed after the catalogue change is implemented; no new label is invented here.
3. Watch the real document counts fill. Confirm the full national Act/regulation listing has been consumed through every page, that the eleven existing minimum instruments loaded, and that the loader reports no failed page or expression. Count sections/documents according to the existing data model; do not equate section count with work count.
4. Verify stored sections have the publisher's working source link, consolidation/version date, point-in-time dates, and the attribution verified from the actual licence terms. Confirm these survive a repeat load. Check the next nightly run processes changed works without downloading unchanged expressions and preserves its successful synchronization checkpoint.
5. Open **`/zenas`** on the ZA-serving Workspace. Ask **“Under South Africa's Companies Act, may a company's board issue shares without shareholder approval?”** Verify the answer stays within civil law, cites the actual relevant stored sections, and includes their working publisher links and the existing legal-information notice. Open every citation and verify the source supports the answer. Do not pre-fill or fabricate an answer if the source is unavailable.
6. Capture the founder's screenshots of the populated feed counts, the real answer, and the opened sources. Record the actual section URLs/version dates and the nightly run outcome, without exposing settings values.

## Founder proof

Pending. No founder screenshots, paid API responses, live count increase, or cited live answer have been supplied or produced. This is a blocked preparation branch, not a completed integration or a ready-for-review claim.
