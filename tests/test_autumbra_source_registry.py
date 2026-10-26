"""Source registry: free first entries, cross-check, credits, weights."""
from pathlib import Path

from agents.ghost.source_registry import (
    credit_for,
    may_act_on_sources,
    record_track,
    registry_public,
    registry_with_weights,
    sources_accepting_support,
)
from agents.ghost.store import Store


REQUIRED = {
    "ransomware_live", "ransomlook", "ransomwatch", "urlhaus", "threatfox", "feodo",
    "malwarebazaar", "spamhaus_drop", "shadowserver", "tor_exits", "cisa_kev", "osv",
    "ghsa", "nvd", "hibp_domain", "researcher_leads",
}


def test_registry_first_entries_present():
    ids = {s["id"] for s in registry_public()}
    assert REQUIRED <= ids
    for src in registry_public():
        assert src["free"] is True
        assert "credit" in src and "licence" in src


def test_cross_check_and_leads_alone():
    ok, why = may_act_on_sources(["cisa_kev"], act_on_single_source=False)
    assert ok is False and "cross-check" in why
    ok, why = may_act_on_sources(["cisa_kev", "osv"], act_on_single_source=False)
    assert ok is True
    ok, why = may_act_on_sources(["researcher_leads"], act_on_single_source=True)
    assert ok is False and "alone" in why


def test_credits_and_weights(tmp_path: Path):
    credits = credit_for(["cisa_kev", "urlhaus"])
    assert {c["id"] for c in credits} == {"cisa_kev", "urlhaus"}
    store = Store(tmp_path / "g.sqlite3")
    tenant = "00000000-0000-0000-0000-0000000000dd"
    record_track(store, tenant, "cisa_kev", "first")
    record_track(store, tenant, "cisa_kev", "confirmed")
    rows = registry_with_weights(store, tenant)
    kev = next(r for r in rows if r["id"] == "cisa_kev")
    assert kev["track"] == {"first": 1, "confirmed": 1, "wrong": 0}
    assert sources_accepting_support()
