"""Autumbra does not own a feed list — Market Lab does."""
from agents.ghost.market_lab_intel import backend_status


def test_backend_points_at_market_lab():
    status = backend_status()
    assert status["owner"] == "Market Lab"
    assert status["autumbra_owns_feed_list"] is False
    assert status["client_visible_feed_list"] is False
