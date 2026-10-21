# Tervory: context for every builder thread

> Read this first, then your lane's brief. Written 20 Oct 2026. The founder merges; Claude reviews every PR.

## What Tervory is
- **Tervory is a platform:** one router (**Tank**) and a squad of specialist agents.
  - **Base:** verified business lists, starting with the ATF FFL list.
  - **Tiger:** prices.
  - **Market Lab:** market shifts.
  - **Rig:** products and the parts that fit.
  - **Tisan:** sites.
  - **Radix:** scans.
  - **Zenas:** legal, US and SA, civil only.
- **The core promise is cheaper and provable.** Every model call goes through Tank, which takes the cheapest proven step (plain code, then the cheapest model that has proven itself, then our own trained model) and leaves a receipt: what it cost, what it would have cost on the baseline model, and the saving.
- **Nothing switches model by itself.** The founder promotes, after held-out gold examples and shadow evidence.
- **Skala** holds the skills, with their versions, evals and approvals. Skills are shared across regions; data is not.

## Where things are
- **Repo:** https://github.com/Tervory-AI/tervory-tank (monorepo).
  - `tank/`: router, ledger, Skala, gold, training.
  - `workspace/`: Next.js 15 app with Clerk; calls Tank server-side only.
  - `agents/<room>/`: one room per agent.
  - `litellm/`: model roster.
  - `jobs/train/`: Hugging Face training.
  - `workers/`: Tervory's own build workers.
  - `docs/cursor/`: briefs.
- **Live:** https://app.tervory.com (Boston, US, USD). **ZA box:** tank-za and agent-zenas-za. za.tervory.com is planned (ZA2).
- **Architecture diagram:** https://www.figma.com/board/69WVHSalRk3gPU0ZMdZFc2
- **The window (COMMAND-1) wireframe:** https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
- **Rules:** `AGENTS.md` and `docs/cursor/ROOMS.md`. Read both.

## Where it stands (20 Oct)
- **Routing and the ledger work, but almost nothing runs through them:** 7 Boston model calls in 30 days.
- **Shadow testing is built but off.** No task has a candidate model.
- **Gold is empty:** 0 of 100 checked examples per task.
- **Training is built but has never run,** and no trained model can be served yet.
- **The build workers are built but not deployed.**
- **#210 just fixed it so Tank lists its models.** Before that, the cheapest-model search saw an empty roster in production.

## Hard rules
- **Pre-launch (founder, 21 Oct): there are no clients yet.** Test with real public data freely, including the R2 buckets (BUCKET-1). Client-data rules apply from the first real client.
- **Client screens are clean.** No internal words (Skala, Tank, ledger, eval, gold, shadow, retire, model names) and no text dumps. The detail lives in founder screens. Match the approved Figma: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
- **Every squad member has its own box:** its own Hermes Agent, sandbox, browser, memory and bucket. It shares nothing and talks only to Tank and Skala.
- Every model call goes through Tank. Rooms never hold model keys. The Workspace never calls a room directly.
- SA client data stays on the ZA box, and nothing is proxied between boxes. Decided cases and legislation are public record.
- No criminal law in Zenas. No tracking or profiling of individuals.
- No secrets in code, URLs, logs or tests. Variable names only in `.env.example`.
- Never change an approved skill version in place: add a new version.
- Schema changes are additive, tested on an empty database and re-applied.
- Never fail silently. A missing key or an unreachable service shows an error and changes nothing.
- Use plain English in the UI. No placeholder text. Use the exact logo files; never redraw a logo.

## How to work
- **Run in the cloud only, never on the founder's computer.** Use your cloud or background agent, with its own cloud machine. Do not clone the repo, install packages, run builds, run tests or start servers on the founder's laptop. If you are running locally, stop and say so. CI runs the tests; Claude checks production through Coolify.
- Branch from the latest `main`, and stay inside your brief's "Files you may change".
- Put new logic in new modules. In shared files (`tank/main.py`, `tank/schema.sql`), add only route registrations and additive schema, to keep merge conflicts small with other lanes running in parallel.
- **CI only runs on PRs.** Open one draft PR to run it, and mark it ready only when every check is green.
- One PR per lane. Never push to `main`. Do not merge: the founder merges after Claude's review.
- End the PR description with what changed, the tests, and screenshots at 375px and 1440px for any UI.
