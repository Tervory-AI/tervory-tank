"""Offline browser fixture only; never imported by the production application."""
from pathlib import Path
from fastapi.responses import HTMLResponse
from rigbox.quotes.hosting import mount as mount_widget
from rigbox.three_d.static import ViewerFiles
from .demo import app

mount_widget(app)
ROOT = Path(__file__).resolve().parents[3]


@app.get("/viewer-test")
async def page():
    import json
    manifest = json.loads((ROOT / "agents/rig/rigbox/quotes/widget/manifest.json").read_text())
    return HTMLResponse('''<!doctype html><html><head><style>body{margin:0}</style></head><body>
<tervory-rig theme="custom-nation" fonts="/widget/fonts/custom-nation.css" rig-key="rk_pub_rig5_sample" kiosk-id="00000000-0000-0000-0000-000000003d10"></tervory-rig>
<script src="/widget/assets/''' + manifest['file'] + '''"></script></body></html>''')

# /3d was mounted before this fixture's routes. Replace its static class only.
for route in app.routes:
    if getattr(route, "path", None) == "/3d":
        route.app = ViewerFiles(directory=ROOT / "agents/rig/rigbox/three_d/widget", html=True)
