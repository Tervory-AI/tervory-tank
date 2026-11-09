"""Gate before (finish): admission control on live paid code calls (ENGINE_CODE_ADMISSION_ENABLED).

Per tenant, at most ENGINE_CODE_ADMISSION_CONCURRENT paid code calls run at once
and at most ENGINE_CODE_ADMISSION_PER_MINUTE start in any 60 seconds (blank uses
2 and 20). Over either cap the round is answered at $0 with a clear hold message
and no paid call is queued. Checked after preflight approved the paid step, so a
held round never spends; the slot is released when the paid call returns.

The counters are per process, like the existing shadow busy guard: Tank runs one
uvicorn process, and nothing here can leak into the money tables. A slot that is
never released (a paid call that never happened) expires after HOLD_SECONDS.
"""
from __future__ import annotations

import math
import os
import re
import time
from collections import deque

CONCURRENT = 'ENGINE_CODE_ADMISSION_CONCURRENT'
PER_MINUTE = 'ENGINE_CODE_ADMISSION_PER_MINUTE'
DEFAULTS = {CONCURRENT: 2, PER_MINUTE: 20}
WINDOW = 60.0
HOLD_SECONDS = 180.0  # longer than the 150 s code-turn timeout

_running: dict[str, dict[str, float]] = {}
_recent: dict[str, deque] = {}


class SettingError(ValueError):
    pass


def limits() -> dict[str, int]:
    values = {}
    for name, default in DEFAULTS.items():
        raw = os.environ.get(name, '')
        if raw == '':
            values[name] = default
        elif re.fullmatch(r'[1-9][0-9]{0,3}', raw) and int(raw) <= 1000:
            values[name] = int(raw)
        else:
            raise SettingError(name)
    return values


def admit(tenant_id, turn_id: str, *, now: float | None = None) -> dict | None:
    """Reserve a slot for this paid call, or say why it must wait (None = admitted)."""
    cap = limits()
    now = time.monotonic() if now is None else now
    tenant = str(tenant_id)
    running = {turn: expiry for turn, expiry in _running.get(tenant, {}).items() if expiry > now}
    recent = _recent.setdefault(tenant, deque())
    while recent and recent[0] <= now - WINDOW:
        recent.popleft()
    if len(running) >= cap[CONCURRENT]:
        _running[tenant] = running
        return {'reason': 'concurrent', 'limit': cap[CONCURRENT], 'running': len(running), 'retry_after_s': 5,
                'message': f'Your workspace already has {len(running)} paid code answers running, the most allowed at once. '
                           'Send this again when one finishes. No model call was made.'}
    if len(recent) >= cap[PER_MINUTE]:
        _running[tenant] = running
        wait = max(1, math.ceil(recent[0] + WINDOW - now))
        return {'reason': 'per_minute', 'limit': cap[PER_MINUTE], 'retry_after_s': wait,
                'message': f'Your workspace reached {cap[PER_MINUTE]} paid code calls in the last minute. '
                           f'Send this again in {wait} s. No model call was made.'}
    running[str(turn_id)] = now + HOLD_SECONDS
    _running[tenant] = running
    recent.append(now)
    return None


def release(tenant_id, turn_id: str) -> None:
    tenant = str(tenant_id)
    running = _running.get(tenant)
    if running is not None:
        running.pop(str(turn_id), None)
        if not running:
            _running.pop(tenant, None)


def reset() -> None:
    _running.clear()
    _recent.clear()
