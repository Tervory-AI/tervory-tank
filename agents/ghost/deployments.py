"""Read the latest Coolify deployment for an identified product; never deploy or read logs."""
import re
from urllib.parse import urlparse

from .inventory import container_app, coolify_settings
from .models import Observation, SITES, ROOMS


async def deployment_observation(http, target: str) -> Observation:
    if target not in {*SITES, *ROOMS, "tank"} or target == "za":
        raise ValueError("Unknown check target.")
    base, token = coolify_settings()
    if not token:
        raise RuntimeError("The read-only evidence feed is not connected.")

    async def get(path):
        response = await http.get(base + path, headers={"Authorization": "Bearer " + token},
                                  timeout=20, follow_redirects=False)
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise RuntimeError("The read-only evidence feed is not connected.")
        return response.json()

    try:
        applications = await get("/api/v1/applications")
        if not isinstance(applications, list):
            raise ValueError()
        host = urlparse(SITES.get(target, "")).hostname
        matches = []
        for row in applications:
            name = container_app(str(row.get("name") or "")).replace("-", "_")
            hosts = {urlparse(url.strip()).hostname for url in str(row.get("fqdn") or "").split(",")}
            if name in {target, "agent_" + target, "tervory_" + target} or (host and host in hosts):
                matches.append(row)
        if len(matches) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(matches[0].get("uuid") or "")):
            raise ValueError()
        data = await get("/api/v1/deployments/applications/" + matches[0]["uuid"])
        rows = data.get("deployments") if isinstance(data, dict) else data
        if not isinstance(rows, list) or not rows:
            raise ValueError()
        # Compare provider timestamps, never list order or status from an older deployment.
        from .advisories import parse_time
        if any(not isinstance(row, dict) or parse_time(row.get("created_at")) is None for row in rows):
            raise ValueError()
        latest = max(rows, key=lambda row: parse_time(row["created_at"]))
        status = latest.get("status")
        if status not in {"finished", "failed", "cancelled", "queued", "in_progress"}:
            raise ValueError()
        return Observation(target=target, signal="deploy", failing=status in {"failed", "cancelled"}, count=1)
    except Exception:
        raise RuntimeError("The read-only evidence feed is not connected.") from None
