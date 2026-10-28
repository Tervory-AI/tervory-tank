# Grok: wire up the ZA Zenas box (27 Oct 2026, 18:25 PT)

```
RULES (founder, non-negotiable):
1. Product first. No sign-in work, pricing, keys, Stripe, credits or spend caps.
2. Figma first. Nothing new goes on any page without an approved Figma frame, matched to the character. Do not add text, buttons, empty states or error wording. If you need one, stop and report it.
3. No sample, demo or fixture data on any live screen, and no made-up copy.
4. No model calls where code can do the job, and none to check work.
5. Use what already exists and is free; never recode it.
6. Never type, see or create secrets. Coolify settings are handled by name only; the founder fills in values.
7. The founder merges. Never push to main. One draft PR, then stop.
8. No SQL on production data and no permanent live-data change without the founder's OK.
Done means the founder sees it work in his own browser. Tests passing is not done.
Deviate from this brief and the thread is deleted with its work.
9. DO NOT ASK QUESTIONS. Follow these instructions exactly as written. You are pre-approved to do everything in this brief except merging. If something blocks you (a missing setting value, missing Figma text, a file you may not change), stop at that point and report exactly what is missing. Do not ask, do not guess, do not work around it.
10. A separate review thread checks your PR against this brief. Fix everything it lists, on the same PR, without arguing.
11. Your PR must show: what changed (file and line), the exact commands you ran and their results, and screenshots of the founder's test. Nothing claimed without that proof.

JOB: bring up Zenas for South Africa on the new ZA box. The founder decided this on 27 Oct: attorneys confirmed that clients acknowledge court-record details are public record. Zenas stays civil only. The law is about precision, not speed.

The code exists; do not rebuild it:
- the ZA stack is docker-compose.za.yml (Postgres, Redis, Qdrant, Hermes, LiteLLM, Tank; za.tervory.com -> tank:8000; no US hostname, no shared network with Boston);
- the Zenas room is agents/zenas/docker-compose.za.yml (TANK_REGION za).

1. COOLIFY (names matter, because .github/scripts/deploy_changed.py finds apps by name):
   - Add the new box as a server.
   - Create the stack resource named exactly "tervory-tank-za" from docker-compose.za.yml, with za.tervory.com on tank port 8000. Every other service stays internal.
   - Create the room resource named exactly "agent-zenas-za" (Base Directory /agents/zenas, Compose Location /docker-compose.za.yml).
   - Create every setting the two files need BY NAME ONLY, then give the founder the list to fill in. The list includes TANK_API_KEY, TANK_KEY_ZENAS, AGENT_DB_PASSWORD_ZENAS, ZENAS_PII_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID_ZENAS, R2_SECRET_ACCESS_KEY_ZENAS and the LiteLLM model keys. Use .env.example for the exact names. Wait for him.

2. OWN CLOUD STORAGE (one small draft PR):
   - Today both the US and ZA Zenas rooms use the bucket "tervory-zenas" (agents/zenas/docker-compose.yml:17 and docker-compose.za.yml:19), so ZA and US files would mix.
   - Change the ZA file only to R2_BUCKET: ${R2_BUCKET_ZENAS_ZA:-tervory-zenas-za}.
   - The founder creates the bucket "tervory-zenas-za" and a token scoped to that bucket only.

3. BACKUPS TO THE CLOUD FROM DAY ONE (same PR):
   - The ZA stack keeps backups only on a local volume (za_backups).
   - Add the same encrypted nightly Postgres backup to R2 that Boston has (the r2-backup service in docker-compose.yml:270-303, jobs/train/backup.py), writing to the ZA bucket.
   - Switch it on, run it once, and prove one restore into a throwaway container (row counts side by side).

4. CONNECT:
   - On Boston's Workspace, set TANK_URL_ZA=https://za.tervory.com and TANK_API_KEY_ZA. The founder fills in the value.
   - Clear the repo variable ZA_OFFLINE, or ask the founder to, only after tervory-tank-za and agent-zenas-za are both healthy.
   - Run ops/seal-check.sh on the ZA box.

5. LOAD THE SA LIBRARY (docs/ops/ZENAS-LIVE-SUNDAY.md part 3):
   - The founder presses "Load now" on /zenas/feeds for ZA: the gov.za Acts and regulations and the official court archives. Watch the counts.
   - SAFLII STAYS OFF until SAFLII gives written permission.
   - Use GOVZA_MIN_INTERVAL=1 as .env.example says.

6. CHECK, with no model calls to check:
   - za.tervory.com/health is OK;
   - a ledger row appears on the ZA Tank, not Boston;
   - a criminal question is refused;
   - one civil SA question is answered with citations to the ZA library.

DONE WHEN: the founder, signed in as a ZA tenant, asks one civil South African question on zenas.tervory.com/zenas and gets a cited answer from the SA library, with its receipt. He also sees today's ZA backup file in the ZA bucket and the restore row counts.
```
