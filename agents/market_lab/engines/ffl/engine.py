"""Supply, demand, and cost series for the firearms case study.

Supply: active licences per area and type from the ATF monthly lists, per
capita (Census population), dealers with a web presence (Base), stock and
price signals (Tiger).

Demand: the founder's per-state licence-application history (uploaded),
monthly FBI NICS background-check counts per state (a demand proxy, not
sales), population growth, and client order data where the client allows it.

Costs: copper, zinc, and lead from FRED, plus freight indices. FRED is read
live and never stored. Saturation is supply density plus competitor activity.
"""

from __future__ import annotations

from typing import Any

# Platform tenant. Scheduled work for this case study lands here until a
# client tenant is named on the job.
PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"

# FRED series ids. The feeds package links these and refuses a database copy.
FRED_COSTS = [
    {"role": "copper", "ref": "PCOPPUSDM", "feeds_id": "fred_pcoppusdm"},
    {"role": "zinc", "ref": "PZINCUSDM", "feeds_id": "fred_pzincusdm"},
    {"role": "lead", "ref": "PLEADUSDM", "feeds_id": "fred_pleadusdm"},
    {"role": "freight", "ref": "TSIFRGHT", "feeds_id": "fred_tsifrght"},
]

SURGE = {"window": 6, "z_threshold": 2.0, "pct_threshold": 0.25}

# Response-rate targets written onto each recommendation, scored 90 days later.
RESPONSE_TARGETS = {"increase": 5.0, "hold": 3.0, "reduce": 1.0}


def plan() -> dict[str, Any]:
    from feeds.catalog import sources

    return {
        "feeds": [source.id for source in sources("ffl") if source.allow_bulk],
        "linked_pages": [source.id for source in sources("ffl") if not source.allow_bulk],
        "engine": "ffl",
        "supply": [
            {
                "source": "listing_counts",
                "prefix": "count:state:",
                "unit": "listings",
                "per_capita": True,
                "note": "Active licences per state from the ATF monthly lists",
            }
        ],
        "demand": [
            {
                "source": "upload",
                "prefix": "applications:",
                "unit": "applications",
                "note": "Founder per-state licence-application history",
            },
            {
                "source": "check_counts",
                "prefix": "total:",
                "unit": "checks",
                "note": "Monthly FBI NICS background-check counts per state",
            },
        ],
        "population": [
            {"source": "census_population", "prefix": "population:state:", "unit": "people"}
        ],
        "costs": [
            {**item, "adapter": "fred", "source": "fred", "store": False, "unit": "index"}
            for item in FRED_COSTS
        ],
        "surge": dict(SURGE),
        "bindings": {
            "supply": [{"source": "listing_counts", "prefix": "count:state:"}],
            "demand": [
                {"source": "upload", "prefix": "applications:"},
                {"source": "check_counts", "prefix": "total:"},
            ],
            "population": [{"source": "census_population", "prefix": "population:state:"}],
            "competitors": [{"source": "competitor", "prefix": "competitors:"}],
        },
        "response_targets": dict(RESPONSE_TARGETS),
    }


def products() -> list[dict[str, Any]]:
    """Where a gap lines up with a product Tervory has or could build."""
    return [
        {"id": "tisan", "when": "no_website", "fit": 0.9, "note": "dealers with no website"},
        {"id": "rig", "when": "web_shop", "fit": 0.8, "note": "dealers with a web shop"},
        {"id": "zenas", "when": "expiring", "fit": 0.7, "note": "licences expiring"},
    ]


def schedules() -> list[dict[str, Any]]:
    """Daily refresh reads FRED live and reloads licence counts. A repeated month is not overwritten. Gaps are recomputed on the first of the month."""
    base = {"tenant_id": PLATFORM_TENANT, "input": {"engine": "ffl"}}
    return [
        {**base, "cron": "20 6 * * *", "kind": "refresh"},
        {**base, "cron": "40 6 1 * *", "kind": "opportunities"},
        {**base, "cron": "10 7 * * *", "kind": "resolve"},
    ]
