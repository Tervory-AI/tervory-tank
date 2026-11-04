# CLI-1: the Tervory CLI, the same window in a terminal

> Written 20 Oct 2026. Founder: the product works like Cursor: the window (COMMAND-1) in the browser, **and a CLI**, both linked to every available model. The CLI is a client of the same Tank `/v1/command/*` contract as the window (COMMAND-1 Lane A): same threads, tools, confirm cards and receipts. Code against the contract with a fake Tank until Lane A lands.

**Files you may change:**
- new `cli/` (the package);
- `tank/` (personal access tokens only: new module, route registration in main.py, additive schema);
- `workspace/app/cli/` (CLI sign-ins page; approval is hosted by Trigger sign-in);
- `.env.example` (names only);
- tests.

1. **Package:** `cli/` (`"private": true`, never published to npm or any third-party registry), distributed only from Tervory's own Workspace at `https://app.tervory.com/cli/` (install.sh, latest.json, versioned per-platform tarballs with a SHA-256 manifest; `tervory update`). Node 22, a single `tervory` command. Version pinned, with a changelog.
2. **Sign-in:** Trigger sign-in.
   - Native device approval (`tervory login`) in both regions, not pasted tokens or a Workspace approval page. Each user sees and revokes their own issuer-scoped sign-ins in the Workspace at `/cli/sign-ins`.
   - Stored hashed in Tank, scoped to one user, one tenant and one region box.
   - `tervory login` saves the token in the OS keychain, never in plain files or logs.
   - Founders see every tool; clients see only their own squad tools, enforced by Tank.
3. **Commands:**
   - `tervory chat [thread]`: an interactive thread. The answer streams, step lines show as they change, and confirm cards are a y/N prompt.
   - `tervory ask "<question>"`: one-shot.
   - `tervory threads`: list threads, with spent and saved for each.
   - `tervory run <agent> <task> [--file]`: start squad work (for example `tervory run base batch --file delaware.csv`).
   - `tervory build "<change>"`: writes the brief, then confirm sends it to the workers.
   - `tervory receipts [thread|task]`: cost, would-have-cost and saved per step (the founder also sees model or "code" and tokens).
4. **Model choice is founder-only, the same in the CLI and the window (review of #506, B2):**
   - Everyone answers with Auto: Tank picks the cheapest proven step.
   - Founder only, not in help or the README: `tervory models` (the roster, formatted, never raw JSON) and `--model <name>` (pins a roster model for that turn, still through Tank; the receipt also shows what Auto would have cost).
   - Tank answers `/v1/command/models` with 404 and a non-Auto pin with 403 ("Only Auto is available on this account", no model named) for everyone else. The app.tervory.com CLI corridor does not forward `models` at all. Receipts, steps, messages and streams carry model names, requested models and price-book rows to the founder only (customer views are allowlists).
5. **Region:** the token's box decides where it talks: app.tervory.com or za.tervory.com. It never mixes the two.

## Trigger sign-in device flow — supersedes Workspace approval

The CLI starts the region's native device flow through Tank. Only that region's
Trigger sign-in host approves the code: `auth.tervory.com` in the US and
`auth-za.tervory.com` in ZA. Tank verifies the native token's signature, issuer,
audience, expiry, subject and Tervory-project grants before issuing its existing
hashed CLI credential. The subject is unchanged; an organisation maps only to
its setup-published existing Tank tenant. Email, names and metadata grant nothing.

There is no Workspace approval page or service-key approval fallback. The narrow
`TRIGGER_SIGNIN_SESSIONS_KEY` permits only verified own-session list/revoke on ZA;
it cannot approve a code or mint a credential. Independent regional subjects are
not linked by matching email. See [Trigger sign-in deployment](../ops/TRIGGER-SIGNIN.md).

**What phishing gets an attacker, and why revoke matters.** An attacker can start
`tervory login` on their own machine and send the code or approval link to a victim. If the
victim approves, the attacker's machine holds a credential with **the victim's access** in the
victim's organization and region (the CLI corridor only: chat, threads, receipts, build and
confirm cards; a CLI token reaches no other route). Binding the code to a tenant would not
stop this: the attacker would just create it for the victim's tenant. So the defences are:
- approval is rendered only by the native Trigger sign-in device screens; never
  approve a code you did not just request in your own CLI;
- native codes expire, are single-use, and enforce the server's polling interval;
- the access token lasts 1 hour and the refresh token 30 days, rotating on every use;
- **revoke**: the Workspace page **CLI sign-ins** (`/cli/sign-ins`) lists every active sign-in
  (device name, region, signed in, last used) with Revoke, which ends the access and refresh
  tokens at once; `tervory logout` revokes from the CLI side. Revocation is what ends a
  phished sign-in. A separately issued ZA-native credential can always be revoked
  by `tervory logout` in that CLI.

Revisit if Tank gains per-tenant region residency rules (then refuse approval on a box
outside the tenant's allowed regions) or if a code ever needs to carry a tenant hint.

## Done when
CI green. Tests against a fake Tank:
- login stores the token in the keychain and never prints it;
- chat streams tokens, steps and receipts;
- a confirm card does nothing on "N";
- a client token cannot see founder tools;
- a pinned model shows the Auto comparison;
- a revoked token is refused.

Include a terminal recording (asciinema or GIF) of a chat with a receipt in the PR.
