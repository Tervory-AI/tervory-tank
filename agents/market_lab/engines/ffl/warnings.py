"""First shipping chains and the market words; statistics live in core."""

from typing import Any
import hashlib


def plan() -> dict[str, Any]:
    return {
        "signals": [
            {
                "source": "port_los_angeles",
                "ref": "teu",
                "label": "Port of Los Angeles container volume",
            },
            {"source": "bts_freight", "ref": "tsifrght", "label": "Freight volume"},
            {"source": "eia_diesel", "label": "Diesel prices"},
            {
                "source": "noaa_alerts",
                "label": "Severe weather notices",
                "kind": "notice",
            },
            {"source": "legiscan", "label": "Legislation", "kind": "notice"},
            {"source": "world_bank_commodities", "label": "Commodity prices"},
        ],
        "outcomes": [
            {"source": "listing_counts", "label": "Licence counts"},
            {
                "source": "check_counts",
                "label": "Background-check counts",
                "note": "These are not sales.",
            },
            {"source": "tiger_price", "label": "Watched product prices"},
            {"source": "tiger_stock", "label": "Watched product availability"},
        ],
        # First chain only. No causal claim is inferred from a past association.
        "pairs": [
            {
                "id": f"{source}:availability",
                "source": source,
                "ref": ref,
                "label": label,
                "downstream_source": "tiger_stock",
                "direction": "drop",
                "outcome_direction": "drop",
                "baseline_value": 2,
                "outcome_pct": 0.25,
                "outcome_words": "became unavailable",
                "prediction_words": "may become unavailable",
                "min_episodes": 3,
                "window": 6,
                "z_threshold": 2.0,
                "pct_threshold": 0.15,
                "min_lag_days": 7,
                "max_lag_days": 84,
                "max_gap_days": 14,
            }
            for source, ref, label in [
                ("port_los_angeles", "teu", "Port of Los Angeles container volume"),
                ("bts_freight", "tsifrght", "Freight volume"),
            ]
        ],
    }


def product_series(watch: dict, observations: list[dict]) -> list[dict]:
    """Tiger's recorded product name is the subject; never invent a category."""
    if watch.get("engine") not in {"", "ffl"}:
        return []
    named = [row for row in observations if str(row.get("product_name") or "").strip()]
    if not named:
        return []
    name = str(max(named, key=lambda row: str(row.get("ts")))["product_name"])
    common = {
        "ref": str(watch["id"]) + ":" + hashlib.sha256(name.encode()).hexdigest()[:16],
        "name": name,
        "url": watch["url"],
        "geo": "US",
        "geo_level": "national",
    }
    stock, prices = [], {}
    for row in sorted(observations, key=lambda row: str(row.get("ts"))):
        if row.get("product_name") != name:
            continue  # A changed product page must not mix two products into one history.
        availability = (
            str(row.get("availability") or "")
            .rsplit("/", 1)[-1]
            .lower()
            .replace("-", "")
            .replace(" ", "")
            .replace("_", "")
        )
        if availability in {"instock", "outofstock"}:
            stock.append(
                {
                    "date": str(row["ts"])[:10],
                    "value": "2" if availability == "instock" else "1",
                    "display_value": "Available"
                    if availability == "instock"
                    else "Unavailable",
                    "observation_id": str(row["id"]),
                }
            )
        if row.get("price") is not None and row.get("currency"):
            prices.setdefault(str(row["currency"]), []).append(
                {
                    "date": str(row["ts"])[:10],
                    "value": str(row["price"]),
                    "observation_id": str(row["id"]),
                }
            )
    result = []
    if stock:
        result.append(
            {
                **common,
                "source": "tiger_stock",
                "unit": "availability",
                "currency": "none",
                "title": f"Availability of {name}",
                "explanation": "Saved product-page availability. Calculations encode available as 2 and unavailable as 1; these are status labels, not stock quantities.",
                "points": stock,
            }
        )
    for currency, points in prices.items():
        result.append(
            {
                **common,
                "ref": common["ref"] + ":" + currency,
                "source": "tiger_price",
                "unit": currency,
                "currency": currency,
                "title": f"Price of {name}",
                "points": points,
            }
        )
    return result
