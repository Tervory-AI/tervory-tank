"""Environment for the worker service. On Boston the values come from /etc/tervory-workers/worker.env.

Settings hold no secret. The GitHub App key (GITHUB_APP_PRIVATE_KEY) is checked here and,
in from_env, kept in a private file for the service; Settings only carries that path.
"""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
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


# The service's own key directory, inside the tmpfs state dir. Task directories are
# tervory-worker-<issue>-<hex>, so this never collides with one and is never mounted.
KEY_DIR = ".github-app"
KEY_NAME = "app-key.pem"
LEGACY_KEY_FILE = "/run/secrets/github_app_key"


# 127.0.0.1 for the service on the host, 10.0.2.2 for a task (slirp4netns host loopback).
LOOPBACK_TANK_HOSTS = frozenset({"127.0.0.1", "10.0.2.2"})


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
    private_key_file: str = LEGACY_KEY_FILE
    # "file" when GITHUB_APP_PRIVATE_KEY_FILE names the key, "setting" when it comes from GITHUB_APP_PRIVATE_KEY.
    private_key_source: str = "file"
    region: str = "us-east"
    proxy_port: int = 8765
    service_port: int = 8000
    state_dir: str = "/var/lib/workers"
    code_dir: str = "/srv/tervory-workers/app"

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
    if link not in {"internal", "wireguard", "loopback"}:
        raise SettingsError("WORKER_LINK must be loopback, internal or wireguard")
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
    if link == "loopback":
        # Boston host: the service reaches Tank on 127.0.0.1 (compose binds 127.0.0.1:8100).
        # A task container reaches the same port through slirp4netns as 10.0.2.2.
        if parsed.scheme != "http" or lowered not in LOOPBACK_TANK_HOSTS or parsed.port is None:
            raise SettingsError("with WORKER_LINK=loopback TANK_URL is http://127.0.0.1:<port>")
        return url
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
    state_dir = _text(data, "WORKER_STATE_DIR", "/var/lib/workers") or "/var/lib/workers"
    key_file, key_source = _key_location(data, state_dir)
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
        private_key_file=key_file,
        private_key_source=key_source,
        region=region,
        proxy_port=_int(data, "WORKER_PROXY_PORT", 8765, minimum=1024, maximum=65535),
        service_port=_int(data, "WORKER_PORT", 8000, minimum=1024, maximum=65535),
        state_dir=state_dir,
        code_dir=_code_dir(data),
    )


def _code_dir(data: dict[str, str]) -> str:
    value = _text(data, "WORKER_CODE_DIR", "/srv/tervory-workers/app") or "/srv/tervory-workers/app"
    if not value.startswith("/") or ".." in value.split("/") or not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", value):
        raise SettingsError("WORKER_CODE_DIR must be an absolute path")
    return value


def private_key_path(state_dir: str) -> str:
    return str(Path(state_dir) / KEY_DIR / KEY_NAME)


def _key_location(data: dict[str, str], state_dir: str) -> tuple[str, str]:
    """GITHUB_APP_PRIVATE_KEY_FILE wins when set. Otherwise the GITHUB_APP_PRIVATE_KEY setting."""
    from workers.github_app import PrivateKeyRejected, private_key_from_setting

    named = _text(data, "GITHUB_APP_PRIVATE_KEY_FILE")
    if named:
        return named, "file"
    setting = str(data.get("GITHUB_APP_PRIVATE_KEY") or "")
    if not setting.strip():
        return LEGACY_KEY_FILE, "file"
    try:
        private_key_from_setting(setting)
    except PrivateKeyRejected as exc:
        raise SettingsError(str(exc)) from None
    return private_key_path(state_dir), "setting"


def stage_private_key(settings: Settings, data: dict[str, str]) -> None:
    """Write the key from the setting to the service's private file. Never logged."""
    from workers.github_app import PrivateKeyRejected, private_key_from_setting, write_private_key

    if settings.private_key_source != "setting":
        return
    try:
        write_private_key(private_key_from_setting(str(data.get("GITHUB_APP_PRIVATE_KEY") or "")), settings.private_key_file)
    except PrivateKeyRejected as exc:
        raise SettingsError(str(exc)) from None


def from_env() -> Settings:
    data = dict(os.environ)
    settings = from_mapping(data)
    stage_private_key(settings, data)
    # Child processes (podman and the task runner) do not inherit the key.
    os.environ.pop("GITHUB_APP_PRIVATE_KEY", None)
    return settings
