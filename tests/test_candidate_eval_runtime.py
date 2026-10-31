"""Live eval regressions: platform identity and Tank's actual shipped files."""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tank/skills/market.series_fetch/1.0.0"
PACKAGE = max((ROOT / "tank/skills/market.series_fetch").glob("*/skill.yaml"),
              key=lambda path: tuple(map(int, path.parent.name.split(".")))).parent


def platform_tenant() -> str:
    # Main and Skala share Gold's constant; avoid importing the server or DB.
    tree = ast.parse((ROOT / "tank/gold.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PLATFORM_TENANT" for t in node.targets):
            return ast.literal_eval(node.value.args[0])
    raise AssertionError("Tank's PLATFORM_TENANT assignment was not found")


# A fresh interpreter prevents repository feeds imports and cached skill
# modules from concealing a missing production dependency. Only /app contents
# shipped by Tank's Dockerfile are available to the evals.
ISOLATED_EVALS = r'''
import asyncio
import json
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch
from uuid import UUID

root = Path.cwd()
sys.path.insert(0, str(root))
import skala

class NoHttp:
    def __getattr__(self, name):
        raise AssertionError("Evals must not access HTTP")

async def no_model(**kwargs):
    raise AssertionError("Evals must not call a model")

async def main():
    assert not (root / "agents").exists()
    assert not (root / "tests").exists()
    os.environ["TANK_REGION"] = "us-east"
    packages = skala.load_packages(root / "skills")
    names = ["radix.verify_business", "radix.entity_links", "radix.account_links",
             "radix.site_risk", "radix.business_risk", "market.series_fetch"]
    summaries = {}
    version = sys.argv[2]
    with patch("socket.socket", side_effect=AssertionError("Evals must stay offline")):
        for name in names:
            pkg = packages[(name, version if name == "market.series_fetch" else "1.0.0")]
            contexts = []
            def context():
                ctx = skala.SkillContext(tenant_id=UUID(sys.argv[1]), skill_ref=pkg.ref,
                    agent=pkg.agent, task_id=None, _model=no_model, http=NoHttp(), env={})
                contexts.append(ctx)
                return ctx
            result = await skala.run_evals(pkg, context)
            expected = {"1.0.0": 3, "1.2.0": 7}.get(version, 10) if name == "market.series_fetch" else 7
            assert result["total"] == expected, result
            assert result["passed"] == expected and result["score"] == 1.0, result
            assert all(ctx.calls == 0 and ctx.cost_usd == 0 for ctx in contexts)
            summaries[name] = {"passed": result["passed"], "total": result["total"]}
            if name == "market.series_fetch":
                listing = next(case for case in result["details"] if case["name"] == "monthly listing counts")
                assert listing["result"]["points"] == [
                    {"date": "2024-01-01", "value": 3.0},
                    {"date": "2024-02-01", "value": 2.0}], listing
        package = root / "skills/market.series_fetch" / version
        if version != "1.0.0":
            cases = runpy.run_path(str(package / "evals/feed_cases.py"))
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(cases["BundledFeedCases"])
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            assert result.wasSuccessful() and result.testsRun == 10
            summaries["bundled_feed_cases"] = {"passed": result.testsRun, "total": result.testsRun}
        for name, module in list(sys.modules.items()):
            if name == "feeds" or name.startswith("feeds."):
                assert Path(module.__file__).is_relative_to(package / "feeds"), name
    print(json.dumps(summaries))

asyncio.run(main())
'''


class CandidateEvalRuntimeTests(unittest.TestCase):
    def test_every_package_case_has_the_gold_startup_import_shape(self):
        import skala

        for pkg in skala.load_packages(ROOT / "tank/skills").values():
            for case in pkg.cases:
                with self.subTest(package=pkg.ref, case=case.get("name")):
                    self.assertIsInstance(case["input"], dict)
                    if "expected" not in case:
                        # gold.import_packages skips refusal cases (expected_error only);
                        # Skala scores them as must_refuse checks.
                        self.assertIs(case.get("must_refuse"), True)
                        self.assertIsInstance(case.get("expected_error"), dict)
                        continue
                    self.assertIsInstance(case["expected"], dict)
        cases = [json.loads(line) for line in (PACKAGE / "evals/cases.jsonl").read_text().splitlines()]
        self.assertTrue(all("expected_error" not in case for case in cases))

    def test_newest_package_preserves_every_latest_baseline_case_hash(self):
        import skala

        packages = skala.load_packages(ROOT / "tank/skills")
        baseline = packages[("market.series_fetch", "1.1.1")]
        candidate = packages[("market.series_fetch", PACKAGE.name)]
        self.assertEqual(len(baseline.cases), 5)
        self.assertIn("decimal CSV observation", {case["name"] for case in baseline.cases})
        # Approval compares the entire case, including JSON number types.
        previous = {skala.evidence_hash(case) for case in baseline.cases}
        current = {skala.evidence_hash(case) for case in candidate.cases}
        self.assertEqual(previous - current, set())
        # 1.2.0 added two cases; 1.2.1 also carries Boston's approved 1.1.0 lines verbatim.
        self.assertEqual(len(current - previous), 5)
        approved = {skala.evidence_hash(case) for case in packages[("market.series_fetch", "1.1.0")].cases}
        self.assertEqual(approved - current, set())

    def test_radix_eval_rows_and_source_links_all_use_platform_tenant(self):
        tenant = platform_tenant()
        files = sorted((ROOT / "tank/skills").glob("radix.*/1.0.0/evals/cases.jsonl"))
        self.assertEqual(len(files), 5)
        for path in files:
            cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            self.assertEqual(len(cases), 7)
            for case in cases:
                data = case["input"]
                self.assertEqual(data["tenant_id"], tenant)
                for rows in (data["sources"], data["businesses"], data["accounts"]):
                    self.assertTrue(all(row["tenant_id"] == tenant for row in rows))
                for source in data["sources"]:
                    if source["url"].startswith("client://"):
                        self.assertTrue(source["url"].startswith(f"client://{tenant}/"))
                self.assertNotIn("10000000-0000-0000-0000-000000000001", json.dumps(case))

    def test_one_oh_oh_stays_free_of_the_batch_guard(self):
        files = [p for p in (LEGACY / "feeds").rglob("*") if p.is_file() and p.suffix in {".py", ".sql"}]
        self.assertEqual(len(files), 19)
        self.assertFalse((LEGACY / "feeds" / "batch_guard.py").exists())
        self.assertNotIn("batch_guard", (LEGACY / "feeds" / "store.py").read_text(encoding="utf-8"))
        self.assertIn("version: 1.0.0", (LEGACY / "skill.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("1.1.0", (LEGACY / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_bundled_feeds_and_fixtures_match_existing_sources(self):
        self.assertIn(f"version: {PACKAGE.name}", (PACKAGE / "skill.yaml").read_text(encoding="utf-8"))
        files = [p for p in (PACKAGE / "feeds").rglob("*") if p.is_file() and p.suffix in {".py", ".sql"}]
        self.assertEqual(len(files), 21)
        self.assertTrue((PACKAGE / "feeds/published.py").is_file())
        for path in files:
            original = ROOT / "agents/market_lab/feeds" / path.relative_to(PACKAGE / "feeds")
            self.assertEqual(path.read_bytes(), original.read_bytes(), str(path))
        fixtures = [p for p in (PACKAGE / "tests/fixtures/feeds").rglob("*") if p.is_file()]
        self.assertEqual(len(fixtures), 3)
        for path in fixtures:
            original = ROOT / "tests/fixtures/feeds" / path.relative_to(PACKAGE / "tests/fixtures/feeds")
            self.assertEqual(path.read_bytes(), original.read_bytes(), str(path))

    def test_real_eval_runner_in_tank_only_process(self):
        report = self.run_isolated("1.0.0")
        self.assertEqual(len(report), 6)
        self.assertEqual(report["market.series_fetch"], {"passed": 3, "total": 3})

    def test_newest_eval_runner_and_feed_cases_in_tank_only_process(self):
        report = self.run_isolated(PACKAGE.name)
        self.assertEqual(len(report), 7)
        self.assertEqual(report["market.series_fetch"], {"passed": 10, "total": 10})
        self.assertEqual(report["bundled_feed_cases"], {"passed": 10, "total": 10})

    def run_isolated(self, version):
        with tempfile.TemporaryDirectory(prefix="tank-eval-runtime-") as folder:
            app = Path(folder)
            # These copies match Tank's Dockerfile: top-level modules + skills.
            for path in (ROOT / "tank").glob("*.py"):
                shutil.copyfile(path, app / path.name)
            shutil.copytree(ROOT / "tank/skills", app / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            for name in ("PYTHONPATH", "SKILLS_DIR", "RADIX_SOURCE_CIPC_KEY", "RADIX_SOURCE_REGISTER_KEY", "FRED_API_KEY"):
                env.pop(name, None)
            result = subprocess.run([sys.executable, "-I", "-c", ISOLATED_EVALS, platform_tenant(), version],
                                    cwd=app, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
