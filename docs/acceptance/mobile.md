# Mobile — founder testing sheet

Scope: gate 1 is the installable web app in `workspace/`. Gate 2 (Capacitor iOS
and Android) belongs to a separate branch. Gate 3 is this acceptance sheet.
No store app is claimed built, merged, signed or tested by this branch.

Use `https://app.tervory.com` after the reviewed branch is merged and deployed.
Use two founder-controlled test organizations with distinct harmless records.
No additional founder-filled environment settings are introduced by gate 1;
the existing Workspace Trigger sign-in/Tank deployment settings remain prerequisites.
Never record passwords, tokens or client data in evidence.

For every row record: date, deployed commit, device model, OS/browser version,
pass/fail/blocked, and a redacted screenshot or observed result. Record web app
and native build versions separately. A blank result is **not run**, not passed.

| ID | Surface / action | Expected result | Current evidence / result |
| --- | --- | --- | --- |
| M01 | Android Chrome: open the URL, sign in, use the browser Install action, then launch its home-screen icon. | Tervory name and existing logo on navy; standalone window opens `/chats` and the existing signed-in app. | Automated manifest and PNG checks pass; physical-device installation not run. |
| M02 | iPhone Safari: Share → Add to Home Screen; launch the new icon. | Tervory name/icon, standalone window; sign-in remains usable if Safari's existing session is not shared. | Apple metadata and 180px icon present; physical-device installation not run. |
| M03 | From the installed app, sign out, sign in and relaunch; cancel sign-in once before retrying. | Existing Trigger sign-in flow completes; cancellation does not expose private pages; session expiry returns to sign-in. | Device check not run. |
| M04 | At 375px and 390px portrait, then landscape: open Menu, a chat, Work and a receipt; type with keyboard open. | No sideways scrolling or hidden primary controls; menu opens/closes; input and send stay reachable; receipts remain readable. | Device check not run. |
| M05 | Send one harmless request, follow progress, leave the app and return, then reopen the chat. | The existing server-backed answer, work steps and cost receipt remain consistent; relaunch does not duplicate the request. | Authenticated device check not run. |
| M06 | With browser developer tools inspect Cache Storage after chat/API/file use. Go offline and revisit a private URL; reconnect. | Only manifest, icons and public `_next/static` JS/CSS/fonts are cached by this worker. No HTML, API/JSON, documents or client data; offline navigation may show the browser connection error. Reconnect restores normal use. | Worker policy tests pass; browser/device check not run. |
| M07 | Sign out of test organization A, sign into B and open A's copied chat/file URL. Inspect Cache Storage again. | Server authorization refuses A's private data. No cached client response supplies it. | Worker exclusion checks pass; authenticated tenant check not run. |
| M08 | Leave installed app open during a later web deployment; close all app windows and reopen online. | New worker activates with the normal browser lifecycle; old `tervory-shell-*` caches are removed. New application assets load; private data is still network-only. | Browser update check not run. |
| M09 | Signed out: fetch `/manifest.webmanifest`, `/sw.js` and all three `/icons/tervory-*.png` URLs on deployed app origin. | HTTP 200 with correct manifest/JS/PNG content, no Trigger sign-in redirect; worker has no-cache/no-store and root scope headers. | Source routes/headers present; deployed check not run. |

## Store apps — run only after the gate 2 branch merges

First record the gate 2 PR, merge SHA, deployed Workspace SHA, iOS build number,
Android version code and install source. These rows remain **blocked: awaiting
gate 2 merge and installable builds**. Obtain the exact install links, supported
OS versions and native configuration names from that branch's delivery notes;
do not substitute an unmerged build or invent settings. Run M03–M07 separately
on both native apps as well as the web app.

| ID | Surface / action | Expected result | Result |
| --- | --- | --- | --- |
| S01 | Install the supplied iOS test/store build and Android test/store build on supported physical devices; cold launch each. | Correct Tervory identity, install succeeds, app opens the deployed Workspace; no blank screen or redirect loop. | Blocked: gate 2 dependency. |
| S02 | Start sign-in from each app; inspect the system browser; complete return to app. Repeat with cancellation, expired authorization and a logged-out browser. | Gate 2's documented identity flow completes securely; cancellation/expiry can retry. A Trigger sign-in token alone must not be treated as a Trigger sign-in session or imply a tenant mapping. | Blocked: gate 2 dependency. |
| S03 | Open the gate 2 documented return/deep link with app closed and open; try an unrelated or malformed return URL. | Only the documented app link is handled; no token appears in UI/log evidence; invalid returns do not grant a session or expose data. | Blocked: gate 2 dependency. |
| S04 | In each native app: open a chat, send a harmless request, background/foreground, rotate, use Android Back/iOS navigation, then force-close and relaunch. | Keyboard/navigation remain usable; correct chat and server state reload; no duplicate request or cross-tenant state. | Blocked: gate 2 dependency. |
| S05 | In each native app: lose connectivity mid-request, reconnect, sign out, then switch test organization. | Clear recoverable connection/auth state; no silent duplicate sends; no private response from the previous organization shown to the next user. | Blocked: gate 2 dependency. |
| S06 | Update each installed native app using the supplied distribution channel; rerun sign-in and one chat request. | Upgrade succeeds with correct build identity; supported session behavior follows delivery notes; core flow still works. | Blocked: gate 2 dependency. |

Gate 1 code checks do not close physical-device acceptance. Gate 3 store coverage
closes only when the dependency details and actual results above are recorded.
