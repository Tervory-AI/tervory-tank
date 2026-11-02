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

A EMPTY, FILLED-ONE and FILLED are draft. All A ERROR states remain draft and preserve the
other fields. FILLED-ONE shows one item. FILLED shows two items and Remove item; all editable screens show
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
| E1 | 166:4191 | 600 | E1 |
| E2 | 166:4200 | 600 | E2 |
| E3 | 166:4209 | 600 | E3 |
| E4 | 166:4218 | 600 | E4 |
| E5 | 166:4227 | 600 | E5 |
| E6 | 166:4236 | 600 | E6 |
| E7 | 166:4245 | 600 | E7 |
| E1-375 | 207:21765 | 375 | E1 |
| E2-375 | 207:21783 | 375 | E2 |
| E3-375 | 207:21812 | 375 | E3 |
| E4-375 | 207:21833 | 375 | E4 |
| E5-375 | 207:21850 | 375 | E5 |
| E6-375 | 207:21866 | 375 | E6 |
| E7-375 | 207:21883 | 375 | E7 |
| B-MENU-375 | 167:3263 | 375 | menu-open |
| A-FILLED-ONE-390 | 170:3036 | 390 | filled-one |
| A-FILLED-ONE-768 | 170:3096 | 768 | filled-one |
| A-FILLED-ONE-1440 | 170:3156 | 1440 | filled-one |
| SPEC | 172:3525 | 1440 | complete draft register |

## Exact wording register — every entry is awaiting founder approval

