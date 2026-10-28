"""Explicit founder opt-in per client and agent. No automatic publication."""

import json
import uuid
from hermes.deidentify import deidentify
from hermes.record_schema import PLATFORM_TENANT


class Publisher:
    def __init__(self, records):
        self.records = records

    async def set_policy(
        self, agent: str, tenant: str, actor: str, enabled: bool, identifiers: dict
    ) -> dict:
        s = self.records.schema(agent)
        if enabled:
            deidentify("inventory validation", [], tenant, identifiers)
        async with self.records.pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {s}.memory_publish_policy(tenant_id,enabled,identifiers,updated_by)
                VALUES($1,$2,$3::jsonb,$4) ON CONFLICT(tenant_id) DO UPDATE
                SET enabled=EXCLUDED.enabled,identifiers=EXCLUDED.identifiers,
                updated_by=EXCLUDED.updated_by,updated_at=now()""",
                uuid.UUID(tenant),
                enabled,
                json.dumps(identifiers),
                actor,
            )
        return dict(agent=agent, tenant_id=tenant, enabled=enabled)

    async def publish(
        self, agent: str, tenant: str, source_id: str, actor: str
    ) -> dict:
        s = self.records.schema(agent)
        tenant_id, source = uuid.UUID(tenant), uuid.UUID(source_id)
        target = uuid.uuid5(source, "platform-memory:" + tenant)
        result, published = "disabled", None
        async with self.records.pool.acquire() as conn, conn.transaction():
            # Lock policy against concurrent revoke; no row means off.
            policy = await conn.fetchrow(
                f"SELECT * FROM {s}.memory_publish_policy WHERE tenant_id=$1 FOR UPDATE",
                tenant_id,
            )
            if policy and policy["enabled"]:
                row = await conn.fetchrow(
                    f"""SELECT * FROM {s}.memory_records
                    WHERE tenant_id=$1 AND id=$2 AND tier='client' FOR SHARE""",
                    tenant_id,
                    source,
                )
                if not row:
                    result = "missing"
                else:
                    try:
                        claim, evidence = deidentify(
                            row["claim"],
                            json.loads(row["evidence"]),
                            tenant,
                            json.loads(policy["identifiers"]),
                        )
                    except ValueError:
                        result = "refused"
                    else:
                        await self.records.lock(conn, s, target)
                        created = await conn.fetchval(
                            f"""INSERT INTO {s}.memory_records
                            (id,tenant_id,claim,evidence,confidence,last_verified,tier)
                            VALUES($1,$2,$3,$4::jsonb,$5,$6,'platform') ON CONFLICT(id) DO NOTHING RETURNING id""",
                            target,
                            uuid.UUID(PLATFORM_TENANT),
                            claim,
                            json.dumps(evidence),
                            row["confidence"],
                            row["last_verified"],
                        )
                        result = "published" if created else "already_published"
                        published = target
                        await self.records.enqueue(
                            conn,
                            s,
                            target,
                            uuid.UUID(PLATFORM_TENANT),
                            self.records.model,
                        )
            await conn.execute(
                f"""INSERT INTO {s}.memory_publish_log(tenant_id,actor,source_row,result,published_row)
                VALUES($1,$2,$3,$4,$5)""",
                tenant_id,
                actor,
                source,
                result,
                published,
            )
        # Indexing is durable but deliberately not coupled to publication success.
        return dict(result=result, published_row=str(published) if published else None)
