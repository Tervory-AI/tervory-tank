# Marketing · current specification · 3 November

All changes listed here are **Changed after approval, awaiting founder**. Unchanged frames retain **Approved 3 Nov**. This document replaces the prior Marketing SPEC in full; historical proposals, raw binding paths and contradictory mobile Channels rules are removed.

## Layout and navigation

One 240px Trigger menu. Desktop 1440×900: 1200px work area with 24px Content padding; existing 1136px content blocks fit within its 1152px inner width. Mobile 375×812: one 240px drawer, a clipped vertical area above a pinned account block, a full-width divider and enough scroll clearance for its last item. Account settings is distinct from the one Settings item in Chat bot. Writing uses Write and Voice. Marketing menu entries are Channels, Calendar, Composer, Google posts and Google reviews. Post detail highlights Calendar and has no menu entry. Approve and Schedule confirms highlight Composer; review-reply confirms highlight Google reviews. Mobile menu buttons open a drawer for the current parent area. Titles use the same names. All voice fields say Saved voice.

## Current flows

- Channels: one 64px row per channel on desktop. At 375, one 120px two-line connection card per channel; there is no horizontal Channels table. Name, account and status allow two lines. Connected → Disconnect → Confirm · Disconnect; Needs reconnecting → Reconnect → Confirm · Connect; Off → Connect → Confirm · Connect. Zero Connect never opens Disconnect. Filled is a state specimen, with no claim of live account status.
- Filled calendars: equal seven-column cells with day numbers and one placeholder post card showing channel, status and time. Desktop cards open Post detail `149:8745`; mobile cards `270:3669` and `270:3701` open mobile Post detail `149:9366`. Day numerals describe the calendar geometry; the period and all post content remain placeholders, not a scheduled client post.
- Google posts is reachable from the menu. Header and row widths match. Desktop rows and mobile cards open Post detail. Google posts highlights Google posts. Post detail highlights Calendar; the Post detail menu entry is removed.
- Google reviews: Zero shows No reviews yet.; Filled shows a review summary linked to Review detail. Detail order is Review, Draft reply, Checker findings, Send reply. Duplicate section headings are hidden with all IDs and field labels retained. Sending retains the founder confirmation step and returns to that detail.
- Composer order: Post, checker findings, Approve; then Schedule with Date, Time and Time zone. All channel previews and channel-specific limits remain. Schedule is disabled and has no action until approval. Approve → Confirm · Approve → the explicit Approved Composer specimen; only there is Schedule enabled and linked to Confirm · Schedule. On mobile the active action stays in a sticky footer with matching content clearance.
- Confirmations identify a Post title rather than a post ID. Bracketed values are plain-word annotations, never live records. Fields come first in the scroll area; Cancel then Confirm occupy an 80px pinned footer (desktop y=820; mobile y=732). Confirm/Cancel are prototype navigation only.

## Shared components

