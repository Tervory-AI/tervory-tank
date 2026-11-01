# Tisan quote — SPEC — DRAFT, founder approval required

Figma file: ZnphBOJU6657tohGLD3IzS. Page: **3 · Tisan quote**, ID **164:12**.
Approval is pending for every new screen, interaction, limit and wording below.
This is design only. No live pages, engine code, payment flow or email sending changed.
Homepage approval is separate and does not approve these quote designs.

## Authority and sources

- Founder brief: draft → submitted → acknowledged → quoted → accepted | declined.
- Founder clarification: use standard Tervory colours and fonts everywhere.
- agents/tisan/README.md: scaffold, branding and Playwright widths.
- agents/tisan/scaffold.py: brief name, pages, four colours, two fonts and logo.
- agents/tisan/templates/next-site/app/layout.tsx: header, wrapping navigation, main and footer.
- agents/tisan/templates/next-site/app/contact/page.tsx: stacked labels, 48px fields, max-w-md and contact-style primary action.
- agents/tisan/templates/next-site/app/privacy/page.tsx: existing /privacy page.
- Figma 42:2: case-study table header 43:389, row 43:405, canonical client menu 125:10372 and mobile menu 125:10373. Existing source components are unchanged.
- No Code Connect files were found; library search returned no Tisan quote or Tervory field assets. New field and action masters are local draft components, not replacements for existing library assets.

## Approval and implementation gate

The customer's request is approval to request a quote. No extra payment approval,
card, bank or other financial fields appear on /quote. Store quote amount and
currency are the explicitly requested quote fields, not a payment collection flow.
No financial integration is added. All data values in braces are design bindings,
not actual requests or customer data. No sample/fixture data is put on a live screen.
Nothing may be built from these drafts until the founder approves exact frames and wording.
Keep QUOTE-EMAILS-DRAFT.md; the approved QUOTE-EMAILS.md is intentionally absent.

## Tokens and accessibility

