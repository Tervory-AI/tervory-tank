"""Explicit home records for synthetic tenants in disposable integration databases."""
from uuid import UUID


async def onboard(connection, *tenants, region='us-east'):
    for tenant in tenants:
        await connection.execute("""INSERT INTO tank.tenants(tenant_id,home_region,onboarded_by)
            VALUES($1,$2,'fixture-founder') ON CONFLICT(tenant_id)
            DO UPDATE SET home_region=EXCLUDED.home_region""", UUID(str(tenant)), region)
