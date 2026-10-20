# Context.dev documentation fixture

`brand-documented.json` is the abridged response printed under “Read the profile”
in https://docs.context.dev/brand/overview, retrieved 20 October 2026.
It is a **documented example**, not a captured API response or accuracy evidence.
The example omits credit metadata. Tests that add `X-Credits-Used: 10` use a
synthetic header based on https://docs.context.dev/account/credits; that header
is not represented as captured evidence.

Other error, malformed-response and timeout cases are synthetic mocks.
CI never contacts Context.dev. Claude will add sanitized real captures, with
provenance and actual credit metadata, after the key is configured.
