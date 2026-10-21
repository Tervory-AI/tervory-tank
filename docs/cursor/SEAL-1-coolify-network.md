# SEAL-1: keep sealed containers off Coolify's network

> Written 21 Oct 2026. Found live on Boston by a read-only `docker network inspect` (Grok, 21 Oct, 12:04 PT).

## What is wrong
- **Coolify adds its own app network to every service in a compose file,** unless that service uses `network_mode` (`coolify/bootstrap/helpers/parsers.php`, `applicationParser`: the `$baseNetwork` is added whenever `$use_network_mode` is false).
- **That network is not internal.** It has a gateway, so it reaches the internet. On Boston:
  - `base-sandbox` is on `<app uuid>` (internal=false) as well as `_sandbox` (internal=true);
  - `base-browser` is on `<app uuid>` (internal=false) as well as `_browser` (internal=true).
- **So both can reach the internet directly,** and they can also reach every other Base service on that network (`agent-base`, `base-brain`, the gateway) without going through the corridor.
- **Radix is very likely the same:** `agent-radix` should reach only `tervory-gw-radix` (internal) and `proxy-link` (internal). If Coolify also puts it on its app network, it has direct internet and the egress proxy is bypassed.

## The fix: raw compose for sealed rooms
In Coolify's **Raw Compose Deployment** mode, the compose file is deployed as written. Coolify adds only its labels; no networks and no `env_file` (`ApplicationDeploymentJob`, `oldRawParser`).

**Files you may change:**
- `agents/base/docker-compose.yml` and `agents/radix/docker-compose.yml`;
- `agents/base/` browser and gateway code (point 4 only);
- new `ops/seal-check.sh`;
- new `tests/test_room_seal.py`;
- `docs/cursor/ROOMS.md` (a short "Sealed rooms" section).

1. **Make both files raw-ready:**
   - every variable is passed by explicit `environment:` interpolation, since raw mode has no `env_file`;
   - every service names its networks;
   - no `ports:`;
   - named volumes keep the same names, so data survives the switch. If that is not possible, say so in the PR.
2. **CI test (`tests/test_room_seal.py`):**
   - Parse every `agents/*/docker-compose*.yml` and simulate Coolify's normal mode (add a non-internal app network to every service without `network_mode`).
   - Fail if any service declared only on internal networks would end up on a non-internal one, unless its compose file carries the comment `# coolify: raw compose` at the top.
   - Base and Radix carry that comment.
   - Also fail if a service on an internal network declares `ports:`.
3. **Live check (`ops/seal-check.sh`, read-only, run on the host):**
   - For every container labelled `coolify.applicationUuid`, list its networks and their `Internal` flag.
   - Exit non-zero, naming the container and network, if any container that joins an internal network also joins a non-internal one, other than the declared corridor services:
     - `agent-base`, `base-brain` and `base-browser-gateway` on `tervory-gw-base`;
     - `egress-proxy` on `egress`.
   - Print one line per room: "sealed" or "LEAK: <container> on <network>".
   - Grok runs it after every deploy of Base or Radix, and Ghost picks it up later.
4. **The browser holds no Tank key.**
   - `base-browser` runs untrusted web pages, so remove `TANK_KEY` and `TANK_REGION` from it.
   - Only `base-browser-gateway` talks to Tank. If the browser needs a receipt, it asks the gateway.

## Founder step after merge
For agent-base, and for agent-radix once it is deployed: in Coolify go to the app, then **Advanced**, turn on **Raw Compose Deployment** and redeploy. This setting is not available through Coolify's API.

## Done when
CI is green. The test fails on today's main file in normal mode and passes in raw mode. The PR shows `seal-check.sh` output from a fixture.