Braced values are data bindings. Existing menu labels are reused, unchanged, from
the canonical case-study menu. The register below is read back from visible screen text, including reused menu labels and data bindings; new wording remains draft.
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
- W010: "Product"
- W011: "Service"
- W012: "Product or service"
- W013: "Quantity"
- W014: "1"
- W015: "Notes (optional)"
- W016: "Add another item"
- W017: "How should we reply?"
- W018: "Phone"
- W019: "Privacy"
- W020: "Send request"
- W021: "{customer_name}"
- W022: "{customer_email}"
- W023: "{customer_phone}"
- W024: "{customer_company}"
- W025: "{item_description}"
- W026: "{quantity}"
- W027: "{item_notes}"
- W028: "Remove item"
- W029: "Item 2"
- W030: "Enter your name using 120 characters or fewer."
- W031: "Enter your email address."
- W032: "invalid-email"
- W033: "Enter a valid email address."
- W034: "Enter a phone number so we can reply by phone."
- W035: "invalid-phone"
- W036: "Enter a valid phone number."
- W037: "{company_name: over 120 characters}"
- W038: "Use 120 characters or fewer for the company name."
- W039: "Choose product or service."
- W040: "Enter an item description using 240 characters or fewer."
- W041: "0"
- W042: "Enter a whole quantity of 1 or more."
- W043: "{item_notes: over 2,000 characters}"
- W044: "Use 2,000 characters or fewer for item notes."
- W045: "Choose email or phone."
- W046: "Add at least one item."
- W047: "Sending request…"
- W048: "Sending…"
- W049: "Request sent"
- W050: "Your quote request has been sent to {shop_name}."
- W051: "Your request could not be sent. Your details are still here. Try again."
- W052: "Try again"
- W053: "Dashboard"
- W054: "Projects"
- W055: "Chats"
- W056: "Integrations"
- W057: "Connections"
- W058: "The Squad"
- W059: "New Notices"
- W060: "Settings"
- W061: "Support"
- W062: "Contact Us"
- W063: "Tisan"
- W064: "Quote requests"
- W065: "Request"
- W066: "Status"
- W067: "No quote requests yet."
- W068: "{request_id} · {customer_name}"
- W069: "submitted"
- W070: "acknowledged"
- W071: "quoted"
- W072: "accepted"
- W073: "declined"
- W074: "Select a request to view its details."
- W075: "Request {request_id}"
- W076: "Status: draft"
- W077: "Name: {customer_name}\nEmail: {customer_email}\nPhone: {customer_phone}\nCompany: {customer_company}\nReply preference: {reply_method}"
- W078: "Items"
- W079: "{product_or_service} · {item_description}\nQuantity: {quantity}\nNotes: {item_notes}"
- W080: "History"
- W081: "draft · {draft_at}"
- W082: "Status: submitted"
- W083: "submitted · {submitted_at}"
- W084: "Acknowledge"
- W085: "Status: acknowledged"
- W086: "acknowledged · {acknowledged_at}"
- W087: "Send a quote"
- W088: "Status: quoted"
- W089: "quoted · {quoted_at}"
- W090: "Quote: {quote_amount} {quote_currency}\nValid until: {valid_until}\nMessage: {quote_message}"
- W091: "Mark accepted"
- W092: "Mark declined"
- W093: "Status: accepted"
- W094: "accepted · {accepted_at}"
- W095: "Status: declined"
- W096: "declined · {declined_at}"
- W097: "Request {request_id} · acknowledged"
- W098: "Amount"
- W099: "{quote_amount}"
- W100: "Currency"
- W101: "{quote_currency}"
- W102: "Valid until"
- W103: "{valid_until}"
- W104: "Message"
- W105: "{quote_message}"
- W106: "Review quote"
- W107: "Cancel"
- W108: "Acknowledge this request?"
- W109: "submitted → acknowledged"
- W110: "Confirm acknowledgement"
- W111: "Send this quote?"
- W112: "acknowledged → quoted"
- W113: "Amount: {quote_amount} {quote_currency}\nValid until: {valid_until}\nMessage: {quote_message}"
- W114: "Confirm and send quote"
- W115: "Mark this quote accepted?"
- W116: "quoted → accepted"
- W117: "Record this change only after the customer has confirmed their decision."
- W118: "Confirm accepted"
- W119: "Mark this quote declined?"
- W120: "quoted → declined"
- W121: "Confirm declined"
- W122: "Menu"
- W123: "DRAFT · Founder approval required"
- W124: "E1 · Customer · Request received · submitted"
- W125: "Subject"
- W126: "We received your quote request — {shop_name}"
- W127: "Plain-text body"
- W128: "Hello {customer_name},\n\n{shop_name} has received your quote request {request_id}.\n\n{items}\n\nReply preference: {reply_method}\nWe will contact you using the details you provided.\n\n{shop_name}"
- W129: "HTML body"
- W130: "We received your quote request"
- W131: "Hello {customer_name},"
- W132: "{shop_name} has received your quote request {request_id}."
- W133: "{items}"
- W134: "Reply preference: {reply_method}"
- W135: "We will contact you using the details you provided."
- W136: "{shop_name}"
- W137: "HTML source"
- W138: "<h1>We received your quote request</h1>\n<p>Hello {customer_name},</p>\n<p>{shop_name} has received your quote request {request_id}.</p>\n<ul>{items}</ul>\n<p>Reply preference: {reply_method}</p>\n<p>We will contact you using the details you provided.</p>\n<p>{shop_name}</p>"
- W139: "E2 · Store · New request · submitted"
- W140: "New quote request {request_id}"
- W141: "A new quote request is ready for {shop_name}.\n\nRequest: {request_id}\nReceived: {submitted_at}\nName: {customer_name}\nEmail: {customer_email}\nPhone: {customer_phone}\nCompany: {customer_company}\nReply preference: {reply_method}\n\n{items}\n\nOpen the request: {request_url}"
- W142: "New quote request"
- W143: "A new quote request is ready for {shop_name}."
- W144: "{request_id}"
- W145: "Received"
- W146: "{submitted_at}"
- W147: "Company"
- W148: "Reply preference"
- W149: "{reply_method}"
- W150: "Open the request"
- W151: "<h1>New quote request</h1>\n<p>A new quote request is ready for {shop_name}.</p>\n<dl>\n<dt>Request</dt><dd>{request_id}</dd>\n<dt>Received</dt><dd>{submitted_at}</dd>\n<dt>Name</dt><dd>{customer_name}</dd>\n<dt>Email</dt><dd>{customer_email}</dd>\n<dt>Phone</dt><dd>{customer_phone}</dd>\n<dt>Company</dt><dd>{customer_company}</dd>\n<dt>Reply preference</dt><dd>{reply_method}</dd>\n</dl>\n<ul>{items}</ul>\n<p><a href=\"{request_url}\">Open the request</a></p>"
- W152: "E3 · Customer · Your quote · quoted"
- W153: "Your quote from {shop_name} — {request_id}"
- W154: "Hello {customer_name},\n\nYour quote from {shop_name} is ready.\nRequest: {request_id}\n\n{items}\n\nAmount: {quote_amount} {quote_currency}\nValid until: {valid_until}\n\n{quote_message}\n\nReply to this email to accept or decline the quote.\n\n{shop_name}"
- W155: "Your quote"
- W156: "Your quote from {shop_name} is ready."
- W157: "Request: {request_id}"
- W158: "Amount: {quote_amount} {quote_currency}"
- W159: "Valid until: {valid_until}"
- W160: "Reply to this email to accept or decline the quote."
- W161: "<h1>Your quote</h1>\n<p>Hello {customer_name},</p>\n<p>Your quote from {shop_name} is ready.</p>\n<p>Request: {request_id}</p>\n<ul>{items}</ul>\n<p><strong>Amount: {quote_amount} {quote_currency}</strong></p>\n<p>Valid until: {valid_until}</p>\n<p>{quote_message}</p>\n<p>Reply to this email to accept or decline the quote.</p>\n<p>{shop_name}</p>"
- W162: "E4 · Customer · Accepted · accepted"
- W163: "Quote accepted — {shop_name} — {request_id}"
- W164: "Hello {customer_name},\n\nYour acceptance has been recorded for quote {request_id} from {shop_name}.\nAmount: {quote_amount} {quote_currency}\nRecorded: {changed_at}\n\n{shop_name} will contact you about the next steps."
- W165: "Quote accepted"
- W166: "Your acceptance has been recorded for quote {request_id} from {shop_name}."
- W167: "Recorded: {changed_at}"
- W168: "{shop_name} will contact you about the next steps."
- W169: "<h1>Quote accepted</h1>\n<p>Hello {customer_name},</p>\n<p>Your acceptance has been recorded for quote {request_id} from {shop_name}.</p>\n<p>Amount: {quote_amount} {quote_currency}</p>\n<p>Recorded: {changed_at}</p>\n<p>{shop_name} will contact you about the next steps.</p>"
- W170: "E5 · Store · Accepted · accepted"
- W171: "Quote {request_id} accepted"
- W172: "{customer_name}'s acceptance of quote {request_id} has been recorded.\nAmount: {quote_amount} {quote_currency}\nRecorded: {changed_at}\n\nOpen the request: {request_url}"
- W173: "{customer_name}'s acceptance of quote {request_id} has been recorded."
- W174: "<h1>Quote accepted</h1>\n<p>{customer_name}'s acceptance of quote {request_id} has been recorded.</p>\n<p>Amount: {quote_amount} {quote_currency}</p>\n<p>Recorded: {changed_at}</p>\n<p><a href=\"{request_url}\">Open the request</a></p>"
- W175: "E6 · Customer · Declined · declined"
- W176: "Quote declined — {shop_name} — {request_id}"
- W177: "Hello {customer_name},\n\nYour decision to decline quote {request_id} from {shop_name} has been recorded.\nRecorded: {changed_at}\n\nYou can reply to this email if you would like to discuss the quote.\n\n{shop_name}"
- W178: "Quote declined"
- W179: "Your decision to decline quote {request_id} from {shop_name} has been recorded."
- W180: "You can reply to this email if you would like to discuss the quote."
- W181: "<h1>Quote declined</h1>\n<p>Hello {customer_name},</p>\n<p>Your decision to decline quote {request_id} from {shop_name} has been recorded.</p>\n<p>Recorded: {changed_at}</p>\n<p>You can reply to this email if you would like to discuss the quote.</p>\n<p>{shop_name}</p>"
- W182: "E7 · Store · Declined · declined"
- W183: "Quote {request_id} declined"
- W184: "{customer_name}'s decision to decline quote {request_id} has been recorded.\nRecorded: {changed_at}\n\nOpen the request: {request_url}"
- W185: "{customer_name}'s decision to decline quote {request_id} has been recorded."
- W186: "<h1>Quote declined</h1>\n<p>{customer_name}'s decision to decline quote {request_id} has been recorded.</p>\n<p>Recorded: {changed_at}</p>\n<p><a href=\"{request_url}\">Open the request</a></p>"
- W187: "Close menu"

