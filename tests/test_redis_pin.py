"""Redis is pinned to a patched 7.4.x by multi-arch index digest, the same in both regions.

No network and no Docker. It reads the two compose files only.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^redis:7\.4\.(\d+)@sha256:[0-9a-f]{64}$")


def _redis_image(name: str) -> str:
    compose = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
    return compose["services"]["redis"]["image"]


def test_redis_is_pinned_by_digest_to_a_patched_7_4() -> None:
    for name in ("docker-compose.yml", "docker-compose.za.yml"):
        image = _redis_image(name)
        match = PIN.match(image)
        assert match, f"{name} redis image must be redis:7.4.x@sha256:<index digest>, got {image}"
        # 7.4.11 fixes CVE-2026-81934; 7.4.9 fixed CVE-2026-23479.
        assert int(match.group(1)) >= 11, f"{name} redis must be 7.4.11 or later"


def test_redis_pin_is_identical_in_both_regions() -> None:
    assert _redis_image("docker-compose.yml") == _redis_image("docker-compose.za.yml")


def test_redis_stays_unpublished_and_untouched() -> None:
    for name in ("docker-compose.yml", "docker-compose.za.yml"):
        compose = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
        redis = compose["services"]["redis"]
        assert "ports" not in redis, f"{name} redis must not publish ports"
        assert redis["command"] == ["redis-server", "--appendonly", "yes"]
