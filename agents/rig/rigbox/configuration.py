"""Configuration diagnostics return setting names, never their values."""
import os
import asyncio


GROUPS = {
    'catalogue': ('DATABASE_URL',),
    'routing': ('TANK_KEY', 'RIG_RETAILER_KEY', 'RIG_TRUSTED_PROXY_CIDRS'),
    'widget': ('RIG_WIDGET_PUBLISHABLE_KEY',),
    'email': ('SMTP_HOST', 'SMTP_FROM'),
    'storage': ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_RIG', 'R2_SECRET_ACCESS_KEY_RIG'),
    'gpu': ('HF_JOBS_TOKEN', 'HF_JOBS_NAMESPACE'),
}


def missing(group, env=None):
    values = os.environ if env is None else env
    names = [name for name in GROUPS[group] if not values.get(name, '').strip()]
    if group == 'email' and values.get('SMTP_USER', '').strip() and 'SMTP_FROM' in names:
        names.remove('SMTP_FROM')
    if group == 'email' and values.get('SMTP_USER', '').strip() and not values.get('SMTP_PASSWORD', '').strip():
        names.append('SMTP_PASSWORD')
    return names


def report(env=None):
    return {group: {'ready': not (names := missing(group, env)), 'missing_settings': names}
            for group in GROUPS}


async def startup_missing(agent, env=None):
    values = os.environ if env is None else env
    names = missing('catalogue', values)
    if names:
        return names
    if values.get('CHASSIS_ADMIN_DATABASE_URL', '').strip():
        return [] if values.get('CHASSIS_RLS_ADMIN_ROLE', '').strip() else ['CHASSIS_RLS_ADMIN_ROLE']
    # Once RLS is enabled the shared chassis requires its separate admin pool.
    # Detect absent configuration before starting pools or background workers.
    import asyncpg
    from chassis.db import schema_for
    try:
        conn = await asyncpg.connect(values['DATABASE_URL'], timeout=10, command_timeout=10)
        try:
            enforced = await conn.fetchval('''SELECT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE c.relrowsecurity AND n.nspname=$1)''', schema_for(agent))
        finally:
            await conn.close(timeout=10)
    except (OSError, ValueError, asyncio.TimeoutError, asyncpg.PostgresError):
        return ['DATABASE_URL']
    if not enforced:
        return []
    names = ['CHASSIS_ADMIN_DATABASE_URL']
    if not values.get('CHASSIS_RLS_ADMIN_ROLE', '').strip():
        names.append('CHASSIS_RLS_ADMIN_ROLE')
    return names
