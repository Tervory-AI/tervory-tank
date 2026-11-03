"""A8: earliest cheapest known window for an approved model, bounded by a deadline."""
from __future__ import annotations

import math
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

BATCH_SECONDS = 24 * 60 * 60  # Existing provider batch completion_window is 24h.
MAX_WAIT = timedelta(days=7)
DEFAULT_WAIT = timedelta(days=2)


def minute(value: str) -> int:
    hour, minute = map(int, value.split(':'))
    if not 0 <= hour <= 24 or not 0 <= minute < 60 or (hour == 24 and minute):
        raise ValueError('Invalid price window time')
    return hour * 60 + minute


def multiplier(settings: dict | None, at: datetime) -> float:
    if settings is None:
        return 1.0
    local = at.astimezone(ZoneInfo(settings['timezone']))
    rate = float(settings['charge_multiplier'])
    if not math.isfinite(rate) or not 0 < rate <= 1:
        raise ValueError('Invalid price multiplier')
    rates = [1.0]
    if local.date().isoformat() in settings.get('dates', []):
        rates.append(rate)
    for window in settings['windows']:
        start, end = minute(window['start']), minute(window['end'])
        if not start < end:
            raise ValueError('Split price windows crossing midnight')
        price = float(window.get('charge_multiplier', rate))
        if not math.isfinite(price) or not 0 < price <= 1:
            raise ValueError('Invalid window multiplier')
        if any(not isinstance(day, int) or not 0 <= day <= 6 for day in window['days']):
            raise ValueError('Invalid weekday')
        if local.weekday() in window['days'] and start <= local.hour * 60 + local.minute < end:
            rates.append(price)
    return min(rates)


def choose(info: dict, *, at: datetime, deadline: datetime | None, batch_discount: float | None) -> dict:
    end = deadline or at + DEFAULT_WAIT
    if end.tzinfo is None or end <= at or end > at + MAX_WAIT:
        raise HTTPException(422, 'The work deadline must be in the next seven days and include a timezone.')
    settings = info.get('offpeak')
    candidates = {at}
    try:
        multiplier(settings, at)
        if settings:
            zone = ZoneInfo(settings['timezone'])
            day = at.astimezone(zone).date()
            for offset in range(9):
                date = day + timedelta(days=offset)
                starts = [0] if date.isoformat() in settings.get('dates', []) else []
                starts.extend(minute(w['start']) for w in settings['windows'] if date.weekday() in w['days'])
                for start in starts:
                    local = datetime.combine(date, time(), zone) + timedelta(minutes=start)
                    # Both folds cover repeated hours; UTC round trips shift a
                    # nonexistent spring start to the next actual clock instant.
                    candidates.update(local.replace(fold=fold).astimezone(UTC) for fold in (0, 1))
        choices = [(multiplier(settings, stamp), stamp, 'direct') for stamp in candidates if at <= stamp < end]
        # Provider batch prices are fixed: never invent a stacked time discount.
        if batch_discount is not None and at + timedelta(seconds=BATCH_SECONDS + 120) <= end:
            if not math.isfinite(batch_discount) or not 0 < batch_discount <= 1:
                raise ValueError('Invalid batch price')
            choices.append((batch_discount, at, 'batch'))
        rate, start, mode = min(choices)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, 'Scheduling price data is unavailable or invalid') from exc
    return {'not_before': start, 'deadline_at': end, 'dispatch_mode': mode, 'scheduled_multiplier': rate}
