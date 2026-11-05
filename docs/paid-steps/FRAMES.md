# Paid-step settings frame status

Read from `origin/codex/figma-w5:docs/figma/workspace/REGISTER.md` (PR #685). PR #685 has now merged: main contains these **Proposed** frames. Per the brief's instruction to build the switches once the frames land, the settings page now follows these frames at `/settings/paid-steps`. The prototype inventory is replaced with real configured steps, and tenant administrators are authorized as required by the brief. The founder-only global pause reuses its existing server action. No prototype or sample inventory is shipped.

| State | Desktop 1440 | Mobile 375 |
| --- | --- | --- |
| Default | 559:3085 | 561:3445 |
| Paused | 559:3249 | 561:3533 |
| Saved | 559:3414 | 561:3622 |
| Empty | 562:3565 | 562:3910 |
| Loading | 562:3679 | 562:3948 |
| Error | 562:3795 | 562:3988 |

File: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS

Backend: authenticated tenant administrators and founders read `GET /v1/command/paid-steps`, then write `PUT /v1/command/paid-steps/{step_id}` with `{"mode":"ask"}` or `{"mode":"auto"}`. The response lists real configured steps, not the five design examples. Default is Ask, independently for every tenant and step. Pending approvals and run receipts are available under that prefix. A room key cannot write settings or decisions.

The Workspace exposes the list and switch write through `GET/PUT /settings/paid-steps/api` using the existing sign-in and active tenant. PUT accepts `step_id` and `mode`, requires same-origin JSON, and forwards only the mode to Tank. No credential or tenant override is accepted from the body.

The existing /chats confirmation card handles reached steps now. The obsolete onboarding claim that nothing waits was removed by retaining the existing sentence prefix only: “Most steps are free. A paid step uses the cheapest option available.” No new onboarding wording was invented.

Implemented screen evidence: [375px](evidence/settings-375.png), [1440px](evidence/settings-1440.png). The existing Trigger menu component is reused with its Workspace title. Its pre-existing navigation and typography differences are outside the settings content. The production content omits the prototype's review-only “Proposed · Illustrative paid-step inventory” banner. The founder label is shown only to founders; the brief also authorizes tenant administrators to use their step switches.

The logo is the existing `workspace/public/trigger/wordmark.png`, byte-identical to the Figma asset (SHA256 `18f375fa245b97c814811e356e9a08b9fe8419f68f8b181b3a32e409ce0dc605`). Screenshots use the repository's Inter and Jost font files; browser assertions check the logo dimensions, title geometry and horizontal overflow. No Figma image URL is shipped.
