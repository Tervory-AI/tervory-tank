# AGENT-1: give each squad member a real brain (Hermes Agent), its own computer, browser and working memory

> Written 20 Oct 2026. The Build Pack says every squad member has: a **Hermes Agent** brain, a private Memory Bank, a Skills Bank from Skala, and its own computer.
>
> **Today the rooms are services, not agents.** They run fixed code pipelines and call Tank:
> - **Brain:** none. No agent loop plans, uses skills or learns.
> - **Memory:** our `hermes/` service is only the memory store. Rooms write to it, but nothing ever reads it back: no `.recall(` call outside the chassis.
> - **Browser:** one shared browser service (`tiger`, Chromium plus OCR), used by Tiger and Base.
> - **Computer:** each room is its own container with its own disk and network corridor, but has no sandbox for open-ended work.
>
> Pilot on **Base** first, measure the receipts, then roll out room by room.

**Files you may change:**
- `agents/base/` (the brain service and its compose);
- new `agents/_brain/` (shared adapter code, reused by later rooms);
- `tank/` (a new OpenAI-compatible route only; route registration in main.py);
- `hermes/` (recall API additions only);
- `docs/cursor/ROOMS.md`;
- tests.

1. **Brain:** run Nous Research **Hermes Agent** inside the room's own container. Check its licence first and record it in the PR. Pin the version.
2. **Every model call goes through Tank.**
   - Tank exposes `POST /v1/agents/{room}/chat/completions`, OpenAI-compatible and authenticated with the room's key, which Hermes Agent uses as its custom endpoint.
   - Tank maps each call to task type `agent.<room>.think` and routes it by policy (cheapest proven model) with a ledger row and receipt, like any call.
   - The room holds no model keys.
3. **Skills only from Skala.**
   - Hermes Agent's skills folder is filled only from Skala's approved skills for that room (exported in agentskills.io format).
   - A skill Hermes Agent writes for itself is submitted to Skala as a **candidate** and is not used until evals pass and the founder approves it.
4. **Memory that is actually used.**
   - Every task starts with a recall from the room's own Hermes collection, for that tenant only, and ends with a remember with its sources.
   - Hermes Agent's own session memory lives on the room's volume.
   - Nothing crosses rooms, tenants or regions.
5. **Its own computer:** Hermes Agent's Docker sandbox backend runs inside the room, with no internet except the room's allowed hosts. Every run writes to the room's own volume only.
6. **Its own browser:** a separate browser profile per room from the shared browser service. Cookies, storage and history are never shared between rooms. Human checks (captchas) are recorded, never solved.
7. **Receipts:** each agent task shows its steps (recall, skills used, model calls with cost and baseline, browser and sandbox actions) and feeds the COMMAND-1 work panel when called from the window.
8. **Pilot Base:** keep today's code pipeline as the default. The brain plans and runs it, and handles the records the pipeline cannot finish, before any paid step.

## Done when
CI green. Tests:
- the brain's calls arrive at Tank on the room key, with ledger rows;
- the room has no model key;
- an unapproved self-made skill is not loaded;
- recall happens before work and returns only that tenant's memories;
- the sandbox cannot reach a disallowed host;
- two rooms' browser profiles share no cookies.

Then a recorded Base run on a small ATF state, with its receipt, linked in the PR.
