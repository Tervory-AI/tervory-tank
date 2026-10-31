# CLI-1: the Tervory CLI, the same window in a terminal

> Written 20 Oct 2026. Founder: the product works like Cursor: the window (COMMAND-1) in the browser, **and a CLI**, both linked to every available model. The CLI is a client of the same Tank `/v1/command/*` contract as the window (COMMAND-1 Lane A): same threads, tools, confirm cards and receipts. Code against the contract with a fake Tank until Lane A lands.

**Files you may change:**
- new `cli/` (the package);
- `tank/` (personal access tokens only: new module, route registration in main.py, additive schema);
- `workspace/app/cli/` (device approval and CLI sign-ins pages);
- `.env.example` (names only);
- tests.

1. **Package:** `cli/` (`"private": true`, never published to npm or any third-party registry), distributed only from Tervory's own Workspace at `https://app.tervory.com/cli/` (install.sh, latest.json, versioned per-platform tarballs with a SHA-256 manifest; `tervory update`). Node 22, a single `tervory` command. Version pinned, with a changelog.
2. **Sign-in:** personal access tokens.
   - Now device approval (`tervory login`), not pasted tokens. Each user sees and revokes their own sign-ins in the Workspace at `/cli/sign-ins` (review of #506, B3).
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

## Decision: ZA device codes are not bound to a tenant (review item 5, 31 Oct)
Any signed-in organization can approve a ZA code into its own tenant on the ZA Tank.
This is deliberate, not an omission:
- The CLI has no identity when it asks for a code (RFC 8628 §3.1); the tenant comes from
  the person who approves. There is nothing trustworthy to bind the code to at creation.
- Binding a code to a tenant chosen at creation does not stop the phishing case the review
  raised: an attacker who sends someone an approval link would simply create the code for
  that person's tenant. The token is minted for the approving user in the approving
  tenant, so an approval never grants access to anyone else's tenant.
- Binding codes to a home region would close Chat to customers outside their home region,
  and Tervory Chat must be open to all regions.
Mitigations in place: codes are single use and expire in 10 minutes; the approval page
(`workspace/app/cli/device/page.tsx`) shows the code, organization, device name and
region and says to approve only a code the user's own terminal shows; ZA approvals use
only the dedicated `TANK_DEVICE_APPROVAL_KEY` (two routes, user and tenant still
required); `tervory logout` revokes the credential, and the Workspace **CLI sign-ins** page (`/cli/sign-ins`) lists every active sign-in with Revoke.
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