## Email frames

E1 customer request received and E2 store new request correspond to submitted.
E3 customer your quote corresponds to quoted. E4/E5 notify customer/store of
accepted; E6/E7 notify customer/store of declined. Each frame has a subject,
plain-text body, editable rendered HTML preview and exact HTML source. No marketing or tracking pixels.
Founder approval must cover recipients, reply routing, omitted optional rows,
item rendering, date/time formatting and the exact copy in the draft email file.

Every email now has a 600px frame and a matching 375px phone frame. Original frame IDs identify the 600px versions. Subject, plain text, rendered HTML wording, HTML source and every braced variable are unchanged. Text reflows at existing font sizes with Jost/Inter and existing token bindings. All 14 widths and exact text pairs pass; zero text-bound overflow findings. E2 was visually checked at both widths. All wording remains draft pending founder approval.

## Verification and review evidence

Source reads, library inspection, component/variable reuse and frame inventory
were performed in this isolated branch. The source-to-frame structural audit found 90 draft screen/email frames,
713 component instances and 2,135 visible text nodes. Font families were only
Jost and Inter. Horizontal and vertical text-overflow counts were 0. All 128 prototype
destinations (including inherited menu links) existed. Founder browser acceptance has not occurred and
must not be claimed from tool screenshots. Claude opens the PR from this branch;
the founder alone merges. A separate review thread may require changes on the
same branch and PR.