Collection: Tisan quote / Standard brand, VariableCollectionId:164:13.
- ink VariableID:164:14 aliases the case-study navy text token (#001840).
- paper VariableID:164:15 aliases the case-study canvas token (#F4F6FB).
- line VariableID:164:16 aliases the case-study border token (#B8BFD0).
- accent VariableID:164:17 is the standard red (#E80008).
- heading VariableID:164:18 = Jost; body VariableID:164:19 = Inter.
Named variables are used, rather than one customer's brand. The founder's standard-colour
clarification supersedes the original arbitrary-colour requirement.
Ink/paper = 16.12:1. Accent/paper = 4.38:1. Red filled buttons therefore use
Inter Bold 20px (large text, 3:1 requirement). Error explanations stay ink;
red input outlines are a non-text indicator. Input boundaries use ink, not
the low-contrast decorative line token. Errors always include text, never colour alone.
Headings are Jost Light. All other text uses Inter. Customer form max width 448px.
Input height 48px; notes 84px. Preserve keyboard order, label associations,
required/optional semantics, error descriptions and focus visibility in any later implementation.
This spec does not certify WCAG for a different customer palette.

## Field register and engine state mapping — all validation rules are draft

| Field | Type / rule | State / storage meaning |
| --- | --- | --- |
| name | Required text; 1–120 characters | editable in draft; request snapshot after submitted |
| email | Required valid email; at most 254 characters | draft → submitted; customer delivery address |
| phone | Optional; valid phone when supplied; required if reply method is phone; at most 40 characters | draft → submitted |
| company | Optional; at most 120 characters | draft → submitted |
| items | One or more items; no last-item removal without showing missing-item error | draft → submitted |
| items[].type | Required product or service | draft → submitted |
| items[].description | Required; at most 240 characters | draft → submitted |
| items[].quantity | Required whole number ≥ 1; initial 1 | draft → submitted |
| items[].notes | Optional; at most 2,000 characters | draft → submitted |
| reply_method | Required email or phone; explicit radio selection | draft → submitted |
| privacy link | Existing /privacy route; no new privacy wording or checkbox | all customer views |
| request_id | Read-only engine identifier | submitted and later |
| state | Read-only lifecycle status | draft/submitted/acknowledged/quoted/accepted/declined |
| history[].state / history[].at | Every reached state plus timezone-qualified time | append for each committed state transition |
| quote_amount | Required positive decimal; format for selected currency; no payment details | editable while composing from acknowledged; snapshot when quoted |
| quote_currency | Required supported currency code | acknowledged → quoted |
| valid_until | Required future date with shop timezone resolved | acknowledged → quoted |
| quote_message | Required message; at most 2,000 characters | acknowledged → quoted |
| customer decision | Store records actual acceptance or decline | quoted → accepted OR quoted → declined |
| email subject / text / HTML | Exact E1–E7 wording, escaped bindings | submitted, quoted, accepted, declined |

## Customer states and behaviour

A EMPTY and FILLED are draft. All A ERROR states remain draft and preserve the
other fields. FILLED shows two items and Remove item; all editable screens show
Add another item. Empty selection for Type is a product/service choice.
Reply uses explicit Email/Phone radio controls. Phone is optional except when
phone reply is selected. Missing-item screens have no item rows.
SENDING preserves values, disables re-entry and duplicate submission, and is
pending submission rather than a separate engine state. SENT means submitted.
FAILED means no confirmed submission; retain values and allow retry.
No new success redirect, live backend, sign-in or payment interaction is designed.
Customer navigation and /privacy retain template routes. Optional logo is omitted
when absent; no made-up logo or account name is shown.

## Store states and transitions

Workspace route: /tisan. List Zero, list Filled and detail Zero are separate.
Detail frames cover each engine state, the submitted request and the reached
history with time bindings. No privileged action is available for draft.
Submitted exposes Acknowledge; acknowledged exposes Send a quote.
Quoted exposes Mark accepted and Mark declined. Accepted/declined are terminal.
Every store change has a separate confirmation frame. Cancel returns unchanged.
Quote composition requires review before confirm/send. Store staff must record
the customer's decision, not fabricate acceptance. Confirmation records both the
new state and timestamp. The store never edits the original submitted request here.
A failed email is distinct from a committed engine change; do not label it delivered.
Mobile Menu opens the canonical case-study mobile menu and returns to the prior screen.
List rows and lifecycle actions are connected for founder review; no engine is invoked.

## Screen register

| Screen | Figma node ID | Width | UI state |
| --- | --- | --- | --- |
| A-EMPTY-390 | 166:9 | 390 | empty |
| A-FILLED-390 | 166:69 | 390 | filled |
| A-ERROR-NAME-390 | 166:152 | 390 | error-name |
| A-ERROR-EMAILREQUIRED-390 | 166:212 | 390 | error-emailRequired |
| A-ERROR-EMAILFORMAT-390 | 166:272 | 390 | error-emailFormat |
| A-ERROR-PHONEREQUIRED-390 | 166:332 | 390 | error-phoneRequired |
| A-ERROR-PHONEFORMAT-390 | 166:392 | 390 | error-phoneFormat |
| A-ERROR-COMPANY-390 | 166:452 | 390 | error-company |
| A-ERROR-TYPE-390 | 166:512 | 390 | error-type |
| A-ERROR-DESCRIPTION-390 | 166:572 | 390 | error-description |
| A-ERROR-QUANTITY-390 | 166:632 | 390 | error-quantity |
| A-ERROR-NOTES-390 | 166:692 | 390 | error-notes |
| A-ERROR-REPLY-390 | 166:752 | 390 | error-reply |
| A-ERROR-ITEMS-390 | 166:812 | 390 | error-items |
| A-SENDING-390 | 166:873 | 390 | sending |
| A-SENT-390 | 166:934 | 390 | sent |
| A-FAILED-390 | 166:946 | 390 | failed |
| A-EMPTY-768 | 166:1007 | 768 | empty |
| A-FILLED-768 | 166:1067 | 768 | filled |
| A-ERROR-NAME-768 | 166:1150 | 768 | error-name |
| A-ERROR-EMAILREQUIRED-768 | 166:1210 | 768 | error-emailRequired |
| A-ERROR-EMAILFORMAT-768 | 166:1270 | 768 | error-emailFormat |
| A-ERROR-PHONEREQUIRED-768 | 166:1330 | 768 | error-phoneRequired |
| A-ERROR-PHONEFORMAT-768 | 166:1390 | 768 | error-phoneFormat |
| A-ERROR-COMPANY-768 | 166:1450 | 768 | error-company |
| A-ERROR-TYPE-768 | 166:1510 | 768 | error-type |
| A-ERROR-DESCRIPTION-768 | 166:1570 | 768 | error-description |
| A-ERROR-QUANTITY-768 | 166:1630 | 768 | error-quantity |
| A-ERROR-NOTES-768 | 166:1690 | 768 | error-notes |
| A-ERROR-REPLY-768 | 166:1750 | 768 | error-reply |
| A-ERROR-ITEMS-768 | 166:1810 | 768 | error-items |
| A-SENDING-768 | 166:1871 | 768 | sending |
| A-SENT-768 | 166:1932 | 768 | sent |
| A-FAILED-768 | 166:1944 | 768 | failed |
| A-EMPTY-1440 | 166:2005 | 1440 | empty |
| A-FILLED-1440 | 166:2065 | 1440 | filled |
| A-ERROR-NAME-1440 | 166:2148 | 1440 | error-name |
| A-ERROR-EMAILREQUIRED-1440 | 166:2208 | 1440 | error-emailRequired |
| A-ERROR-EMAILFORMAT-1440 | 166:2268 | 1440 | error-emailFormat |
| A-ERROR-PHONEREQUIRED-1440 | 166:2328 | 1440 | error-phoneRequired |
| A-ERROR-PHONEFORMAT-1440 | 166:2388 | 1440 | error-phoneFormat |
| A-ERROR-COMPANY-1440 | 166:2448 | 1440 | error-company |
| A-ERROR-TYPE-1440 | 166:2508 | 1440 | error-type |
| A-ERROR-DESCRIPTION-1440 | 166:2568 | 1440 | error-description |
| A-ERROR-QUANTITY-1440 | 166:2628 | 1440 | error-quantity |
| A-ERROR-NOTES-1440 | 166:2688 | 1440 | error-notes |
| A-ERROR-REPLY-1440 | 166:2748 | 1440 | error-reply |
| A-ERROR-ITEMS-1440 | 166:2808 | 1440 | error-items |
| A-SENDING-1440 | 166:2869 | 1440 | sending |
| A-SENT-1440 | 166:2930 | 1440 | sent |
| A-FAILED-1440 | 166:2942 | 1440 | failed |
| B-LIST-ZERO-1440 | 166:3003 | 1440 | list-zero |
| B-LIST-FILLED-1440 | 166:3086 | 1440 | list-filled |
| B-DETAIL-ZERO-1440 | 166:3163 | 1440 | detail-zero |
| B-DETAIL-DRAFT-1440 | 166:3222 | 1440 | detail-draft |
| B-DETAIL-SUBMITTED-1440 | 166:3287 | 1440 | detail-submitted |
| B-DETAIL-ACKNOWLEDGED-1440 | 166:3355 | 1440 | detail-acknowledged |
| B-DETAIL-QUOTED-1440 | 166:3424 | 1440 | detail-quoted |
| B-DETAIL-ACCEPTED-1440 | 166:3496 | 1440 | detail-accepted |
| B-DETAIL-DECLINED-1440 | 166:3566 | 1440 | detail-declined |
| B-COMPOSE-1440 | 166:3636 | 1440 | compose |
| B-CONFIRM-ACKNOWLEDGED-1440 | 166:3719 | 1440 | confirm-acknowledged |
| B-CONFIRM-QUOTED-1440 | 166:3783 | 1440 | confirm-quoted |
| B-CONFIRM-ACCEPTED-1440 | 166:3848 | 1440 | confirm-accepted |
| B-CONFIRM-DECLINED-1440 | 166:3913 | 1440 | confirm-declined |
| B-LIST-ZERO-375 | 166:3978 | 375 | list-zero |
| B-LIST-FILLED-375 | 166:3988 | 375 | list-filled |
| B-DETAIL-ZERO-375 | 166:4012 | 375 | detail-zero |
| B-DETAIL-DRAFT-375 | 166:4018 | 375 | detail-draft |
| B-DETAIL-SUBMITTED-375 | 166:4030 | 375 | detail-submitted |
| B-DETAIL-ACKNOWLEDGED-375 | 166:4045 | 375 | detail-acknowledged |
| B-DETAIL-QUOTED-375 | 166:4061 | 375 | detail-quoted |
| B-DETAIL-ACCEPTED-375 | 166:4080 | 375 | detail-accepted |
| B-DETAIL-DECLINED-375 | 166:4097 | 375 | detail-declined |
| B-COMPOSE-375 | 166:4114 | 375 | compose |
| B-CONFIRM-ACKNOWLEDGED-375 | 166:4144 | 375 | confirm-acknowledged |
| B-CONFIRM-QUOTED-375 | 166:4155 | 375 | confirm-quoted |
| B-CONFIRM-ACCEPTED-375 | 166:4167 | 375 | confirm-accepted |
| B-CONFIRM-DECLINED-375 | 166:4179 | 375 | confirm-declined |
| E1 | 166:4191 | 960 | E1 · Customer · Request received · submitted |
| E2 | 166:4200 | 960 | E2 · Store · New request · submitted |
| E3 | 166:4209 | 960 | E3 · Customer · Your quote · quoted |
| E4 | 166:4218 | 960 | E4 · Customer · Accepted · accepted |
| E5 | 166:4227 | 960 | E5 · Store · Accepted · accepted |
| E6 | 166:4236 | 960 | E6 · Customer · Declined · declined |
| E7 | 166:4245 | 960 | E7 · Store · Declined · declined |
| B-MENU-375 | 167:3263 | 375 | menu-open |

## Exact wording register — every entry is awaiting founder approval

Braced values are data bindings. Existing menu labels are reused, unchanged, from
the canonical case-study menu. The static strings below are exact new draft copy.
Email subjects, plain-text bodies and HTML bodies are also reproduced in E1–E7
and QUOTE-EMAILS-DRAFT.md; each is part of this approval register.

- W001: "{site.name}"
- W002: "Home   About   Contact   Privacy"
- W003: "Request a quote"
- W004: "Name"
- W005: "Email"
- W006: "Phone (optional)"
- W007: "Company (optional)"
- W008: "Item 1"
- W009: "Type"
- W010: "Product or service"
- W011: "Quantity"
- W012: "1"
- W013: "Notes (optional)"
- W014: "Add another item"
- W015: "How should we reply?"
- W016: "Email   /   Phone"
- W017: "Privacy"
- W018: "Send request"
- W019: "{customer_name}"
- W020: "{customer_email}"
- W021: "{customer_phone}"
- W022: "{customer_company}"
- W023: "{product_or_service}"
- W024: "{item_description}"
- W025: "{quantity}"
- W026: "{item_notes}"
- W027: "Remove item"
- W028: "Item 2"
- W029: "Enter your name using 120 characters or fewer."
- W030: "Enter your email address."
- W031: "invalid-email"
- W032: "Enter a valid email address."
- W033: "Enter a phone number so we can reply by phone."
- W034: "Phone"
- W035: "Enter a valid phone number."
- W036: "Use 120 characters or fewer for the company name."
- W037: "Choose product or service."
- W038: "Enter an item description using 240 characters or fewer."
- W039: "Enter a whole quantity of 1 or more."
- W040: "Use 2,000 characters or fewer for item notes."
- W041: "Choose email or phone."
- W042: "Add at least one item."
- W043: "Sending request…"
- W044: "Sending…"
- W045: "Request sent"
- W046: "Your quote request has been sent to {shop_name}."
- W047: "Your request could not be sent. Your details are still here. Try again."
- W048: "Try again"
- W049: "Tisan"
- W050: "Quote requests"
- W051: "Request"
- W052: "Status"
- W053: "No quote requests yet."
- W054: "{request_id} · {customer_name}"
- W055: "submitted"
- W056: "acknowledged"
- W057: "quoted"
- W058: "accepted"
- W059: "declined"
- W060: "Select a request to view its details."
- W061: "Request {request_id}"
- W062: "Status: draft"
- W063: "Name: {customer_name}\nEmail: {customer_email}\nPhone: {customer_phone}\nCompany: {customer_company}\nReply preference: {reply_method}"
- W064: "Items"
- W065: "{product_or_service} · {item_description}\nQuantity: {quantity}\nNotes: {item_notes}"
- W066: "History"
- W067: "draft · {draft_at}"
- W068: "Status: submitted"
- W069: "submitted · {submitted_at}"
- W070: "Acknowledge"
- W071: "Status: acknowledged"
- W072: "acknowledged · {acknowledged_at}"
- W073: "Send a quote"
- W074: "Status: quoted"
- W075: "quoted · {quoted_at}"
- W076: "Quote: {quote_amount} {quote_currency}\nValid until: {valid_until}\nMessage: {quote_message}"
- W077: "Mark accepted"
- W078: "Mark declined"
- W079: "Status: accepted"
- W080: "accepted · {accepted_at}"
- W081: "Status: declined"
- W082: "declined · {declined_at}"
- W083: "Request {request_id} · acknowledged"
- W084: "Amount"
- W085: "{quote_amount}"
- W086: "Currency"
- W087: "{quote_currency}"
- W088: "Valid until"
- W089: "{valid_until}"
- W090: "Message"
- W091: "{quote_message}"
- W092: "Review quote"
- W093: "Cancel"
- W094: "Acknowledge this request?"
- W095: "submitted → acknowledged"
- W096: "Confirm acknowledgement"
- W097: "Send this quote?"
- W098: "acknowledged → quoted"
- W099: "Amount: {quote_amount} {quote_currency}\nValid until: {valid_until}\nMessage: {quote_message}"
- W100: "Confirm and send quote"
- W101: "Mark this quote accepted?"
- W102: "quoted → accepted"
- W103: "Record this change only after the customer has confirmed their decision."
- W104: "Confirm accepted"
- W105: "Mark this quote declined?"
- W106: "quoted → declined"
- W107: "Confirm declined"
- W108: "Menu"
- W109: "DRAFT · Founder approval required"
- W110: "E1 · Customer · Request received · submitted"
- W111: "Subject"
- W112: "We received your quote request — {shop_name}"
- W113: "Plain-text body"
- W114: "Hello {customer_name},\n\n{shop_name} has received your quote request {request_id}.\n\n{items}\n\nReply preference: {reply_method}\nWe will contact you using the details you provided.\n\n{shop_name}"
- W115: "HTML body"
- W116: "<h1>We received your quote request</h1>\n<p>Hello {customer_name},</p>\n<p>{shop_name} has received your quote request {request_id}.</p>\n<ul>{items}</ul>\n<p>Reply preference: {reply_method}</p>\n<p>We will contact you using the details you provided.</p>\n<p>{shop_name}</p>"
- W117: "E2 · Store · New request · submitted"
- W118: "New quote request {request_id}"
- W119: "A new quote request is ready for {shop_name}.\n\nRequest: {request_id}\nReceived: {submitted_at}\nName: {customer_name}\nEmail: {customer_email}\nPhone: {customer_phone}\nCompany: {customer_company}\nReply preference: {reply_method}\n\n{items}\n\nOpen the request: {request_url}"
- W120: "<h1>New quote request</h1>\n<p>A new quote request is ready for {shop_name}.</p>\n<dl>\n<dt>Request</dt><dd>{request_id}</dd>\n<dt>Received</dt><dd>{submitted_at}</dd>\n<dt>Name</dt><dd>{customer_name}</dd>\n<dt>Email</dt><dd>{customer_email}</dd>\n<dt>Phone</dt><dd>{customer_phone}</dd>\n<dt>Company</dt><dd>{customer_company}</dd>\n<dt>Reply preference</dt><dd>{reply_method}</dd>\n</dl>\n<ul>{items}</ul>\n<p><a href=\"{request_url}\">Open the request</a></p>"
- W121: "E3 · Customer · Your quote · quoted"
- W122: "Your quote from {shop_name} — {request_id}"
- W123: "Hello {customer_name},\n\nYour quote from {shop_name} is ready.\nRequest: {request_id}\n\n{items}\n\nAmount: {quote_amount} {quote_currency}\nValid until: {valid_until}\n\n{quote_message}\n\nReply to this email to accept or decline the quote.\n\n{shop_name}"
- W124: "<h1>Your quote</h1>\n<p>Hello {customer_name},</p>\n<p>Your quote from {shop_name} is ready.</p>\n<p>Request: {request_id}</p>\n<ul>{items}</ul>\n<p><strong>Amount: {quote_amount} {quote_currency}</strong></p>\n<p>Valid until: {valid_until}</p>\n<p>{quote_message}</p>\n<p>Reply to this email to accept or decline the quote.</p>\n<p>{shop_name}</p>"
- W125: "E4 · Customer · Accepted · accepted"
- W126: "Quote accepted — {shop_name} — {request_id}"
- W127: "Hello {customer_name},\n\nYour acceptance has been recorded for quote {request_id} from {shop_name}.\nAmount: {quote_amount} {quote_currency}\nRecorded: {changed_at}\n\n{shop_name} will contact you about the next steps."
- W128: "<h1>Quote accepted</h1>\n<p>Hello {customer_name},</p>\n<p>Your acceptance has been recorded for quote {request_id} from {shop_name}.</p>\n<p>Amount: {quote_amount} {quote_currency}</p>\n<p>Recorded: {changed_at}</p>\n<p>{shop_name} will contact you about the next steps.</p>"
- W129: "E5 · Store · Accepted · accepted"
- W130: "Quote {request_id} accepted"
- W131: "{customer_name}'s acceptance of quote {request_id} has been recorded.\nAmount: {quote_amount} {quote_currency}\nRecorded: {changed_at}\n\nOpen the request: {request_url}"
- W132: "<h1>Quote accepted</h1>\n<p>{customer_name}'s acceptance of quote {request_id} has been recorded.</p>\n<p>Amount: {quote_amount} {quote_currency}</p>\n<p>Recorded: {changed_at}</p>\n<p><a href=\"{request_url}\">Open the request</a></p>"
- W133: "E6 · Customer · Declined · declined"
- W134: "Quote declined — {shop_name} — {request_id}"
- W135: "Hello {customer_name},\n\nYour decision to decline quote {request_id} from {shop_name} has been recorded.\nRecorded: {changed_at}\n\nYou can reply to this email if you would like to discuss the quote.\n\n{shop_name}"
- W136: "<h1>Quote declined</h1>\n<p>Hello {customer_name},</p>\n<p>Your decision to decline quote {request_id} from {shop_name} has been recorded.</p>\n<p>Recorded: {changed_at}</p>\n<p>You can reply to this email if you would like to discuss the quote.</p>\n<p>{shop_name}</p>"
- W137: "E7 · Store · Declined · declined"
- W138: "Quote {request_id} declined"
- W139: "{customer_name}'s decision to decline quote {request_id} has been recorded.\nRecorded: {changed_at}\n\nOpen the request: {request_url}"
- W140: "<h1>Quote declined</h1>\n<p>{customer_name}'s decision to decline quote {request_id} has been recorded.</p>\n<p>Recorded: {changed_at}</p>\n<p><a href=\"{request_url}\">Open the request</a></p>"
- W141: "invalid-phone"
- W142: "{company_name: over 120 characters}"
- W143: "0"
- W144: "{item_notes: over 2,000 characters}"

## Email frames

E1 customer request received and E2 store new request correspond to submitted.
E3 customer your quote corresponds to quoted. E4/E5 notify customer/store of
accepted; E6/E7 notify customer/store of declined. Each frame has subject,
plain-text body and HTML body. No marketing or tracking pixels.
Founder approval must cover recipients, reply routing, omitted optional rows,
item rendering, date/time formatting and the exact copy in the draft email file.

## Verification and review evidence

Source reads, library inspection, component/variable reuse and frame inventory
were performed in this isolated branch. Visual layout and prototype checks are
being recorded before handoff. Founder browser acceptance has not occurred and
must not be claimed from tool screenshots. Claude opens the PR from this branch;
the founder alone merges. A separate review thread may require changes on the
same branch and PR.

