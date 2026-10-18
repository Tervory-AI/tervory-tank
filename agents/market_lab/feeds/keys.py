"""Per-feed API keys for Market Lab.

The values live in the environment (Coolify) or, when lab.vault is switched
on, in that vault. Tank holds the vault. This module never writes a value
into a log, a row, or an error string.

A feed named here stays off until the env var is non-empty, or lab.vault is
on and holds that name. A vault that is off contributes nothing. FRED is
read live and is not stored.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import replace

from feeds.models import SourceSpec

# Adapter -> env var. These feeds copy rows and stay off until the key is set.
ADAPTER_KEYS: dict[str, str] = {
    "census_population": "CENSUS_API_KEY",
    "census_trade": "CENSUS_API_KEY",
    "legiscan": "LEGISCAN_API_KEY",
    "eia": "EIA_API_KEY",
    "noaa_climate": "NOAA_TOKEN",
}

# Live read only. FRED's terms forbid a database copy, so the feeds runner
# never stores the series. The daily refresh reads them when this is set.
FRED_KEY = "FRED_API_KEY"

# Every name the box reads. Compose and .env.example must list each one.
KEY_NAMES: tuple[str, ...] = (
    "CENSUS_API_KEY",
    "LEGISCAN_API_KEY",
    "EIA_API_KEY",
    "NOAA_TOKEN",
    FRED_KEY,
)

_QUERY = re.compile(r"\?[^\s'\"<>]*")
_ASSIGNED = re.compile(r"(?i)\b(api_key|apikey|token|key)=([^&\s]+)")


def key_name_for(spec: SourceSpec) -> str:
    """Env var this feed needs, or '' when it runs without one."""
    if spec.key_name:
        return spec.key_name
    if spec.id.startswith("fred_"):
        return FRED_KEY
    return ADAPTER_KEYS.get(spec.adapter, "")


def bind_key(spec: SourceSpec) -> SourceSpec:
    """Copy the spec with the key name filled in from this registry."""
    name = key_name_for(spec)
    required = bool(name)
    if spec.key_name == name and spec.key_required is required:
        return spec
    return replace(spec, key_name=name, key_required=required)


# lab.vault, filled by the feeds runner after it asks Tank. Default off.
_vault_on = False
_vault_names: frozenset[str] = frozenset()
_resolver: Callable[[str], str] | None = None
_held: set[str] = set()


def configure_vault(
    *,
    enabled: bool,
    names: Iterable[str] = (),
    resolver: Callable[[str], str] | None = None,
) -> None:
    """Tell the feed gate about lab.vault. An off vault drops names and the resolver."""
    global _vault_on, _vault_names, _resolver
    _vault_on = bool(enabled)
    _vault_names = frozenset(str(name) for name in names) if _vault_on else frozenset()
    _resolver = resolver if _vault_on else None


def _remember(value: str) -> None:
    if len(value) >= 8:
        _held.add(value)


def feed_key(name: str) -> str:
    """The env value, or the vault value when lab.vault is on and holds this name.

    The value is not logged. An off vault is not asked.
    """
    env = os.environ.get(name, "").strip()
    if env:
        _remember(env)
        return env
    if not _vault_on or name not in _vault_names or _resolver is None:
        return ""
    try:
        value = str(_resolver(name) or "").strip()
    except Exception:
        return ""
    _remember(value)
    return value


def key_is_set(name: str) -> bool:
    """True when no key is required, the env var is set, or the on vault holds the name.

    This does not fetch the secret. The value is never returned.
    """
    if not name:
        return True
    if os.environ.get(name, "").strip():
        return True
    return bool(_vault_on and name in _vault_names)


def missing_key(spec: SourceSpec) -> str:
    """The env name when this feed must stay off, else ''."""
    name = key_name_for(spec)
    if not name or key_is_set(name):
        return ""
    return name


def redact(text: str) -> str:
    """Drop query strings and any configured key value from a stored error."""
    cleaned = _ASSIGNED.sub(r"\1=REDACTED", text)
    cleaned = _QUERY.sub("", cleaned)
    for name in KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if len(value) >= 8 and value in cleaned:
            cleaned = cleaned.replace(value, "REDACTED")
    for value in list(_held):
        if value and value in cleaned:
            cleaned = cleaned.replace(value, "REDACTED")
    return cleaned
