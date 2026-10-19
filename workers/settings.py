"""Environment for the worker service. Values come from Coolify. Nothing here is a secret."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
DEFAULT_REPO = "Tervory-AI/tervory-tank"
DEFAULT_TASK_TYPE = "reason.brief"
MEMORY_RE = re.compile(r"^[1-9][0-9]{0,3}[kmg]$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PROVIDER_HOSTS = frozenset(
    {
        "api.openai.com",
        "openai.com",
        "api.anthropic.com",
        "anthropic.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "openrouter.ai",
        "api.deepseek.com",
        "api.mistral.ai",
        "api.x.ai",
        "litellm",
    }
)


class SettingsError(ValueError):
    pass


class RegionRefused(SettingsError):
    pass


@dataclass(frozen=True)
class Settings:
    max_tasks: int = 1
    task_cpus: float = 2
    task_memory: str = "4g"
    task_timeout_s: int = 90 * 60
    link: str = "internal"
    tank_url: str = "http://tank:8000"
    tenant_id: str = PLATFORM_TENANT
    task_type: str = DEFAULT_TASK_TYPE
    repo: str = DEFAULT_REPO
    poll_s: int = 60
    app_id: str = ""
    installation_id: str = ""
    private_key_file: str = "/run/secrets/github_app_key"
    region: str = "us-east"
    proxy_port: int = 8765
    service_port: int = 8000
    state_dir: str = "/var/lib/workers"

    @property
    def tank_host(self) -> str:
        return urlsplit(self.tank_url).hostname or ""

    @property
    def tank_port(self) -> int:
        parsed = urlsplit(self.tank_url)
        if parsed.port:
            return parsed.port
        return 443 if parsed.scheme == "https" else 80

    @property
    def github_ready(self) -> bool:
        return bool(self.app_id and self.installation_id and self.private_key_file)

    def route_url(self) -> str:
        parsed = urlsplit(self.tank_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise SettingsError("TANK_URL must be an http or https origin")
        if parsed.path not in {"", "/"}:
            raise SettingsError("TANK_URL must be Tank's origin")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise SettingsError("TANK_URL must not carry a secret or a query")
        return f"{parsed.scheme}://{parsed.netloc}/v1/route"


def _text(data: dict[str, str], name: str, default: str = "") -> str:
    raw = data.get(name)
    if raw is None:
        return default
    return str(raw).strip()


def _int(data: dict[str, str], name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = _text(data, name)
    if not raw:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise SettingsError(f"{name} must be a whole number") from exc
    if value < minimum or value > maximum:
        raise SettingsError(f"{name} is outside {minimum}..{maximum}")
    return value


def _float(data: dict[str, str], name: str, default: float) -> float:
    raw = _text(data, name)
    if not raw:
        value = default
    else:
        try:
            value = float(raw)
        except ValueError as exc:
            raise SettingsError(f"{name} must be a number") from exc
    if value <= 0 or value > 16:
        raise SettingsError(f"{name} is outside 0..16")
    return value


def validate_tank_url(url: str, link: str) -> str:
    if link not in {"internal", "wireguard"}:
        raise SettingsError("WORKER_LINK must be internal or wireguard")
    parsed = urlsplit(url)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        raise SettingsError("TANK_URL must be an http or https origin")
    if parsed.username or parsed.password:
        raise SettingsError("TANK_URL must not carry a secret")
    lowered = host.lower().rstrip(".")
    if lowered in PROVIDER_HOSTS or any(lowered.endswith("." + item) for item in PROVIDER_HOSTS):
        raise SettingsError("TANK_URL must be Tank, not a model provider")
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        address = None
    if link == "wireguard":
        if address is None or not address.is_private or address.is_loopback:
            raise SettingsError("on the third server TANK_URL must be a private WireGuard address")
    elif address is not None and (address.is_global or address.is_loopback or address.is_multicast):
        raise SettingsError("Tank stays off the public internet")
    elif address is None and "." in lowered and not lowered.endswith(".internal"):
        # Docker DNS names are a single label (tank). A public hostname is not the private link.
        raise SettingsError("on Boston TANK_URL is the internal name tank, or a private address")
    return url


def assert_not_za(region: str) -> None:
    if region.strip().lower() == "za":
        raise RegionRefused("workers do not run on the ZA server")


def from_mapping(data: dict[str, str]) -> Settings:
    region = _text(data, "TANK_REGION", "us-east") or "us-east"
    assert_not_za(region)
    link = _text(data, "WORKER_LINK", "internal") or "internal"
    tank_url = validate_tank_url(_text(data, "TANK_URL", "http://tank:8000") or "http://tank:8000", link)
    memory = (_text(data, "WORKER_TASK_MEMORY", "4g") or "4g").lower()
    if not MEMORY_RE.fullmatch(memory):
        raise SettingsError("WORKER_TASK_MEMORY looks like 4g")
    repo = _text(data, "WORKER_REPO", DEFAULT_REPO) or DEFAULT_REPO
    if not REPO_RE.fullmatch(repo):
        raise SettingsError("WORKER_REPO must be owner/name")
    tenant = _text(data, "WORKER_TENANT_ID", PLATFORM_TENANT) or PLATFORM_TENANT
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", tenant):
        raise SettingsError("WORKER_TENANT_ID must be a tenant id")
    task_type = _text(data, "WORKER_TASK_TYPE", DEFAULT_TASK_TYPE) or DEFAULT_TASK_TYPE
    if not re.fullmatch(r"[a-z0-9._]{1,64}", task_type):
        raise SettingsError("WORKER_TASK_TYPE must be an existing Tank policy name")
    return Settings(
        max_tasks=_int(data, "WORKER_MAX_TASKS", 1, minimum=1, maximum=3),
        task_cpus=_float(data, "WORKER_TASK_CPUS", 2),
        task_memory=memory,
        task_timeout_s=_int(data, "WORKER_TASK_TIMEOUT_MINUTES", 90, minimum=1, maximum=240) * 60,
        link=link,
        tank_url=tank_url,
        tenant_id=tenant,
        task_type=task_type,
        repo=repo,
        poll_s=_int(data, "WORKER_POLL_SECONDS", 60, minimum=15, maximum=3600),
        app_id=_text(data, "GITHUB_APP_ID"),
        installation_id=_text(data, "GITHUB_APP_INSTALLATION_ID"),
        private_key_file=_text(data, "GITHUB_APP_PRIVATE_KEY_FILE", "/run/secrets/github_app_key"),
        region=region,
        proxy_port=_int(data, "WORKER_PROXY_PORT", 8765, minimum=1024, maximum=65535),
        service_port=_int(data, "WORKER_PORT", 8000, minimum=1024, maximum=65535),
        state_dir=_text(data, "WORKER_STATE_DIR", "/var/lib/workers") or "/var/lib/workers",
    )


def from_env() -> Settings:
    return from_mapping(dict(os.environ))
