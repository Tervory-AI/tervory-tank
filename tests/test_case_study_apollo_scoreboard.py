"""Invented evidence stays offline; exercise the actual case-study reader."""
from datetime import UTC, date, datetime
import uuid

import pytest

from base_evidence import FIELDS
from case_study_sources import base
from case_study_templates import empty_figures

AT = datetime(2026, 10, 2, tzinfo=UTC)
A, B = uuid.UUID(int=1), uuid.UUID(int=2)
START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 4, tzinfo=UTC)


def record(key, website):
    fields = {name: {"value": None, "verified": False} for name in FIELDS}
    fields["website"] = {"value": website, "verified": bool(website)}
    return {"record_id": uuid.uuid4(), "licence_key": key, "state": "CA",
            "licence_type": "01", "status": "done", "checked_at": AT, "fields": fields}


class Store:
    def __init__(self, imports):
        self.imports = imports
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        assert args[0] in (A, B)
        if "FROM tank.base_apollo_records" in sql:
            assert "r.tenant_id=$1" in sql and "i.tenant_id=$1" in sql
            assert "i.imported_at >= $2 AND i.imported_at < $3" in sql
            assert args[1:] == (START, END)
            return self.imports.get(args[0], [])
        # Snapshot evidence must work without current-period result rows.
        return []

    async def fetchval(self, sql, *args):
        return False


async def figures(store, tenant):
    result = empty_figures("base", date(2026, 10, 1), date(2026, 10, 3))
    await base(store, tenant, "us-east", START, END, result)
    return result


@pytest.mark.asyncio
async def test_scoreboard_is_tenant_scoped_and_reuses_saved_snapshots():
    rows = []
    for key, left, right in (("match", "same.example", "same.example"),
                             ("base", "base.example", None),
                             ("apollo", None, "apollo.example"),
                             ("different", "left.example", "right.example"),
                             ("neither", None, None)):
        rows.append({"licence_key": key, "base_snapshot": record(key, left),
                     "fields": {"website": right}})
    store = Store({A: rows})
    values = await figures(store, A)
    for outcome in ("matches", "base_only", "apollo_only", "disagreements", "neither"):
        item = values[f"base.vs_apollo.website.{outcome}"]
        assert item["value"] == 1
        assert item["source"] == "base_metrics.compare"
    for field in ("website", "phone", "email"):
        assert values[f"base.vs_apollo.{field}.records_compared"]["value"] == 5
    assert values["base.vs_apollo.phone.neither"]["value"] == 5
    coverage = values["base.vs_apollo.coverage"]
    assert coverage["value"] == .6
    assert coverage["base_verified"] == 3
    assert coverage["apollo_returned"] == 5
    other = await figures(store, B)
    assert all(item["value"] == 0 for name, item in other.items() if name.startswith("base.vs_apollo."))


@pytest.mark.asyncio
async def test_missing_comparison_has_zero_outcomes_and_coverage():
    values = await figures(Store({}), A)
    scoreboard = {name: item for name, item in values.items() if name.startswith("base.vs_apollo.")}
    assert len(scoreboard) == 19
    assert all(item["value"] == 0 for item in scoreboard.values())
    assert scoreboard["base.vs_apollo.coverage"]["apollo_returned"] == 0


@pytest.mark.asyncio
async def test_additional_comparison_fields_are_included(monkeypatch):
    import case_study_sources
    original = case_study_sources.compare

    def extended(results, apollo):
        result = original(results, apollo)
        for state in result["states"]:
            state["additional_field"] = {"matches": state["records"]}
        return result

    monkeypatch.setattr(case_study_sources, "compare", extended)
    snapshot = record("one", "one.example")
    values = await figures(Store({A: [{"licence_key": "one", "base_snapshot": snapshot,
                                      "fields": {"website": "one.example"}}]}), A)
    assert values["base.vs_apollo.additional_field.matches"]["value"] == 1
    assert values["base.vs_apollo.additional_field.records_compared"]["value"] == 1
    assert values["base.vs_apollo.additional_field.neither"]["value"] == 0
