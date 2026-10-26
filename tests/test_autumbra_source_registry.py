"""Source registry shim: Autumbra does not own a feed list (Market Lab does)."""
from pathlib import Path

from agents.ghost.source_registry import (
    backend_status,
    may_act_on_sources,
    record_track,
    registry_public,
    registry_with_weights,
    sources_accepting_support,
)
from agents.ghost.store import Store


def test_backend_points_at_market_lab(tmp_path: Path):
    assert registry_public() == []
    assert sources_accepting_support() == []
    status = backend_status()
    assert status["owner"] == "Market Lab"
    assert status["autumbra_owns_feed_list"] is False
    assert status["client_visible_feed_list"] is False
    store = Store(tmp_path / "g.sqlite3")
    assert registry_with_weights(store, "00000000-0000-0000-0000-0000000000dd") == []
    ok, why = may_act_on_sources(["cisa_kev"], act_on_single_source=False)
    assert ok is False and "cross-check" in why
    ok, why = may_act_on_sources(["cisa_kev", "urlhaus"], act_on_single_source=False)
    assert ok is True
    record_track(store, "00000000-0000-0000-0000-0000000000dd", "cisa_kev", "first")
