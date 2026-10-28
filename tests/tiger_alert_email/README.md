# Tiger alert email — local proof and configuration

New confirmed price/stock alerts now create a persistent mail receipt in the same database transaction as the alert. Tiger's existing per-tenant minute dispatch sends due receipts using Rig's unchanged `SmtpMailer`. The source watch's preferences still control alert creation; delivery also checks its current enabled/price/stock preferences. No new page or email wording, sign-in work, model calls or production data changes were made.

## What changed

- `agents/tiger/alert_email.py:45`: Tiger-only SMTP settings and exact tenant-to-address mapping. No default recipient or fallback to another tenant/Rig's settings.
- `agents/tiger/alert_email.py:88`: subject is the existing change sentence; body is the product name, that same sentence and the existing page link. Tests compare against the actual Workspace formatter.
- `agents/tiger/alert_email.py:124`: send due receipts, stable Message-ID per tenant/alert, definite SMTP rejection retries, and no resending accepted or uncertain handoffs. Up to three per dispatch, with a 30-second attempt limit.
- `agents/tiger/watch.py:623,817,836,846,865`: additive `alert_mail` table, transactional enqueue, atomic tenant-scoped claim/current preferences and persistent outcomes. Retry intervals start at 60 seconds and double to a one-hour cap. All reads/updates select tenant and alert IDs. `:1005` supplies the matching offline memory store; `:1101,1231` capture confirmed observation name/currency for the email snapshot.
- `agents/tiger/app.py:152`: drain mail through the existing tenant dispatch, so retries do not depend on another price change.
- `agents/tiger/Dockerfile:11`: include the new module and copy the existing Rig SMTP source into Tiger's image unchanged. The import was verified in an isolated filesystem matching the image layout.
- `agents/tiger/docker-compose.yml:29` and `.env.example:391`: wire/document setting **names only**. No values were created in Coolify or read from a live system.
- `tank/requirements-dev.txt:18`: install `aiosmtpd==1.4.6` for the local mail-catcher tests, the same library/version already used by Rig's proof. No runtime dependency added.
- `tests/test_tiger_alert_email.py:129,199,219,258,288,305,322,340,363,370,417,434,539,563`: five-page journey, all preference combinations across page/feed/portal sources, retry/backoff, concurrency, two tenants, paused/deleted watches, ambiguous acceptance, configuration isolation, copy parity, actual dispatch, Postgres persistence/rollback and failed checks.
- `tests/tiger_alert_email/page_copy.cjs:1`: run the existing Workspace formatter for parity assertions. The Workspace and Rig's source files are unchanged.

Old stored alert history is not backfilled into an inbox. Delivery receipts start with newly confirmed alerts after deployment. Existing observations/alerts and watch-retention behaviour are unchanged.

## Settings for Grok to create; founder supplies values

Only `agent-tiger` receives these settings:

| Name | Purpose |
| --- | --- |
| `TIGER_SMTP_HOST` | SMTP relay host |
| `TIGER_SMTP_PORT` | SMTP relay port; transport defaults to 587 |
| `TIGER_SMTP_USER` | SMTP login, when required by the relay |
| `TIGER_SMTP_PASSWORD` | SMTP login secret |
| `TIGER_SMTP_FROM` | Sender address |
| `TIGER_SMTP_ALERT_ADDRESSES` | JSON object mapping each exact tenant UUID to its alert address; no wildcard/default |

Missing or invalid tenant/transport configuration leaves mail pending. SMTP uses STARTTLS and the normal verifying SSL context from Rig's mailer. No SMTP or recipient value is needed in code, chat or this document.

## Delivery limits

Explicit SMTP rejections, refused connections and DNS failures retry with backoff. Successful sends are permanently marked sent. Concurrent workers cannot claim the same pending receipt, and a process restart does not replay sent receipts.

SMTP cannot establish whether a message was accepted when the connection disappears after DATA, or when the database fails after SMTP acceptance. To honour “never repeated”, this branch holds `uncertain` outcomes and interrupted `sending` receipts for reconciliation instead of automatically sending again. This can leave an interrupted message undelivered; it is not an exactly-once inbox guarantee. Tests cover both a failure after the catcher accepted DATA and a failed database receipt after acceptance, with no duplicate email. Neither a new on-page warning nor new email text was added.

## Commands and results

Base commit: `62db0f8a245d5680726d280b3a1a1acd358d580f`. Commands ran from `/workspace/tervory-tank`.

The existing mail-catcher dependency was installed into scratch space:

```sh
/workspace/.tervory-cloud/venv/bin/python -m pip install --target /workspace/tiger-alert-email/deps aiosmtpd==1.4.6
```