## Reused and draft components

- Local Field master 165:9 and Notes master 165:14 follow the contact template.
- Primary action master 165:19 uses standard accent/paper with large bold text.
- Reply preference master 167:2675 and Product/service choice master 171:3147 provide explicit radio choices.
- Case-study menu masters 125:10372 / 125:10373 and table 43:389 / 43:405 are reused as instances.
- Foundation frame 164:20 records the six named brand variables.
- SPEC node 172:3525 is this same text rendered as editable Figma layers.

## Exact commands and results

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-tisan-quote-design
cd /workspace/codex-tisan-quote-design
git fetch origin main
git checkout -B codex/tisan-quote-design origin/main
ls agents/tisan/README.md agents/tisan/scaffold.py agents/tisan/templates/next-site/app/contact/page.tsx
```

Result: clone/fetch/checkout passed; all three required source files existed.
The branch is codex/tisan-quote-design; main was not changed.
The isolated clone lacked a commit identity; the already established Codex
identity from the earlier task checkout was reused locally. No secrets were read.
Email draft commit 65edb036 and SPEC checkpoint 9b717447 were pushed successfully.

Figma audit used this read-only algorithm (no model or live data call):
```js
const page = await figma.getNodeByIdAsync('164:12');
await figma.setCurrentPageAsync(page);
const screens = page.children.filter(n => n.type === 'FRAME' && /^(A-|B-|E[1-7] ·)/.test(n.name));
// Recursively visit visible TEXT and INSTANCE nodes within these screens.
// Compare text x + width to parent width AND y + height to parent height; collect fonts and reaction destinations.
// Resolve every destination with figma.getNodeByIdAsync; report any missing node.
```
Result: 90 frames, 713 instances, 2,135 visible text nodes, only Jost/Inter,
0 horizontal or vertical overflow findings, 128 existing prototype destinations.
These are design checks, not a live implementation test or founder acceptance.

## Original checks before responsive email revision

- Desktop Workspace shells preserve the canonical menu's 900px minimum height,
  grow for longer request details, and show Connections, The Squad and New Notices.
- Final Figma audit: 90 screen/email frames; 713 instances; 2,135 visible text nodes;
  only Jost and Inter; 0 horizontal or vertical text-overflow findings;
  128 existing prototype destinations. All seven email frames have rendered HTML previews.
- Visual checks inspected the 390px filled-one customer form, 375px store list,
  1440px send-quote confirmation (after correcting its height), and E3 quote email.
  These were tool-rendered design checks, not screenshots of the founder's browser.
- `git diff --check origin/main...HEAD` returned exit 0 with no output.
- A Python documentation check asserted 90 unique screen/email rows plus SPEC,
  seven email sections, seven plain-text and seven HTML bodies, no unresolved SPEC ID,
  and absence of QUOTE-EMAILS.md. Result: PASS.
- Draft page link: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=164-12
- SPEC link: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=172-3525
- Awaiting: founder opens the Figma page and approves the draft wording and frames.
  Founder browser screenshots and separate PR review are not yet available and are not claimed.
- Only docs/figma/tisan/SPEC.md and docs/figma/tisan/QUOTE-EMAILS-DRAFT.md are changed
  in git. No production runtime, source template, API, schema or live-data file changed.


## Responsive email revision — 1 November 2026

Every email now has a 600px frame and a matching 375px phone frame. Original frame IDs identify the 600px versions. Subject, plain text, rendered HTML wording, HTML source and every braced variable are unchanged. Text reflows at existing font sizes with Jost/Inter and existing token bindings. All 14 widths and exact text pairs pass; zero text-bound overflow findings. E2 was visually checked at both widths. All wording remains draft pending founder approval.
The 90-frame audit above predates these seven new phone frames; there are now 97 screen/email frames.

Local checks: a Python comparison against the previous email-draft commit found
all fourteen fenced plain-text/HTML blocks unchanged; the screen register now has
97 unique screen/email rows plus SPEC. `git diff --check` passed. Screenshots were
rendered by Figma for design inspection, not taken from the founder's browser.
No approval or email sending is claimed.
