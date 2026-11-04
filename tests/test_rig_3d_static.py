"""Only public code modules get anonymous cross-origin embed access."""
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/rig'))
from rigbox.three_d.static import ViewerFiles  # noqa: E402


@pytest.mark.asyncio
async def test_public_viewer_modules_allow_embed_imports_but_not_model_files(tmp_path):
    (tmp_path / 'widget-entry.js').write_text('export const fixture = true;')
    (tmp_path / 'model.glb').write_bytes(b'fixture')
    app = FastAPI()
    app.mount('/3d', ViewerFiles(directory=tmp_path))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture.test') as client:
        code = await client.get('/3d/widget-entry.js', headers={'Origin': 'https://store.test'})
        assert code.headers['access-control-allow-origin'] == '*'
        assert code.headers['x-content-type-options'] == 'nosniff'
        model = await client.get('/3d/model.glb')
        assert 'access-control-allow-origin' not in model.headers
        assert (await client.get('/3d/../secret')).status_code == 404