Action family `266:3038`: Primary `266:3032`, Secondary `266:3034`, Destructive `266:3036`; centred labels. Confirm and positive commit actions use Primary. Disconnect uses Secondary with a navy outline and navy text. Destructive red is reserved for Delete. All Marketing and Chat bot navigation uses the canonical white CRM menu family `180:8549`, the same source as `182:9119`. Original Top states remain `180:8387` (desktop) and `180:8467` (mobile). Scrolled Active group states `483:39615` (desktop) and `483:39698` (mobile) show Marketing and Chat bot immediately; every highlighted item is visible without scrolling. Entries and their canonical order are retained. Google posts is added to both source variants. Scoped menu `266:3212` is hidden and marked Retired with IDs retained. Primary `266:3032`, Confirm, Approve, Schedule and Send reply bind to navy color/text `42:14`; Trigger wordmarks are navy. Inputs use color/input-border (#848da3), menu rows are at least 44px high, padding follows 0/8/16/24, and compact card `149:10806` uses radius/8. Under the founder ruling of 3 Nov 11:37 PT, all surfaces here use the light CRM style; dark backgrounds are reserved for homepages. Navy actions and text remain. Native SPEC `151:3973` and visible frame `210:2897` contain this same current document.

## Screen and field register

- `149:2263` · channels|Desktop|Zero · Changed after approval, awaiting founder · Fields: Account; Status.
- `149:2696` · channels|Desktop|Filled · Changed after approval, awaiting founder · Fields: Account; Status.
- `149:3129` · channels|Mobile|Zero · Changed after approval, awaiting founder · Fields: Account; Status.
- `149:3459` · channels|Mobile|Filled · Changed after approval, awaiting founder · Fields: Account; Status.
- `149:3789` · calendar-month|Desktop|Zero · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:4224` · calendar-month|Desktop|Filled · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:4663` · calendar-month|Mobile|Zero · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:4995` · calendar-month|Mobile|Filled · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:5331` · calendar-week|Desktop|Zero · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:5710` · calendar-week|Desktop|Filled · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:6093` · calendar-week|Mobile|Zero · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:6369` · calendar-week|Mobile|Filled · Changed after approval, awaiting founder · Fields: Period; Time zone.
- `149:6649` · composer|Desktop|Zero · Changed after approval, awaiting founder · Fields: Brief; Saved voice; Draft text; Media; Channels; Findings; Checker status; Rule; Location; Date; Time zone; Time; Preview; Length limit; Counted as; Length used.
- `149:7134` · composer|Desktop|Filled · Changed after approval, awaiting founder · Fields: Brief; Saved voice; Draft text; Media; Channels; Post title; Findings; Checker status; Rule; Location; Date; Time zone; Time; Preview; Length limit; Counted as; Length used.
- `149:7619` · composer|Mobile|Zero · Changed after approval, awaiting founder · Fields: Brief; Saved voice; Draft text; Media; Channels; Findings; Checker status; Rule; Location; Date; Time zone; Time; Preview; Length limit; Counted as; Length used.
- `149:8001` · composer|Mobile|Filled · Changed after approval, awaiting founder · Fields: Brief; Saved voice; Draft text; Media; Channels; Post title; Findings; Checker status; Rule; Location; Date; Time zone; Time; Preview; Length limit; Counted as; Length used.
- `149:8383` · post-detail|Desktop|Zero · Changed after approval, awaiting founder · Fields: Channel; Status; Text; Media; Status history; Reported at; Reach; Clicks; Comments; Post title.
- `149:8745` · post-detail|Desktop|Filled · Changed after approval, awaiting founder · Fields: Channel; Status; Text; Media; Status history; Reported at; Reach; Clicks; Comments; Post title.
- `149:9107` · post-detail|Mobile|Zero · Changed after approval, awaiting founder · Fields: Channel; Status; Text; Media; Status history; Reported at; Reach; Clicks; Comments; Post title.
- `149:9366` · post-detail|Mobile|Filled · Changed after approval, awaiting founder · Fields: Channel; Status; Text; Media; Status history; Reported at; Reach; Clicks; Comments; Post title.
- `149:9625` · google-posts|Desktop|Zero · Changed after approval, awaiting founder · Fields: Profile; Post title; Status; Published at.
- `149:9975` · google-posts|Desktop|Filled · Changed after approval, awaiting founder · Fields: Profile; Post title; Status; Published at.
- `149:10325` · google-posts|Mobile|Zero · Changed after approval, awaiting founder · Fields: Post title; Profile; Published at; Status.
- `149:10572` · google-posts|Mobile|Filled · Changed after approval, awaiting founder · Fields: Post title; Profile; Published at; Status.
- `149:10819` · google-reviews|Desktop|Zero · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Checker findings; Reply status.
- `149:11184` · google-reviews|Desktop|Filled · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Checker findings; Reply status.
- `149:11549` · google-reviews|Mobile|Zero · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Checker findings; Reply status.
- `149:11811` · google-reviews|Mobile|Filled · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Checker findings; Reply status.
- `149:21139` · confirm-approve|Desktop|Zero · Changed after approval, awaiting founder · Fields: Post title; Text; Channels; Saved voice; Checker findings.
- `149:21481` · confirm-approve|Desktop|Filled · Changed after approval, awaiting founder · Fields: Post title; Text; Channels; Saved voice; Checker findings.
- `149:21823` · confirm-approve|Mobile|Zero · Changed after approval, awaiting founder · Fields: Post title; Text; Channels; Saved voice; Checker findings.
- `149:22062` · confirm-approve|Mobile|Filled · Changed after approval, awaiting founder · Fields: Post title; Text; Channels; Saved voice; Checker findings.
- `149:22301` · confirm-schedule|Desktop|Zero · Changed after approval, awaiting founder · Fields: Post title; Approved revision; Channels; Date; Time zone; Time.
- `149:22643` · confirm-schedule|Desktop|Filled · Changed after approval, awaiting founder · Fields: Post title; Approved revision; Channels; Date; Time zone; Time.
- `149:22985` · confirm-schedule|Mobile|Zero · Changed after approval, awaiting founder · Fields: Post title; Approved revision; Channels; Date; Time zone; Time.
- `149:23224` · confirm-schedule|Mobile|Filled · Changed after approval, awaiting founder · Fields: Post title; Approved revision; Channels; Date; Time zone; Time.
- `149:23463` · confirm-send-reply|Desktop|Zero · Changed after approval, awaiting founder · Fields: Profile; Review; Reply; Checker findings.
- `149:23802` · confirm-send-reply|Desktop|Filled · Changed after approval, awaiting founder · Fields: Profile; Review; Reply; Checker findings.
- `149:24141` · confirm-send-reply|Mobile|Zero · Changed after approval, awaiting founder · Fields: Profile; Review; Reply; Checker findings.
- `149:24377` · confirm-send-reply|Mobile|Filled · Changed after approval, awaiting founder · Fields: Profile; Review; Reply; Checker findings.
- `149:24613` · confirm-disconnect|Desktop|Zero · Changed after approval, awaiting founder · Fields: Channel; Account.
- `149:24946` · confirm-disconnect|Desktop|Filled · Changed after approval, awaiting founder · Fields: Channel; Account.
- `149:25279` · confirm-disconnect|Mobile|Zero · Changed after approval, awaiting founder · Fields: Channel; Account.
- `149:25509` · confirm-disconnect|Mobile|Filled · Changed after approval, awaiting founder · Fields: Channel; Account.
- `270:3220` · confirm-connect|Desktop|Zero · Changed after approval, awaiting founder · Fields: Channel; Account.
- `270:3369` · confirm-connect|Desktop|Filled · Changed after approval, awaiting founder · Fields: Channel; Account.
- `270:3496` · confirm-connect|Mobile|Zero · Changed after approval, awaiting founder · Fields: Channel; Account.
- `270:3519` · confirm-connect|Mobile|Filled · Changed after approval, awaiting founder · Fields: Channel; Account.
- `270:3789` · review-detail|Desktop|Zero · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Reply status; Checker findings.
- `270:3964` · review-detail|Desktop|Filled · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Reply status; Checker findings.
- `270:4120` · review-detail|Mobile|Zero · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Reply status; Checker findings.
- `270:4169` · review-detail|Mobile|Filled · Changed after approval, awaiting founder · Fields: Profile; Review; Rating; Received at; Reply brief; Draft reply; Saved voice; Reply status; Checker findings.
- `271:3480` · composer-approved|Desktop|Filled · Changed after approval, awaiting founder · Fields: Brief; Saved voice; Draft text; Media; Channels; Post title; Findings; Checker status; Rule; Location; Date; Time zone; Time; Preview; Length limit; Counted as; Length used.
- `271:3780` · composer-approved|Mobile|Filled · Changed after approval, awaiting founder · Fields: Brief; Saved voice; Draft text; Media; Channels; Post title; Findings; Checker status; Rule; Location; Date; Time zone; Time; Preview; Length limit; Counted as; Length used.

## New wording awaiting founder approval

- Changed after approval, awaiting founder
- Approved 3 Nov
- Account settings
- Google posts
- Confirm · Connect
- Reconnect
- Review detail
- No reviews yet.
- Post title; [Post title]
- Date; [Date]
- Time; [Time]
- Approve the post before scheduling.
- Approved

Existing labels, day names, channel names and placeholder field labels are retained. The status/control words Connected, Needs reconnecting, Off, Connect, Disconnect, Schedule and Saved voice were already present; their clarified use above is the changed design, not new live data.

## Build contract and verification

Founder confirms exact post revision, channels, saved voice and checks before approval; scheduling includes the approved revision, date, time and time zone. Changed copy/media/channels invalidate approval. All seven per-channel previews retain length limit, unit and counted length. Missing limits block scheduling. Platform results display only returned reach, clicks and comments, never invented zeroes.

Open-source social scheduler is a founder engine decision; Postiz remains a candidate, not an installed or selected engine. Existing Trigger drafting and code checks are reused. No model API call, live connection, credential, app implementation or deployment is part of this design change. Authoring checks and screenshots are evidence of the proposal; the founder's visual acceptance is still required.


## Correction verification · 3 November

Original screen and navigation instance root IDs are retained. Swapped instance descendants follow the canonical CRM source IDs. Extra mobile drawer specimens preserve the same menu entries while highlighting Calendar, Composer, Google posts or Google reviews. The account block remains pinned below scrolling navigation with 16px bottom clearance. Offscreen menu rows remain reachable by scrolling.

Checks cover light surfaces, navy positive actions, 20 confirm footers, active menu items, input contrast, 44px rows, mobile calendar destinations and 8px compact-card corners. Screenshots and the complete directly edited/created node list are in the [correction register](evidence/2026-11-03-corrections/REGISTER.md) and [machine-readable changes](evidence/2026-11-03-corrections/changes.json). These are design-authoring checks; changed screens remain Changed after approval, awaiting founder. No production code, deployment, credentials or main-branch changes are included.

## Follow-up geometry and menu review · 3 November

The seven-point follow-up is implemented under the founder instruction to decide and continue. All screen and navigation instance root IDs remain. The single CRM menu family now has Top and Active group scrolled states. Both active groups and all 63 highlighted entries across Marketing/Chat bot desktop screens and mobile drawers fit their visible navigation areas; pinned identity/account blocks remain. These are authored scrolled view states, retaining the canonical group order and all entries. Swapping component states changes inherited child IDs, recorded separately from preserved roots.

Composer containers 149:6983, 149:7468 and 271:3485 stay 560px wide. Post and Trigger checks fill that width; their inner fields stack within 528px, eliminating horizontal clipping. Compact cards 149:10806 and 149:14873 hug their two field rows, use 8px gaps and 16px padding, and grow to 88px high. Post cards 270:3669 / 270:3701 use 8px corners and padding and hug to 88px high.

Every Content/* padding value of 40/32 is now 24; mobile Composer bottom padding is 24, with the existing pinned footer occupying its separate viewport area. List column-heading padding of 12 becomes 8. Calendar cell gaps are 8. All ten Disconnect instances use Secondary 266:3034 with navy outlines/text, retaining their root IDs and prototype destinations. Red remains for Delete.

No product words were added. Stale layer names are aligned with Quote draft, Settings, Confirm · Settings and Confirm · Hand-over. Exact IDs, before/after layer names, geometry assertions and screenshots: [follow-up register](evidence/2026-11-03-followup/REGISTER.md). Changed designs remain Changed after approval, awaiting founder. No production changes or deployment.

## Shared mobile Close target · follow-up item 8

Close menu × retains node 180:8471 in Top mobile source 180:8467 and node 483:39702 in scrolled mobile source 483:39698. Both clickable text boxes are fixed 44×44 with the glyph centred and their existing Close prototype action retained. The header row grows to 44px, and the approved logo scales proportionally to 156px wide to fit the 208px row. The scrolled state adjusts its groups by 8px to preserve 16px bottom clearance and active-item visibility. All 44 current mobile menu instances inherit a 44×44 Close target; no instance failed the check. No new nodes or product words. [Exact changed nodes, inherited-instance checks and screenshot](evidence/2026-11-03-followup/close-target.json); [screenshot](evidence/2026-11-03-followup/close-target-375.png). Changed after approval, awaiting founder.
