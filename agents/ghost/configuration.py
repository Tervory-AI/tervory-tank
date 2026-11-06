"""Readiness reports contain setting names, never their values."""
from __future__ import annotations

import math
import os


FEATURE_SETTINGS = {
    "watch": ("TANK_KEY",),
    "inventory": ("COOLIFY_TOKEN_GHOST",),
    "owner_email": ("AUTUMBRA_SMTP_HOST", "AUTUMBRA_SMTP_FROM"),
    "owner_links": ("AUTUMBRA_UNDO_TOKEN_SECRET",),
    "enforce": ("TENANT_ID", "SITE_NAME", "THREAT_PAYLOAD_QUEUE",
                "CLOUDFLARE_API_TOKEN_ENFORCE", "AUTUMBRA_HEALTH_SECRET"),
    "health_observer": ("SITE_NAME", "AUTUMBRA_HEALTH_SECRET"),
    "lifecycle": ("AUTUMBRA_LIFECYCLE_KEY", "AUTUMBRA_COOLIFY_URL",
                  "AUTUMBRA_COOLIFY_TOKEN", "AUTUMBRA_COOLIFY_PROJECT_UUID",
                  "AUTUMBRA_COOLIFY_SERVER_UUID", "AUTUMBRA_COOLIFY_ENVIRONMENT",
                  "AUTUMBRA_COOLIFY_GITHUB_APP_UUID"),
}


def missing_settings(feature: str) -> list[str]:
    return [name for name in FEATURE_SETTINGS[feature] if not os.environ.get(name, "").strip()]


def setting_status(feature: str) -> dict:
    missing = missing_settings(feature)
    return {"configured": not missing, "missing_settings": missing,
            "detail": "Missing settings: " + ", ".join(missing) if missing else "Configured."}


def interval_seconds(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name) or default)
        if not math.isfinite(value):
            return default
        return min(maximum, max(minimum, value))
    except ValueError:
        return default