Disposable Postgres, with no production database, password or persistent volume:

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --rm -d --name codex-tiger-mail-pg --memory 256m --cpus 1 --tmpfs /var/lib/postgresql/data:rw -p 127.0.0.1::5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock port codex-tiger-mail-pg 5432
```

The assigned loopback port was `32768` for this run. A fresh run may assign a different port.

```sh
PATH=/workspace/.tervory-cloud/venv/bin:/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH PYTHONPATH=tank:/workspace/tiger-alert-email/deps TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32768/postgres TIGER_MAIL_EVIDENCE_DIR=tests/tiger_alert_email/evidence READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q tests/test_tiger*.py tests/test_tg2_tiger_watchlist.py
```

**182 passed** ([output](evidence/tiger-suite.txt)). After strengthening the Postgres test to check persisted retry/backoff as well as restart/concurrency, reran:

```sh
PATH=/workspace/.tervory-cloud/venv/bin:/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH PYTHONPATH=tank:/workspace/tiger-alert-email/deps TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32768/postgres python -m pytest -q tests/test_tiger_alert_email.py
```

**30 passed** ([output](evidence/mail-tests.txt)). This overlaps the 182 tests; it is not an additional 30 unique tests.

```sh
PATH=/workspace/.tervory-cloud/venv/bin:/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH PYTHONPATH=tank:/workspace/tiger-alert-email/deps READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q tests/test_access1_feeds.py tests/test_access1_review.py tests/test_agent1_skills.py tests/test_tank_one_door.py tests/test_agent_chassis.py tests/test_agent_roles.py tests/test_smoke.py
```

**89 passed, 1 skipped** ([output](evidence/related-suite.txt)). The skipped agent integration needed a disposable database setting; it then passed using the same local container:

```sh
PATH=/workspace/.tervory-cloud/venv/bin:$PATH PYTHONPATH=tank POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32768/postgres python -m pytest -q tests/test_agent1_skills.py
```

**1 passed** ([output](evidence/related-postgres.txt)). Thus all 90 selected related tests passed, including `test_smoke.py` with `PYTHONPATH=tank`.

```sh
PATH=/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH node --test tests/tiger_works/workspace.test.cjs
PATH=/workspace/.tervory-cloud/venv/bin:$PATH ruff check agents/tiger/alert_email.py agents/tiger/watch.py tests/test_tiger_alert_email.py
```

Both passed ([Workspace output](evidence/workspace-tests.txt)). Terminal evidence has trailing whitespace removed only. No GitHub Actions reruns or CI success is claimed.

Additional checks:

```sh
PATH=/workspace/.tervory-cloud/venv/bin:$PATH PYTHONPATH=tank python -m pytest -q tests/test_secrets.py
git diff --cached --check
```

**2 secret checks passed**; whitespace check passed. [Secret check output](evidence/secrets.txt).

The isolated image-layout import check ran:

```sh
/workspace/.tervory-cloud/venv/bin/python - <<'PYTHON'
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
with tempfile.TemporaryDirectory(prefix='tiger-mail-image-', dir='/tmp') as directory:
    target = Path(directory)
    (target/'agents/rig/rigbox').mkdir(parents=True)
    shutil.copyfile('agents/rig/rigbox/reserve.py', target/'agents/rig/rigbox/reserve.py')
    shutil.copyfile('agents/tiger/alert_email.py', target/'alert_email.py')
    subprocess.run([sys.executable, '-I', '-c', 'import sys;sys.path.insert(0,sys.argv[1]);from alert_email import SmtpMailer;assert SmtpMailer.__module__ == "agents.rig.rigbox.reserve";print("PASS Tiger image layout imports the unchanged Rig SMTP class")', directory], check=True)
PYTHON
```

Output: `PASS Tiger image layout imports the unchanged Rig SMTP class`. This verifies the copied module layout; it is not a full Docker image build or deployment claim.

The disposable database was removed after testing:

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock stop codex-tiger-mail-pg
```

## Local fixture proof

[Captured email](evidence/local-fixture-alert.eml) and [result](evidence/local-fixture-result.json):

```text
5 watched fixture pages
0 initial alerts
1 confirmed change
1 email accepted by the local catcher
0 duplicate emails after repeated dispatches and unchanged checks
Subject: Price went down from $120.00 to $115.00
```

The SMTP catcher never forwards messages and accepts only loopback test traffic. Its STARTTLS boundary is stubbed to avoid generating a certificate/private key; tests assert the unchanged mailer requests STARTTLS with certificate verification enabled. The SMTP dialogue and message acceptance/rejection use the real local catcher. This is not a deployed SMTP/TLS or inbox-delivery test.

## Founder acceptance still pending

No live configuration, deployment, real inbox or founder-browser proof is claimed. After Grok creates the setting names and the founder supplies their values and deploys the branch, the acceptance test remains: watch five real product pages and confirm a price/stock change reaches the founder's inbox. No founder screenshots exist in this cloud workspace; the `.eml` and JSON above are explicitly local fixture evidence.
