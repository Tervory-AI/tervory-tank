"""RX-5 contract tests. Also runnable offline with stdlib unittest."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "tank" / "skills"
sys.path.insert(0, str(ROOT / "tank"))
import skala  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ENGINE = load_module("radix_business_engine_v1", SKILL_ROOT / "radix.shared" / "engine_v1.py")
OTHER = "10000000-0000-0000-0000-000000000002"


def fixture() -> dict:
    return json.loads((ROOT / "tests" / "fixtures" / "rx5" / "businesses.json").read_text())


def evaluate(skill="business_risk", payload=None, tenant=None, env=None):
    payload = payload if payload is not None else fixture()
    return ENGINE.analyse(skill, payload, tenant or payload["tenant_id"], env)


class BusinessEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def test_official_fixture_verifies_with_sources(self):
        result = evaluate("verify_business")
        self.assertTrue(result["ok"])
        self.assertEqual(result["verification"], "verified_from_supplied_register")
        self.assertEqual(result["fields"]["domain_age_days"]["value"], 18)
        self.assertEqual(result["fields"]["licence_status"]["value"], "active")
        self.assertEqual(result["fields"]["officers"]["value"], ["Example Published Officer"])
        for field in result["fields"].values():
            self.assertTrue(field["sources"])
            self.assertTrue(all(s["url"] and s["retrieved_at"] and len(s["evidence_sha256"]) == 64 for s in field["sources"]))

    def test_company_address_and_agent_links_use_both_records(self):
        result = evaluate("entity_links")
        self.assertEqual(len(result["links"]), 1)
        link = result["links"][0]
        self.assertTrue({"registered_address", "registered_agent"} <= set(link["shared_fields"]))
        self.assertTrue(link["newly_formed_cluster"])
        self.assertEqual(set(link["business_ids"]), {s["record_id"] for s in link["finding"]["sources"]})

    def test_banned_seller_link_requires_client_business_evidence(self):
        link = evaluate("account_links")["links"][0]
        self.assertTrue(link["possible_returning_operation"])
        self.assertIn("payout_business_name", link["shared_fields"])
        statuses = [s for s in link["finding"]["sources"] if s["field"] == "status"]
        self.assertEqual(len(statuses), 2)
        self.assertEqual(set(link["account_ids"]), {s["record_id"] for s in statuses})
        payload = fixture()
        payload["accounts"][0]["status"]["source_ids"] = ["register"]
        self.assertFalse(evaluate("account_links", payload)["ok"])

    def test_site_observations_and_lookalike_have_sources(self):
        payload = fixture()
        payload["lookup"]["value"] = payload["businesses"][1]["id"]
        result = evaluate("site_risk", payload)
        findings = {f["code"]: f for f in result["findings"]}
        self.assertEqual(set(findings), {"privacy_notice", "cookie_notice", "exposed_admin", "new_domain", "lookalike_domain"})
        self.assertEqual({s["field"] for s in findings["lookalike_domain"]["sources"]}, {"domain", "brand_domain"})
        for find in findings.values():
            self.assertTrue(find["sources"])
        payload["businesses"][1]["facts"]["domain"]["value"] = "shop.acme-tools.example"
        self.assertNotIn("lookalike_domain", [f["code"] for f in evaluate("site_risk", payload)["findings"]])

    def test_score_is_deterministic_bounded_and_all_factors_are_sourced(self):
        payload = fixture()
        payload["lookup"]["value"] = payload["businesses"][1]["id"]
        first = evaluate(payload=payload)
        second = evaluate(payload=copy.deepcopy(payload))
        self.assertEqual(first, second)
        self.assertEqual(first["score"], 95)
        self.assertEqual(first["score"], min(100, sum(f["weight"] for f in first["factors"])))
        self.assertTrue(all(f["sources"] for f in first["factors"]))
        payload["businesses"][1]["facts"]["status"]["value"] = "inactive"
        self.assertEqual(evaluate(payload=payload)["score"], 100)

    def test_missing_evidence_never_becomes_a_finding_or_a_safe_verdict(self):
        payload = fixture()
        payload["businesses"][0]["facts"] = {}
        payload["accounts"] = []
        out = evaluate(payload=payload)
        self.assertTrue(out["ok"])
        self.assertEqual(out["score"], 0)
        self.assertEqual(out["factors"], [])
        self.assertEqual(out["status"], "incomplete")
        self.assertIn("status", out["unknown"])
        self.assertEqual(evaluate("verify_business", payload)["verification"], "unknown")

    async def test_no_skill_accepts_person_name_email_or_phone_as_any_lookup_key(self):
        packages = skala.load_packages(SKILL_ROOT)
        values = ("Jane Example", "jane@example.test", "+27 82 555 0100", "0825550100", "+1 (202) 555-0199")
        kinds = ("person_name", "name", "email", "phone", "phone_number", "business_id", "company_name", "domain", "registration_number", "licence_number")
        with patch.dict(os.environ, {"TANK_REGION": "us-east"}):
            for skill in ENGINE.SKILLS:
                pkg = packages[("radix." + skill, "1.0.0")]
                for kind in kinds:
                    for value in values:
                        with self.subTest(skill=skill, kind=kind, value=value):
                            payload = fixture()
                            payload["lookup"] = {"kind": kind, "value": value}
                            ctx = SimpleNamespace(tenant_id=payload["tenant_id"], env={}, http=AsyncMock(), model=AsyncMock())
                            with patch("socket.socket", side_effect=AssertionError("No outbound sockets")):
                                result = await skala.run_skill(pkg, payload, ctx)
                            self.assertFalse(result["ok"])
                            self.assertEqual(result["error"], "invalid_business_evidence")
                            self.assertNotIn(value, json.dumps(result))
                            self.assertEqual(ctx.http.mock_calls, [])
                            self.assertEqual(ctx.model.mock_calls, [])

    async def test_all_five_real_packages_and_evals_are_offline(self):
        packages = skala.load_packages(SKILL_ROOT)
        with patch.dict(os.environ, {"TANK_REGION": "us-east"}):
            for skill in ENGINE.SKILLS:
                pkg = packages[("radix." + skill, "1.0.0")]
                self.assertEqual(pkg.rung, 3)
                self.assertEqual(pkg.input_schema, ENGINE.Request.model_json_schema())
                for case in pkg.cases:
                    ctx = SimpleNamespace(tenant_id=fixture()["tenant_id"], env={}, http=AsyncMock(), model=AsyncMock())
                    with patch("socket.socket", side_effect=AssertionError("No outbound sockets")):
                        output = await skala.run_skill(pkg, case["input"], ctx)
                    self.assertTrue(skala.score_case(case["expected"], output, case["tolerance"])[0], (skill, case["name"]))
                    self.assertEqual(ctx.http.mock_calls, [])
                    self.assertEqual(ctx.model.mock_calls, [])

    def test_tenant_crossovers_reject_before_analysis(self):
        for kind in ("sources", "businesses", "accounts"):
            for skill in ENGINE.SKILLS:
                with self.subTest(kind=kind, skill=skill):
                    payload = fixture()
                    payload[kind][0]["tenant_id"] = OTHER
                    self.assertFalse(evaluate(skill, payload)["ok"])
        for skill in ENGINE.SKILLS:
            self.assertFalse(evaluate(skill, tenant=OTHER)["ok"])
        payload = fixture()
        payload["sources"][0]["url"] = f"client://{OTHER}/secret"
        self.assertFalse(evaluate(payload=payload)["ok"])

    async def test_server_region_is_binding_and_cipc_is_za_only(self):
        payload = fixture()
        payload["sources"][0]["kind"] = "cipc"
        self.assertFalse(evaluate(payload=payload)["ok"])
        payload["region"] = "za"
        for source in payload["sources"]:
            source["region"] = "za"
        ctx = SimpleNamespace(tenant_id=payload["tenant_id"], env={})
        with patch.dict(os.environ, {"TANK_REGION": "us-east"}):
            self.assertFalse((await ENGINE.run("verify_business", payload, ctx))["ok"])
        with patch.dict(os.environ, {"TANK_REGION": "za"}):
            self.assertTrue((await ENGINE.run("verify_business", payload, ctx))["ok"])

    def test_keys_are_read_by_name_skipped_until_set_and_never_returned(self):
        payload = fixture()
        payload["sources"][0]["key_env"] = "RADIX_SOURCE_REGISTER_KEY"
        result = evaluate("verify_business", payload)
        self.assertEqual(result["verification"], "unknown")
        self.assertEqual(result["skipped_sources"][0]["reason"], "key_not_set")
        secret = "example-test-value-never-returned"
        result = evaluate("verify_business", payload, env={"RADIX_SOURCE_REGISTER_KEY": secret})
        self.assertEqual(result["verification"], "verified_from_supplied_register")
        self.assertNotIn(secret, json.dumps(result))
        payload["sources"][0]["key_env"] = "TANK_API_KEY"
        self.assertFalse(evaluate(payload=payload)["ok"])

    def test_unknown_ambiguous_keys_and_valid_business_selectors(self):
        original = fixture()
        for kind in ("company_name", "registration_number", "domain", "licence_number"):
            payload = fixture()
            payload["lookup"] = {"kind": kind, "value": payload["businesses"][0]["facts"][kind]["value"]}
            self.assertEqual(evaluate("verify_business", payload)["business_id"], original["businesses"][0]["id"])
        payload["lookup"] = {"kind": "business_id", "value": OTHER}
        self.assertEqual(evaluate(payload=payload)["status"], "unknown")
        payload["lookup"] = {"kind": "company_name", "value": "Acme Tools LLC"}
        payload["businesses"][1]["facts"]["company_name"]["value"] = "Acme Tools LLC"
        out = evaluate(payload=payload)
        self.assertEqual(out["status"], "ambiguous")
        self.assertIsNone(out["score"])

    def test_person_fields_bad_evidence_and_invented_sources_are_refused(self):
        changes = [
            lambda p: p["businesses"][0]["facts"].update(person_email={"value": "jane@example.test", "source_ids": ["platform"]}),
            lambda p: p["businesses"][0]["facts"]["owner_organisation"].update(value="Jane Example"),
            lambda p: p["businesses"][0]["facts"]["officers"].update(source_ids=["platform"]),
            lambda p: p["businesses"][0]["facts"]["status"].update(source_ids=["site"]),
            lambda p: p["businesses"][0]["facts"]["domain"].update(source_ids=["invented"]),
            lambda p: p["businesses"][0]["facts"]["domain"].update(source_ids=[]),
            lambda p: p["businesses"][0]["facts"]["domain_created_on"].update(value="2027-10-19"),
            lambda p: p["accounts"][0].update(email="jane@example.test"),
            lambda p: p["accounts"][0]["payout_business_name"].update(value="Jane Example"),
            lambda p: p["sources"][0].update(url="https://example.test/?token=example"),
            lambda p: p["sources"][0].update(retrieved_at="2027-10-19T10:00:00Z"),
            lambda p: p["sources"].append(copy.deepcopy(p["sources"][0])),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                payload = fixture()
                change(payload)
                self.assertFalse(evaluate(payload=payload)["ok"])

    def test_base_export_reuse_omits_contact_fields_and_preserves_record_source(self):
        payload = fixture()
        bid = payload["businesses"][0]["id"]
        payload["businesses"].pop(0)
        payload["accounts"] = []
        item = {"tenant_id": payload["tenant_id"], "record": {"id": bid,
            "profile": {"licence_number": {"value": "123456000001", "source": "registry:ffl", "confidence": 100},
                        "name": {"value": "Acme Tools LLC", "source": "input", "confidence": 95},
                        "emails": {"value": ["personal@example.test"], "source": "input"}},
            "raw": {"registration_number": "US-DE:123456", "licence_status": "active", "contact_name": "Jane Example"}},
            "bindings": {"company_name": {"path": "profile.name", "source_ids": ["register"]},
                         "licence_number": {"path": "profile.licence_number", "source_ids": ["licence"], "issuer": "US-ATF"},
                         "licence_status": {"path": "raw.licence_status", "source_ids": ["licence"]}}}
        payload["base_imports"] = [item]
        result = evaluate("verify_business", payload)
        self.assertTrue(result["ok"])
        field = result["fields"]["licence_number"]
        self.assertEqual(field["value"], "US-ATF:123456000001")
        self.assertEqual(field["sources"][0]["base_record_id"], bid)
        self.assertNotIn("personal@example.test", json.dumps(result))
        self.assertNotIn("Jane Example", json.dumps(result))
        item["bindings"]["company_name"]["path"] = "raw.contact_name"
        self.assertFalse(evaluate("verify_business", payload)["ok"])
        item["record"]["tenant_id"] = OTHER
        self.assertFalse(evaluate("verify_business", payload)["ok"])

    def test_licence_penalty_deduplicates_and_unrelated_entities_do_not_link(self):
        payload = fixture()
        facts = payload["businesses"][0]["facts"]
        facts["licence_status"]["value"] = "expired"
        facts["licence_expires_on"]["value"] = "2026-01-01"
        out = evaluate(payload=payload)
        self.assertEqual([f["code"] for f in out["factors"] if f["code"].startswith("licence")], ["licence_not_active"])
        payload["businesses"][1]["facts"] = {}
        payload["accounts"] = []
        self.assertEqual(evaluate("entity_links", payload)["links"], [])
