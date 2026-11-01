"""Disk catalogue loaders for isolated tests only; never packaged in Rig."""
from pathlib import Path
from typing import Any
from uuid import UUID
import json

def load_folder(folder: Path) -> dict[str, Any]:
    from rigbox.catalogue import (read_publish, tenant_id_for, parse_products_csv, parse_fits_csv, parse_market_csv)
    publish_path = folder / "publish.json"
    publish: dict[str, Any] = {}
    publish_error = ""
    if publish_path.is_file():
        try:
            publish = read_publish(publish_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            publish_error = str(exc)
    try:
        tenant_id = tenant_id_for(folder.name, str(publish.get("tenant_id") or "") or None)
    except ValueError:
        tenant_id = ""
        publish_error = publish_error or "tenant_id is not a uuid"
    products_path = folder / "products.csv"
    fits_path = folder / "fits.csv"
    products = parse_products_csv(products_path.read_text(encoding="utf-8")) if products_path.is_file() else {
        "rows": [],
        "rejected": [{"row": 0, "reason": "products.csv is missing"}],
    }
    fits = parse_fits_csv(fits_path.read_text(encoding="utf-8")) if fits_path.is_file() else {
        "rows": [],
        "rejected": [],
    }
    market_path = folder / "market.csv"
    market = parse_market_csv(market_path.read_text(encoding="utf-8")) if market_path.is_file() else None
    return {
        "slug": folder.name,
        "tenant_id": tenant_id,
        "publish": publish,
        "publish_error": publish_error,
        "products": products,
        "fits": fits,
        "market": market,
    }


async def load_catalogue(self, folder: Path) -> dict[str, Any]:
    loaded = load_folder(folder)
    report = await self.import_catalogue(loaded)
    if loaded["tenant_id"] and not loaded["publish_error"]:
        shop = loaded["publish"].get("shop", {})
        if hasattr(self.store, "retailers"):
            self.store.retailers[loaded["tenant_id"]]["shop"] = shop
        else:
            async with self.store.pool.acquire() as conn:
                await conn.execute("UPDATE agent_rig.retailers SET shop=$2::jsonb WHERE tenant_id=$1", UUID(loaded["tenant_id"]), json.dumps(shop))
    return report
