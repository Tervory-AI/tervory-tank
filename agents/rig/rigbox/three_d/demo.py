"""Cloud-only stand-in app. Never the production entry point."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from rigbox.api import mount as mount_public
from .api import mount
from .sample import PUBLIC_KEY, PLAIN_KEY, seed


@asynccontextmanager
async def lifespan(app):
    # A separate local database is required; never default to a production DSN.
    pool = await asyncpg.create_pool(os.environ["RIG_3D_TEST_DATABASE_URL"], min_size=1, max_size=4)
    try:
        engine, _ = await seed(pool, Path(os.environ["RIG_3D_TEST_DATA_DIR"]))
        app.state.rig, app.state.rig_three_d = engine.catalogue, engine
        yield
    finally:
        await pool.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
mount_public(app)
mount(app)


@app.get("/health")
async def health():
    return {"ok": True, "sample": True}


@app.get("/3d/config")
async def config():
    return {"publishable_key": PUBLIC_KEY, "photo_key": PLAIN_KEY, "product_id": "centre", "sample": True,
            "kiosk_id": "00000000-0000-0000-0000-000000003d10"}


bundle = Path(os.environ.get("RIG_3D_WIDGET_DIR", str(Path(__file__).with_name("widget"))))
app.mount("/3d", StaticFiles(directory=bundle, html=True), name="rig-3d-sample")
