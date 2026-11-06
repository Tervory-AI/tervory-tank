"""Configuration names only; incomplete rooms never start workers."""
import math
import os


def missing(*names):
    return [name for name in names if not os.environ.get(name, '').strip()]


def problems():
    result = missing('DATABASE_URL', 'TANK_KEY')
    try:
        interval = float(os.environ.get('DOMAIN_INTERVAL_S') or '10')
        if not math.isfinite(interval) or interval < 0:
            raise ValueError
    except ValueError:
        result.append('DOMAIN_INTERVAL_S')
    if os.environ.get('CHASSIS_ADMIN_DATABASE_URL') and not os.environ.get('CHASSIS_RLS_ADMIN_ROLE'):
        result.append('CHASSIS_RLS_ADMIN_ROLE')
    return result


def capabilities():
    return {
        'storage': missing('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TIGER', 'R2_SECRET_ACCESS_KEY_TIGER'),
        'email': missing('TIGER_SMTP_HOST', 'TIGER_SMTP_FROM', 'TIGER_SMTP_ALERT_ADDRESSES'),
    }
