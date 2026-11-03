# Marketing · current specification · 3 November

All changes listed here are **Changed after approval, awaiting founder**. Unchanged frames retain **Approved 3 Nov**. This document replaces the prior Marketing SPEC in full; historical proposals, raw binding paths and contradictory mobile Channels rules are removed.

## Layout and navigation

One 240px Trigger menu. Desktop 1440×900: 1200px work area, 1136px usable content. Mobile 375×812: one 240px drawer, a clipped vertical area above a pinned account block, a full-width divider and enough scroll clearance for its last item. Account settings is distinct from the one Settings item in Chat bot. Writing uses Write and Voice. Marketing areas are Channels, Calendar, Composer, Google posts, Google reviews and Post detail. Each page highlights its own area. Titles use the same names. All voice fields say Saved voice.

## Current flows

- Channels: one 64px row per channel on desktop. At 375, one 120px two-line connection card per channel; there is no horizontal Channels table. Name, account and status allow two lines. Connected → Disconnect → Confirm · Disconnect; Needs reconnecting → Reconnect → Confirm · Connect; Off → Connect → Confirm · Connect. Zero Connect never opens Disconnect. Filled is a state specimen, with no claim of live account status.
- Filled calendars: equal seven-column cells with day numbers and one placeholder post card showing channel, status and time. It opens Post detail `149:8745`. Day numerals describe the calendar geometry; the period and all post content remain placeholders, not a scheduled client post.
- Google posts is reachable from the menu. Header and row widths match. Desktop rows and mobile cards open Post detail. Post detail and Google posts have their own active navigation item.
- Google reviews: Zero shows No reviews yet.; Filled shows a review summary linked to Review detail. Detail order is Review, Draft reply, Checker findings, Send reply. Sending retains the founder confirmation step and returns to that detail.
- Composer order: Post, checker findings, Approve; then Schedule with Date, Time and Time zone. All channel previews and channel-specific limits remain. Schedule is disabled and has no action until approval. Approve → Confirm · Approve → the explicit Approved Composer specimen; only there is Schedule enabled and linked to Confirm · Schedule. On mobile the active action stays in a sticky footer with matching content clearance.
- Confirmations identify a Post title rather than a post ID. Bracketed values are plain-word annotations, never live records. Confirm/Cancel are prototype navigation only.

## Shared components

Action family `266:3038`: Primary `266:3032`, Secondary `266:3034`, Destructive `266:3036`; centred labels. Confirm and positive commit actions use Primary. Disconnect and Delete use Destructive. New scoped menu family `266:3212` uses the existing approved Tervory logo, Trigger accent, fields and typography; it does not modify the CRM/MCP source components. Native SPEC `151:3973` and visible frame `210:2897` contain this same current document.

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


## Authoring verification · 3 November

Menu destinations were checked on both pages, including both mobile drawers and the new Google posts and Post detail entries. Same-page destinations navigate in the prototype; cross-page entries link to the corresponding Figma frame. Schedule confirmation returns to the approved Composer. Mobile Channels use 120px cards with 44px actions and two-line names. Drawer scroll content ends with 16px clearance above the 240px-wide pinned block when scrolled to the end.

Commands run in `/workspace/codex-crm-marketing-chat-design`: `git fetch origin` (passed); `git diff --check` (passed); `git status --short` (only these two SPEC documents); `git push origin codex/crm-marketing-chat-design` (passed after each documentation commit). Figma checks inspected frame bounds, field sets, prototype destinations and mirrored SPEC text. Authoring screenshots covered Channels 375, Google posts 1440, calendar 1440, review detail 1440, approved Composer 375, lead form 375, Answer and Sending. These are authoring checks, not screenshots of a founder acceptance test. Founder browser acceptance remains outstanding.

Shared changed controls: action family `266:3038` (primary `266:3032`, secondary `266:3034`, destructive `266:3036`); navigation family `266:3212` (desktop `266:3039`, mobile `266:3125`). Component variant words Primary, Secondary and Destructive are design metadata. The complete changed screen node register is above; original root IDs are retained. Approval captions are outside product screens.
