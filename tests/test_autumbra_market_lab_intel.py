"""Autumbra consumes Market Lab IOC bundles — no Autumbra-owned feed registry."""
import pytest

from agents.ghost.market_lab_intel import (
    accept_ioc_bundle,
    receipt_for_bundle_consume,
    source_credits_on_receipt,
)
from agents.ghost.source_registry import backend_status, registry_public


def _bundle(**extra):
    base = {
        "schema_version": "market_lab.ioc.v1",
        "bundle_id": "ml-fixture-1",
        "paid": False,
        "sources": [
            {"id": "urlhaus", "name": "abuse.ch URLhaus", "credit": "abuse.ch URLhaus",
             "url": "https://urlhaus.abuse.ch"},
            {"id": "cisa_kev", "name": "CISA KEV", "credit": "CISA KEV",
             "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"},
        ],
        "indicators": [
            {"kind": "ip", "value": "203.0.113.44", "source_ids": ["urlhaus"]},
        ],
    }
    base.update(extra)
    return base


def test_accept_public_bundle_and_credit_on_receipt():
    bundle = accept_ioc_bundle(_bundle())
    assert bundle["producer"] == "Market Lab"
    credits = source_credits_on_receipt(bundle, source_ids=["urlhaus"])
    assert credits[0]["via"] == "Market Lab"
    assert credits[0]["credit"] == "abuse.ch URLhaus"
    receipt = receipt_for_bundle_consume(bundle, tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert receipt["client_visible_feed_list"] is False
    assert receipt["sources"]


def test_reject_paid_and_forbidden_sources():
    with pytest.raises(ValueError, match="paid"):
        accept_ioc_bundle(_bundle(paid=True))
    with pytest.raises(ValueError, match="YouTube|Instagram"):
        accept_ioc_bundle(_bundle(sources=[{"id": "youtube", "name": "YouTube"}]))


def test_autumbra_does_not_own_feed_list():
    assert registry_public() == []
    status = backend_status()
    assert status["autumbra_owns_feed_list"] is False
    assert status["owner"] == "Market Lab"
