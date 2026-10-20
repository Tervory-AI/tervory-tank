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
PACKAGE = ROOT / "tank/skills/market.series_fetch/1.0.0"


def platform_tenant() -> str:
    # Read the authoritative constant without importing Tank's server or DB.
    tree = ast.parse((ROOT / "tank/main.py").read_text())
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
import sys
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
    with patch("socket.socket", side_effect=AssertionError("Evals must stay offline")):
        for name in names:
            pkg = packages[(name, "1.0.0")]
            contexts = []
            def context():
                ctx = skala.SkillContext(tenant_id=UUID(sys.argv[1]), skill_ref=pkg.ref,
                    agent=pkg.agent, task_id=None, _model=no_model, http=NoHttp(), env={})
                contexts.append(ctx)
                return ctx
            result = await skala.run_evals(pkg, context)
            expected = 3 if name == "market.series_fetch" else 7
            assert result["total"] == expected, result
            assert result["passed"] == expected and result["score"] == 1.0, result
            assert all(ctx.calls == 0 and ctx.cost_usd == 0 for ctx in contexts)
            summaries[name] = {"passed": result["passed"], "total": result["total"]}
            if name == "market.series_fetch":
                listing = next(case for case in result["details"] if case["name"] == "monthly listing counts")
                assert listing["result"]["points"] == [
                    {"date": "2024-01-01", "value": 3.0},
                    {"date": "2024-02-01", "value": 2.0}], listing
    assert Path(sys.modules["feeds"].__file__).is_relative_to(root / "skills/market.series_fetch/1.0.0")
    print(json.dumps(summaries))

asyncio.run(main())
'''


class CandidateEvalRuntimeTests(unittest.TestCase):
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

    def test_bundled_feeds_and_fixtures_match_existing_sources(self):
        files = [p for p in (PACKAGE / "feeds").rglob("*") if p.is_file() and p.suffix in {".py", ".sql"}]
        self.assertEqual(len(files), 20)
        for path in files:
            original = ROOT / "agents/market_lab/feeds" / path.relative_to(PACKAGE / "feeds")
            self.assertEqual(path.read_bytes(), original.read_bytes(), str(path))
        fixtures = [p for p in (PACKAGE / "tests/fixtures/feeds").rglob("*") if p.is_file()]
        self.assertEqual(len(fixtures), 3)
        for path in fixtures:
            original = ROOT / "tests/fixtures/feeds" / path.relative_to(PACKAGE / "tests/fixtures/feeds")
            self.assertEqual(path.read_bytes(), original.read_bytes(), str(path))

    def test_real_eval_runner_in_tank_only_process(self):
        with tempfile.TemporaryDirectory(prefix="tank-eval-runtime-") as folder:
            app = Path(folder)
            # These copies match Tank's Dockerfile: top-level modules + skills.
            for path in (ROOT / "tank").glob("*.py"):
                shutil.copyfile(path, app / path.name)
            shutil.copytree(ROOT / "tank/skills", app / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            for name in ("PYTHONPATH", "SKILLS_DIR", "RADIX_SOURCE_CIPC_KEY", "RADIX_SOURCE_REGISTER_KEY", "FRED_API_KEY"):
                env.pop(name, None)
            result = subprocess.run([sys.executable, "-I", "-c", ISOLATED_EVALS, platform_tenant()],
                                    cwd=app, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(len(report), 6)
            self.assertEqual(report["market.series_fetch"], {"passed": 3, "total": 3})
