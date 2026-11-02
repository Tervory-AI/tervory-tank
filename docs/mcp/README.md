# Tervory MCP — Gate G1

Server address: `https://app.tervory.com/mcp`. This gate is **us-east only**. `https://za.tervory.com/mcp` returns 404.

The protocol and backend are implemented. The signed-in consent page at `/oauth/authorize` still requires the founder-approved **Figma page “7 · MCP”, frame 1** before its words or layout can be implemented. The setup steps below describe acceptance after that page lands and the founder merges; they are not a claim of a deployed or tested live connector.

## Connect

Use the existing Tervory account and select the organization whose records the connector may use. Tervory uses Clerk only to establish that signed-in identity. Tank issues the organization-bound OAuth grant; Clerk's OAuth provider is not used. Credentials stay between the client and Tervory, without copying a CLI token.

### Claude

1. Open Claude's **Customize → Connectors** and add a custom connector. Organization administrators use **Organization settings → Connectors**.
2. Name it Tervory and enter `https://app.tervory.com/mcp` as its remote server URL.
3. Use OAuth/sign-in authentication and **Register automatically** for a public client. No static client credentials are needed. Client ID Metadata Documents are also supported when the client uses public-client authentication (`none`).
4. Connect, sign in at Tervory, check the organization and client on the approved consent page, and approve.
5. Enable Tervory for the conversation. Ask “find FFL dealers in DC”; check the verified records and the corresponding thread and receipt in `/chats`. Ask to start a Base batch; follow its thread link and verify that nothing starts until Confirm there.

Claude's [custom connector instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) describe the current setup flow. Availability and organization permissions are controlled by Claude.

### ChatGPT

On ChatGPT's web interface, open **Plugins**, use the plus control and **Add custom MCP server**. Enter Tervory's server URL, choose OAuth with public-client authentication, and create/install the resulting plugin. Complete Tervory's organization-bound consent, then select the installed Tervory plugin in a conversation. Use CIMD or automatic registration, without static credentials. Workspace policy may restrict custom MCP servers.

See the [official OpenAI custom MCP server instructions](https://developers.openai.com/api/docs/guides/custom-mcp-server).

### Cursor

Add a remote server in Cursor's MCP configuration:

```json
{
  "mcpServers": {
    "Tervory": {
      "url": "https://app.tervory.com/mcp"
    }
  }
}
```

Connect and complete the browser OAuth flow. Dynamic registration accepts HTTPS callbacks and loopback HTTP callbacks at `127.0.0.1` or `localhost`, matching Cursor's remote OAuth flow. There is no local server or package to install for Tervory.

See [Cursor's MCP instructions](https://cursor.com/docs/mcp).

## Read, Confirm and revoke

The tool catalogue is the signed-in actor's `command.allowed_tools`, with the existing Command names and argument schemas. A read is computed from the existing adapter: `method == GET` and `paid == False`. Reads have `readOnlyHint: true`; they still create a durable Command proposal and use the same Confirm implementation automatically. Their result includes the stored receipt figures. A missing receipt stays pending; no cost is invented.

Every other tool creates only a pending card and returns its `/chats` thread link and card id. Confirm remains in Tervory. A read taking over 60 seconds continues on its thread and returns a running status and link. Founder tools remain restricted to the founder. Each MCP session has one client-named thread owned by its token's user and organization.

To revoke, open [CLI sign-ins](https://app.tervory.com/cli/sign-ins) for the same organization, find the entry named after the connected client and revoke it. The existing page lists MCP grants using the same rows as CLI grants. The next MCP request and refresh are refused. Removing the client-side connector is separate from revoking its Tervory grant.

## Protocol and implementation

- [MCP 2025-11-25 Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), JSON response mode. `GET /mcp` returns 405 because G1 does not send unsolicited SSE messages. DELETE terminates the authenticated session. Initialize, initialized notifications, tools/list, tools/call and ping are supported; resources and prompts are not advertised.
- Resource metadata: `/.well-known/oauth-protected-resource/mcp` and `/.well-known/oauth-protected-resource`. Authorization metadata: `/.well-known/oauth-authorization-server`.
- [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), OAuth authorization code with S256 PKCE, resource `https://app.tervory.com/mcp`, single-use ten-minute codes and public clients only. Redirects must exactly match validated metadata/registration. Unvalidated redirects never receive a browser redirect.
- Client metadata fetches reuse `access.public_get`, with public-address validation, pinned connections, no redirects and a 64 KiB bound. The bounded in-process metadata cache honors no-store/no-cache and never exceeds 24 hours. DCR limits each observed source address to 50 registrations an hour; proxy callers deliberately share their proxy's bucket, without trusting forwarding headers.
- Access credentials, hashing, one-hour access expiry and rotating thirty-day refresh reuse the CLI implementation. The `mcp` audience and client binding prevent use on CLI routes or through the CLI refresh endpoint; CLI tokens are refused by MCP. Codes, credentials and session handles are stored only as hashes.
- Accepted browser origins are exactly `https://app.tervory.com`, `https://claude.ai`, `https://chatgpt.com` and `https://cursor.com`; an absent Origin is accepted for server-side clients. Any other Origin is refused with 403.
- Workspace forwards only the six protocol headers to MCP. Public OAuth calls forward only the body and media type. Signed-in approval alone uses the existing us-east Workspace approval path. No new settings or secret values are required.
- New tenant tables follow the same conditional RLS rollout as `personal_tokens`. Legacy installations do not enable RLS merely by applying this schema. Enforced installations receive both tenant policies. The existing Tank startup guard is unchanged.
- Latest stable SDK checked: **`mcp==2.3.0`**, from [PyPI metadata](https://pypi.org/pypi/mcp/json). Its requirement `pydantic>=2.12.0` conflicts with Tank's frozen `pydantic==2.10.6` pin. The dependency resolver refuses that combination. Under the brief's fallback, G1 implements the four methods directly without changing frozen skill schemas or adding an SDK dependency.

## Acceptance still required

The founder completes the live Claude sign-in, verified FFL lookup, pending batch/Confirm check, matching `/chats` receipt and grant revocation. Founder screenshots and deployed connector acceptance have not been produced by synthetic tests. No live tokens, production SQL, production data changes or model calls were used to implement or test this gate.
