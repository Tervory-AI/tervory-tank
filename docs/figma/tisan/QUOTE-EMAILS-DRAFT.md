# Tisan quote emails — DRAFT, awaiting founder approval

Design-only wording. No messages are sent by this work. This file must not be
renamed to `QUOTE-EMAILS.md` until the founder approves the exact wording.
All interpolation values must be escaped for HTML; `{items}` is a structured
item list rendered as text or escaped list items, never trusted HTML.
No marketing, tracking pixels, remote images, payment fields or payment links.
The request itself records the customer's approval to request a quote.

## Responsive layout revision — 1 November 2026

Each email has a 600px version and a 375px phone version on Figma page
**3 · Tisan quote**. The original frame IDs now identify the 600px versions.
Subject, plain-text body, rendered HTML wording, HTML source and all braced
variables are unchanged. Jost/Inter and existing brand-token bindings are retained.
Text reflows at its existing font size; frame height grows to fit. The review
frame uses 32px side padding at 600px and 20px at 375px; HTML preview padding
remains 24px. These are draft designs, not sent emails or approved implementation.

| Email | 600px frame | 375px frame |
| --- | --- | --- |
| E1 | 166:4191 | 207:21765 |
| E2 | 166:4200 | 207:21783 |
| E3 | 166:4209 | 207:21812 |
| E4 | 166:4218 | 207:21833 |
| E5 | 166:4227 | 207:21850 |
| E6 | 166:4236 | 207:21866 |
| E7 | 166:4245 | 207:21883 |

Validation: all 14 frame widths checked; every text layer matches its original
and paired version exactly; only Jost/Inter fonts; zero text-bound overflow
findings. The longest email (E2) was visually inspected at both widths using
Figma-rendered screenshots. Founder acceptance is still pending.

## E1 · Customer · Request received · submitted

Subject: We received your quote request — {shop_name}

Plain text:
```text
Hello {customer_name},

{shop_name} has received your quote request {request_id}.

{items}

Reply preference: {reply_method}
We will contact you using the details you provided.

{shop_name}
```

HTML body:
```html
<h1>We received your quote request</h1>
<p>Hello {customer_name},</p>
<p>{shop_name} has received your quote request {request_id}.</p>
<ul>{items}</ul>
<p>Reply preference: {reply_method}</p>
<p>We will contact you using the details you provided.</p>
<p>{shop_name}</p>
```

## E2 · Store · New request · submitted

Subject: New quote request {request_id}

Plain text:
```text
A new quote request is ready for {shop_name}.

Request: {request_id}
Received: {submitted_at}
Name: {customer_name}
Email: {customer_email}
Phone: {customer_phone}
Company: {customer_company}
Reply preference: {reply_method}

{items}

Open the request: {request_url}
```

HTML body:
```html
<h1>New quote request</h1>
<p>A new quote request is ready for {shop_name}.</p>
<dl>
<dt>Request</dt><dd>{request_id}</dd>
<dt>Received</dt><dd>{submitted_at}</dd>
<dt>Name</dt><dd>{customer_name}</dd>
<dt>Email</dt><dd>{customer_email}</dd>
<dt>Phone</dt><dd>{customer_phone}</dd>
<dt>Company</dt><dd>{customer_company}</dd>
<dt>Reply preference</dt><dd>{reply_method}</dd>
</dl>
<ul>{items}</ul>
<p><a href="{request_url}">Open the request</a></p>
```

## E3 · Customer · Your quote · quoted

Subject: Your quote from {shop_name} — {request_id}

Plain text:
```text
Hello {customer_name},

Your quote from {shop_name} is ready.
Request: {request_id}

{items}

Amount: {quote_amount} {quote_currency}
Valid until: {valid_until}

{quote_message}

Reply to this email to accept or decline the quote.

{shop_name}
```

HTML body:
```html
<h1>Your quote</h1>
<p>Hello {customer_name},</p>
<p>Your quote from {shop_name} is ready.</p>
<p>Request: {request_id}</p>
<ul>{items}</ul>
<p><strong>Amount: {quote_amount} {quote_currency}</strong></p>
<p>Valid until: {valid_until}</p>
<p>{quote_message}</p>
<p>Reply to this email to accept or decline the quote.</p>
<p>{shop_name}</p>
```

## E4 · Customer · Accepted · accepted

Subject: Quote accepted — {shop_name} — {request_id}

Plain text:
```text
Hello {customer_name},

Your acceptance has been recorded for quote {request_id} from {shop_name}.
Amount: {quote_amount} {quote_currency}
Recorded: {changed_at}

{shop_name} will contact you about the next steps.
```

HTML body:
```html
<h1>Quote accepted</h1>
<p>Hello {customer_name},</p>
<p>Your acceptance has been recorded for quote {request_id} from {shop_name}.</p>
<p>Amount: {quote_amount} {quote_currency}</p>
<p>Recorded: {changed_at}</p>
<p>{shop_name} will contact you about the next steps.</p>
```

## E5 · Store · Accepted · accepted

Subject: Quote {request_id} accepted

Plain text:
```text
{customer_name}'s acceptance of quote {request_id} has been recorded.
Amount: {quote_amount} {quote_currency}
Recorded: {changed_at}

Open the request: {request_url}
```

HTML body:
```html
<h1>Quote accepted</h1>
<p>{customer_name}'s acceptance of quote {request_id} has been recorded.</p>
<p>Amount: {quote_amount} {quote_currency}</p>
<p>Recorded: {changed_at}</p>
<p><a href="{request_url}">Open the request</a></p>
```

## E6 · Customer · Declined · declined

Subject: Quote declined — {shop_name} — {request_id}

Plain text:
```text
Hello {customer_name},

Your decision to decline quote {request_id} from {shop_name} has been recorded.
Recorded: {changed_at}

You can reply to this email if you would like to discuss the quote.

{shop_name}
```

HTML body:
```html
<h1>Quote declined</h1>
<p>Hello {customer_name},</p>
<p>Your decision to decline quote {request_id} from {shop_name} has been recorded.</p>
<p>Recorded: {changed_at}</p>
<p>You can reply to this email if you would like to discuss the quote.</p>
<p>{shop_name}</p>
```

## E7 · Store · Declined · declined

Subject: Quote {request_id} declined

Plain text:
```text
{customer_name}'s decision to decline quote {request_id} has been recorded.
Recorded: {changed_at}

Open the request: {request_url}
```

HTML body:
```html
<h1>Quote declined</h1>
<p>{customer_name}'s decision to decline quote {request_id} has been recorded.</p>
<p>Recorded: {changed_at}</p>
<p><a href="{request_url}">Open the request</a></p>
```

## Delivery and approval contract — also draft

- Customer emails go only to the request's customer email; store emails go to
  the shop's configured quote recipient. Do not guess either destination.
- The store records accepted/declined only after the customer's decision;
  a staff click must not be described as an independently verified customer reply.
- Quotes use the shop reply address. No public accept/decline endpoints are added.
- Omit empty optional phone/company rows, rather than displaying invented values.
- Render item type, description, quantity and supplied notes in `{items}`.
- Preserve timestamps with timezone. No response-time promise is drafted.
- State change and delivery status are distinct: a failed email must not falsely
  imply a quote was delivered. Implementation is gated on founder approval.
