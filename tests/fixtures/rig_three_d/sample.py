"""Opt-in neutral sample data for the cloud test page and integration tests."""
import json
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from rigbox.service import Service, hash_key
from rigbox.store import PgStore
from rigbox.three_d.assets import LocalAssets
from rigbox.three_d.contracts import Job, Review
from rigbox.three_d.engine import Engine
from fixtures.rig_three_d.forge import StubForge
from rigbox.three_d.store import Store

TENANT = UUID("00000000-0000-0000-0000-000000003d01")
WITHOUT_3D = UUID("00000000-0000-0000-0000-000000003d02")
PUBLIC_KEY = "rk_pub_rig5_sample"
PLAIN_KEY = "rk_pub_rig5_photos"


async def seed(pool, directory: Path, *, approve_models=True):
    catalogue = Service(PgStore(pool), rate_limit=1000)  # Explicit sample runner, not production traffic.
    await catalogue.store.apply_schema()
    admin_key = secrets.token_urlsafe(32)
    for tenant, public in [(TENANT, PUBLIC_KEY), (WITHOUT_3D, PLAIN_KEY)]:
        for key, kind in [(public, "publishable"), (admin_key, "admin")]:
            if tenant == WITHOUT_3D and kind == "admin":
                continue
            await pool.execute("""
                INSERT INTO agent_rig.keys (tenant_id,key_hash,kind,origins) VALUES ($1,$2,$3,$4)
                ON CONFLICT (key_hash) DO UPDATE SET origins=excluded.origins
            """, tenant, hash_key(key), kind, ["http://127.0.0.1:5173", "http://127.0.0.1:8035"])
        for sku, name, category, amount in [
            ("centre", "Centre", "base", 100), ("part-a", "Side module", "module", 20),
            ("part-b", "End module", "end", 30), ("part-tall", "Tall side module", "module", 25),
        ]:
            await pool.execute("""
                INSERT INTO agent_rig.products (tenant_id,id,sku,name,brand,category,price,currency,attributes)
                VALUES ($1,$2,$2,$3,'Sample',$4,$5,'USD','{"sample":true}')
                ON CONFLICT (tenant_id,sku) DO NOTHING
            """, tenant, sku, name, category, amount)
        for part in ("part-a", "part-b", "part-tall"):
            await pool.execute("""
                INSERT INTO agent_rig.fits (tenant_id,part_sku,fits_sku,source,approved)
                VALUES ($1,$2,'centre','sample',true) ON CONFLICT DO NOTHING
            """, tenant, part)
    engine = Engine(Store(pool), catalogue, StubForge(), LocalAssets(directory), sample=True)
    await engine.store.set_entitlement(TENANT, True, None, "USD")
    await engine.store.set_entitlement(WITHOUT_3D, False, None, "USD")
    if approve_models:
        for product in ("centre", "part-a", "part-b", "part-tall"):
            if await engine.store.approved(TENANT, product):
                continue
            metadata = json.loads((Path(__file__).with_name("models") / (product + ".json")).read_text())
            job = Job(id=uuid4(), tenant_id=TENANT, product_id=product, source="scan",
                      inputs=[f"{TENANT}/uploads/sample-{n}.jpg" for n in range(50)], dimensions_mm=metadata["dimensions_mm"], cost_cap_usd=0)
            await engine.submit(str(TENANT), job)
            result = await engine.poll(str(TENANT), job.id)
            if result["status"] != "draft":
                raise RuntimeError("The stand-in model failed its checks")
            # Only fixed test fixtures are pre-reviewed. Never called in asgi.py.
            await engine.approve(str(TENANT), job.id,
                                 Review(scale=True, appearance=True, attachment_points=True), "stand-in-fixture-review")
        for part, anchor in [("part-a", "left"), ("part-tall", "left"), ("part-b", "right")]:
            await engine.mount_points(str(TENANT), part, "centre", anchor, "attach")
    return engine, admin_key
