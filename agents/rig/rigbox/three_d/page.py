"""Optional terminal configuration, created only by an administrator save."""
import os
from pathlib import Path
import tempfile
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from rigbox.api import _admin, _service, _tenant
from rigbox.rooms import require_owner
from rigbox.service import RigError
from .contracts import Strict

router = APIRouter()


class PageConfig(Strict):
    publishable_key: str = Field(default='', pattern=r'^(rk_pub_[A-Za-z0-9_-]+)?$')
    photo_key: str = Field(default='', pattern=r'^(rk_pub_[A-Za-z0-9_-]+)?$')
    product_id: str = Field(default='', pattern=r'^([A-Za-z0-9][A-Za-z0-9_.-]{0,63})?$')
    kiosk_id: UUID | None = None


class SavedPage(PageConfig):
    tenant_id: UUID | None = None  # Ownership is private; old files remain readable.


def filename():
    return Path(os.environ.get('DATA_DIR', '/data')) / 'rig-3d-page.json'


def load():
    path = filename()
    try:
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError('Unsafe path')
        with path.open('rb') as source:
            raw = source.read(16_385)
        if len(raw) > 16_384:
            raise ValueError('Large configuration')
        return SavedPage.model_validate_json(raw)
    except FileNotFoundError:
        return SavedPage()
    except (OSError, ValueError):
        raise RigError('configuration', 'The 3D test page is not configured.', 503) from None


def public(config):
    return {**config.model_dump(mode='json', exclude={'tenant_id'}),
            'configured': bool(config.publishable_key)}


def write(config, *, create_only=False):
    path = filename()
    try:
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise OSError('Unsafe path')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.rig-3d-', delete=False) as output:
            temporary = Path(output.name)
            try:
                output.write(config.model_dump_json().encode())
                output.flush(); os.fsync(output.fileno())
                if create_only:
                    try:
                        os.link(temporary, path)
                    except FileExistsError:
                        pass
                else:
                    os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    except OSError:
        raise RigError('configuration', 'The settings could not be saved. Try again.', 503) from None


def initialize(tenant):
    require_owner(tenant)
    # Ordinary retailer settings create the day-zero file once. They never
    # overwrite another tenant's display or issue a publishable key implicitly.
    write(SavedPage(tenant_id=tenant), create_only=True)


async def save(service, tenant, config):
    require_owner(tenant)
    previous = load()
    if previous.tenant_id and str(previous.tenant_id) != str(tenant):
        raise RigError('forbidden', 'This store has its own Rig room.', 403)
    # Check old files without stored ownership too, before permitting replacement.
    legacy_key = previous.publishable_key if previous.tenant_id is None else ''
    for key in {legacy_key, config.publishable_key, config.photo_key} - {''}:
        owner = await service.authenticate(key)
        if str(owner['tenant_id']) != str(tenant):
            raise RigError('forbidden', 'This store has its own Rig room.', 403)
    if config.product_id:
        await service.product(tenant, config.product_id)
    saved = SavedPage(**config.model_dump(), tenant_id=tenant)
    write(saved)
    return public(saved)


@router.get('/3d/config', include_in_schema=False)
async def page_config(request: Request):
    config = load()
    if config.publishable_key:
        owner = await _service(request).authenticate(config.publishable_key)
        require_owner(owner['tenant_id'])
        if config.tenant_id and str(owner['tenant_id']) != str(config.tenant_id):
            raise RigError('forbidden', 'This store has its own Rig room.', 403)
    return JSONResponse(public(config), headers={'Cache-Control': 'no-store'})


@router.post('/v1/rig/admin/3d/page')
async def save_page(request: Request, config: PageConfig):
    await _admin(request)
    return JSONResponse(await save(_service(request), _tenant(request), config),
                        headers={'Cache-Control': 'no-store'})
