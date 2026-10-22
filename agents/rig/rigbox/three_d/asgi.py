"""Opt-in deployment entry point: uvicorn rigbox.three_d.asgi:app.

Keeps other lanes' app.py unchanged. The existing image already copies rigbox.
No stand-in or automatic entitlement in this production entry point.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from chassis.storage import Storage
from app import app

from .api import mount
from .assets import R2Assets
from .engine import Engine
from .forge import BrainForge
from .store import Store

mount(app)
_original = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    async with _original(application):
        # Missing R2 credentials must not break Rig's existing catalogue API.
        # Initialize lazily at the first 3D storage operation and show its error.
        application.state.rig_three_d = Engine(Store(application.state.pool), application.state.rig,
            BrainForge(application.state.http, os.environ.get("TANK_KEY", "")), LazyR2())
        yield
        if application.state.rig_three_d.assets.instance:
            await application.state.rig_three_d.assets.instance.storage.close()


class LazyR2:
    instance = None

    def backend(self):
        from chassis.storage import StorageError
        from rigbox.service import RigError
        if self.instance is None:
            try:
                self.instance = R2Assets(Storage("rig"))
            except StorageError:
                raise RigError("storage", "Model storage is not connected.", 503) from None
        return self.instance

    async def put(self, *args):
        return await self.backend().put(*args)

    async def get(self, *args):
        return await self.backend().get(*args)


app.router.lifespan_context = lifespan
bundle = Path(__file__).with_name("widget")
if bundle.is_dir():
    app.mount("/3d", StaticFiles(directory=bundle, html=True), name="rig-three-d-test")
