"""One box, one region. The loader never reads or writes the other region's law."""

from __future__ import annotations

from agents.zenas.pool.licence import PoolError
from agents.zenas.pool.model import SourceSpec


class RegionError(PoolError):
    """This deployment will not touch a source that belongs to another region."""


def assert_source_region(source: SourceSpec, region: str) -> None:
    """Refuse before any fetch, parse, or write."""
    if source.region != region:
        raise RegionError(
            f"refusing {source.source_id}: it belongs to {source.region}, and this box is {region}"
        )
