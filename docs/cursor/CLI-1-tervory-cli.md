# CLI-1: the Tervory CLI, the same window in a terminal

> Written 20 Oct 2026. Founder: the product works like Cursor: the window (COMMAND-1) in the browser, **and a CLI**, both linked to every available model. The CLI is a client of the same Tank `/v1/command/*` contract as the window (COMMAND-1 Lane A): same threads, tools, confirm cards and receipts. Code against the contract with a fake Tank until Lane A lands.

**Files you may change:**
- new `cli/` (the package);
- `tank/` (personal access tokens only: new module, route registration in main.py, additive schema);
- `workspace/app/settings/` (token page only);
- `.env.example` (names only);
- tests.

1. **Package:** `cli/` (`"private": true`, never published to npm or any third-party registry), distributed only from Tervory's own Workspace at `https://app.tervory.com/cli/` (install.sh, latest.json, versioned per-platform tarballs with a SHA-256 manifest; `tervory update`). Node 22, a single `tervory` command. Version pinned, with a changelog.
2. **Sign-in:** personal access tokens.
   - Created and revoked in the Workspace under Settings > Access tokens.
   - Stored hashed in Tank, scoped to one user, one tenant and one region box.
   - `tervory login` saves the token in the OS keychain, never in plain files or logs.
   - Founders see every tool; clients see only their own squad tools, enforced by Tank.
3. **Commands:**
   - `tervory chat [thread]`: an interactive thread. The answer streams, step lines show as they change, and confirm cards are a y/N prompt.
   - `tervory ask "<question>"`: one-shot.
   - `tervory threads`: list threads, with spent and saved for each.
   - `tervory run <agent> <task> [--file]`: start squad work (for example `tervory run base batch --file delaware.csv`).
   - `tervory build "<change>"`: writes the brief, then confirm sends it to the workers.
   - `tervory receipts [thread|task]`: model or "code", tokens, cost, baseline and saved per step.
   - `tervory models`: the roster with prices.
4. **Model choice, the same in the CLI and the window:**
   - `--model auto` (the default): Tank picks the cheapest proven step.
   - `--model <name>`: pins any roster model for that turn. It still goes through Tank, and the receipt also shows what Auto would have cost.
5. **Region:** the token's box decides where it talks: app.tervory.com or za.tervory.com. It never mixes the two.

## Done when
CI green. Tests against a fake Tank:
- login stores the token in the keychain and never prints it;
- chat streams tokens, steps and receipts;
- a confirm card does nothing on "N";
- a client token cannot see founder tools;
- a pinned model shows the Auto comparison;
- a revoked token is refused.

Include a terminal recording (asciinema or GIF) of a chat with a receipt in the PR.
