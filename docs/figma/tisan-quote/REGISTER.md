# J4 · Tisan client quote request

Status: **Approved 3 Nov 2026, 17:45 PT** (Claude, under the founder's 3 Nov 13:28 delegation) for the eight frames and their wording at this commit, with one change still required before build: the quote-request page is public, so it must not show the Workspace menu. Remove the side menu and the mobile menu bar from all its frames. Design only; no client submission, email, payment, production data, or deployment occurred.

File: [Tervory design](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS). Dedicated page: `513:40527` (J4 · Tisan client quote · Proposed).

## Sources and wording

Engine source: `agents/tisan/quotes.py:51–117` at origin/main. Labels map directly to existing fields: contact.name → Name; contact.email → Email; contact.phone → Phone; contact.company → Company; contact.reply_method → Reply method; items[].type → Type; items[].description → Description; items[].quantity → Quantity; items[].notes → Notes. Display capitalization and replacing the underscore in Reply method are **Proposed**. The prior “Product or service” field label becomes **Description (Proposed)** to match the engine. Product/Service and Email/Phone are existing enum values with display capitalization.

Contact/Items grouping labels, Reply method, Description, and the Proposed review marker are **Proposed** presentation wording. Existing product labels Name/Email originate in `agents/tisan/templates/next-site/app/contact/page.tsx`. Other form, action and feedback wording is reused from the existing Tisan canvas on page `164:12`; its approval is not inferred. All reused canvas copy remains **Proposed** here: “Request a quote”, “Item 1”, “Add another item”, “Send request”, “Privacy”, “Sending request…”, “Sending…”, “Request sent”, “Your quote request has been sent to {shop_name}.”, “Your request could not be sent. Your details are still here. Try again.”, “Try again”. Placeholder strings are synthetic slot names from that canvas, not real identities.

Validation copy is **Proposed**, including reused canvas messages: “Enter your name using 120 characters or fewer.”, “Enter your email address.”, “Enter a phone number so we can reply by phone.”, “Enter a product or service using 240 characters or fewer.”, “Enter a valid email address.”, “Enter a whole quantity of 1 or more.” No acknowledgement email or guaranteed response time is promised.

## Components and behavior

Existing local masters reused: Field `165:9`, Notes `165:14`, Primary action `165:19`, Reply preference `167:2675`, Product/service choice `171:3147`; shared desktop menu `180:8387`, mobile bar `180:8550`. Masters and previous screens remain unchanged. Choice controls are derived from those existing component instances, then detached locally because Figma prevents inherited minimum-size overrides. This keeps the existing radio design while allowing 44px targets and unbroken labels. All other fields/actions/menu stay linked instances. Complete node IDs and instance inventory are in [nodes.json](nodes.json).

White/light surfaces, navy #001840 main buttons/text, Inter throughout. Input borders #848da3 (3.32:1 against white). 8px corners; 16/24px layout spacing. Desktop 1440: shared 240px menu and two form columns. Mobile 375: shared menu bar and one column; long content scrolls vertically. Mobile menu opening uses the shared component contract; no new product menu is invented.

Required: Name, Email, Reply method, at least one item, Type, Description, Quantity. Phone is required only when Reply method is Phone; Company and Notes are optional. Quantity is integer 1–10000; 1–100 items; Name/Company ≤120, Email ≤254, Phone ≤40, Description ≤240, Notes ≤2000, matching the engine. Validation is shown on submission; it preserves entries, focuses the first invalid field and associates inline feedback with its field (**Proposed behavior**). Submission/loading disables duplicate requests. Error retains entries and offers Try again. Submitted replaces the form with confirmation; it represents a successful API response, not an email delivery claim. The prototype is a visual specification, not a running form.

## Screens

| State | Width | Proposed frame | Screenshot |
| --- | --- | --- | --- |
| ready | 1440 | [513:40528](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-40528) | [ready-1440.png](screenshots/ready-1440.png) |
| ready | 375 | [513:40686](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-40686) | [ready-375.png](screenshots/ready-375.png) |
| empty | 1440 | [514:5990](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5990) | [empty-1440.png](screenshots/empty-1440.png) |
| empty | 375 | [514:6148](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-6148) | [empty-375.png](screenshots/empty-375.png) |
| missing | 1440 | [514:18203](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18203) | [missing-1440.png](screenshots/missing-1440.png) |
| missing | 375 | [514:18361](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18361) | [missing-375.png](screenshots/missing-375.png) |
| invalid | 1440 | [514:18586](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18586) | [invalid-1440.png](screenshots/invalid-1440.png) |
| invalid | 375 | [514:18744](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18744) | [invalid-375.png](screenshots/invalid-375.png) |

## Verification

Screenshots exported at native widths; ready desktop/mobile, empty mobile, missing mobile and invalid mobile were visually reviewed. Node audit checks Inter and horizontal text bounds; results are recorded per frame in nodes.json. No executable app code changed; build tests are not applicable. All frames await founder approval.

## Blocked remaining states

The Figma MCP returned its Full-seat Professional-plan call-limit error on the first loading-screen construction attempt. That call committed no frame. **Loading, submitted and error desktop/mobile frames are unfinished and have no IDs or screenshots.** No fabricated IDs or completion claim is recorded. Resume these six frames when Figma tool access is available. The existing source references for these states are sending 166:873 / 166:2869, submitted 166:934 / 166:2930, error 166:946 / 166:2942. These are source frames, not new deliverables.

Pushed screen commits: ready d29002e1; empty fc789bac; missing 44328dde; invalid 070955cd. Full per-node inventory is in nodes.json, including locally detached choice controls. No pre-existing frame or master was changed.
