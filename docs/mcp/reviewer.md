# Reviewer test account

The founder creates the Clerk user, the organization, and the sample data. This repository does not contain a password, an API key, or the test account.

Put the email and the password in the Anthropic submission form only. Reviewers see them there. Do not commit them.

## What the account needs before review

One Clerk user who belongs to one organization. In that organization, before the reviewer signs in:

- A few catalogue products the reviewer can search for by name.
- A few enriched business records, including one batch id the reviewer can quote.
- Nothing else is required for the price watch. The reviewer adds a public product page with the watch tool.

Criminal-law questions must be refused. A short United States or South Africa company-law question must return passages.

## How a reviewer connects

1. In Claude, add a custom connector.
2. Server address: `https://mcp.tervory.com/mcp`
3. Sign in with the test user when Claude opens Tervory.
4. Continue past the screen that names `claude.ai`.
5. Confirm the organization is the one that holds the sample catalogue and records.

## What to run

- Search a catalogue: ask for one of the sample product names. The answer should name that product, a model, and a cost.
- Look up records: ask for the sample batch, or for a word that appears on a sample record.
- Enrich a list: send two made-up company rows. The answer should include a batch id. Do not send more than 100 rows.
- Research a legal question: ask a company-law question and name the United States or South Africa. Then ask a criminal-law question and confirm it is refused with no research passages.
- Write a market brief: ask for a short brief on one ordinary product category. Claims that include a source should show the URL and the date.
- Watch a price: give a public `https://` product page. The answer should confirm the watch.

Every answer should include sources, the model, and a cost in USD. A second organization, if one is created later, must not see these rows.
