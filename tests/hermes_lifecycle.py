"""Personal Hermes calls use the same v1 assertions as shipped clients."""
import json
import httpx
from chassis.user_assertion import bind_personal_headers


def personal_headers(key, method, path, *, tenant, user, body=None, extra=None, params=None):
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode() if body is not None else b""
    target = httpx.URL("http://placeholder" + path)
    if params:
        target = target.copy_merge_params(params)
    headers = {"X-Tank-Key": key,
        **bind_personal_headers(key, method, target.raw_path.decode("ascii"), tenant=tenant, user=user, body=raw),
        **(extra or {})}
    if body is not None:
        headers["Content-Type"] = "application/json"
    return headers, raw
