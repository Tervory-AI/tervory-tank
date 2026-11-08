#!/usr/bin/env python3
"""One cloud-only Gate 7/8 runner; --core validates infrastructure, not products.

Product contract: tests/gates78/products/<product>.json contains product,
source_sha (the product commit integrated into Tank), entrypoints (real routes or
workers), legacy_tests (original Gate 7/8 node IDs) and cases (requirement ID ->
nonempty list of pytest node IDs). Every requirement in gate78_contract applies.
Product tests live in tests/gates78/products/test_<product_with_underscores>.py.
The head thread reviews semantics: a node mapping alone is not acceptance proof.

Usage: python scripts/gates_7_8.py [--core | --submitted | --product opli]
Results are JSON + Markdown under .tmp/gates78/<unique run>/; no customer data.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "tests" / "gates78"
sys.path.insert(0, str(SUITE))

from gate78_contract import CORE_TARGETS, PRODUCTS, REQUIREMENTS


def load_product(product: str, root: Path = ROOT) -> dict:
    path = root / "tests" / "gates78" / "products" / f"{product}.json"
    if not path.exists():
        return {"product": product, "error": "Product scenarios not submitted"}
    try:
        item = json.loads(path.read_text())
        if item["product"] != product or not re.fullmatch(r"[a-f0-9]{40}", item["source_sha"]):
            raise ValueError("Invalid product/source_sha")
        for field in ("entrypoints", "legacy_tests"):
            if not isinstance(item[field], list) or not item[field] or not all(isinstance(v, str) and v.strip() for v in item[field]):
                raise ValueError(f"Missing {field}")
        if not isinstance(item["cases"], dict) or set(item["cases"]) != set(REQUIREMENTS):
            raise ValueError("Every canonical requirement must have an explicit test mapping")
        owned = f"tests/gates78/products/test_{product.replace('-', '_')}.py"
        for nodes in item["cases"].values():
            if not isinstance(nodes, list) or not nodes:
                raise ValueError("Empty test mapping")
            for node in nodes:
                if not isinstance(node, str) or not node.startswith(owned + "::test_") or "\n" in node:
                    raise ValueError("Required proof must enter the product's owned test module")
                if not (root / owned).is_file():
                    raise ValueError("Mapped test module does not exist")
        return item
    except (KeyError, ValueError, TypeError) as exc:
        return {"product": product, "error": f"Invalid manifest: {exc}"}


def mapped_outcome(nodes: list[str], evidence: dict) -> str:
    if evidence.get("exit_code") != 0 or evidence.get("collection_errors"):
        return "FAIL"
    cases = evidence.get("cases", {})
    for wanted in nodes:
        matches = [status for node, status in cases.items() if node == wanted or node.startswith(wanted + "[")]
        if not matches or any(status != "PASS" for status in matches):
            return "FAIL"
    return "PASS"


def run_tests(targets: list[str], output: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(str(ROOT / p) for p in ("", "tank", "agents", "agents/_chassis", "tests", "tests/gates78"))
    # Selection/exclusion flags from a developer shell cannot trim gate evidence.
    env["PYTEST_ADDOPTS"] = ""
    env.pop("PYTEST_PLUGINS", None)
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short", "--strict-markers",
               "--disable-socket", "--allow-unix-socket", "--allow-hosts=127.0.0.1,localhost,::1",
               "--timeout=180", "-p", "gate78_result", "--gate78-result", str(output), *targets]
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if not output.exists():
        return {"exit_code": result.returncode or 1, "cases": {}, "collection_errors": ["pytest produced no evidence"]}
    evidence = json.loads(output.read_text())
    if result.returncode:
        evidence["exit_code"] = result.returncode
    return evidence


def status_table(report: dict) -> str:
    lines = ["# Gate 7/8 acceptance", "", f"Tank commit: `{report['tank_sha']}`",
             f"Working tree: {'DIRTY — not certifiable' if report['dirty'] else 'clean'}",
             f"Shared core: **{report['core']}**", "",
             "A foundation-only PASS does not pass a product gate. Head review is required.", "",
             "| Product | Source commit | Gate 7 | Gate 8 |", "|---|---|---|---|"]
    for product, item in report["products"].items():
        lines.append(f"| {product} | {item.get('source_sha', 'pending')} | {item['gate7']} | {item['gate8']} |")
    lines += ["", f"Overall acceptance: **{report['overall']}**", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--core", action="store_true", help="Foundation only; products remain NOT RUN")
    scope.add_argument("--submitted", action="store_true", help="CI migration: test submitted products; report missing products as INCOMPLETE")
    scope.add_argument("--product", choices=PRODUCTS, help="Core plus one product; other products remain NOT RUN")
    args = parser.parse_args()
    temp = ROOT / ".tmp" / "gates78"
    temp.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=temp))
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True).strip())
    report = {"tank_sha": sha, "dirty": dirty, "core": "BLOCKED", "products": {}, "overall": "NOT RUN"}
    db = os.environ.get("MEMORY_TEST_DATABASE_URL", "")
    if urlsplit(db).hostname in {"127.0.0.1", "localhost", "::1"}:
        core = run_tests(list(CORE_TARGETS), output / "core.json")
        report["core"] = "PASS" if core["exit_code"] == 0 and core["cases"] else "FAIL"
    else:
        report["blocker"] = "Disposable loopback MEMORY_TEST_DATABASE_URL is required"
    selected = [] if args.core else [args.product] if args.product else list(PRODUCTS)
    if args.submitted:
        selected = [p for p in PRODUCTS if (ROOT / "tests/gates78/products" / f"{p}.json").exists()]
    for product in PRODUCTS:
        item = load_product(product, ROOT)
        row = {"gate7": "NOT RUN", "gate8": "NOT RUN", "source_sha": item.get("source_sha", "pending")}
        row["entrypoints"] = item.get("entrypoints", [])
        report["products"][product] = row
        if "error" in item:
            row.update(gate7="MISSING", gate8="MISSING", blocker=item["error"])
            continue
        if product not in selected:
            continue
        if report["core"] != "PASS":
            row.update(gate7="BLOCKED", gate8="BLOCKED", blocker="Shared core did not pass")
            continue
        targets = sorted({node for nodes in item["cases"].values() for node in nodes})
        evidence = run_tests(targets, output / f"{product}.json")
        row["requirements"] = {key: mapped_outcome(nodes, evidence) for key, nodes in item["cases"].items()}
        for gate in (7, 8):
            values = [value for key, value in row["requirements"].items() if key.startswith(f"G{gate}.")]
            row[f"gate{gate}"] = "PASS" if values and all(v == "PASS" for v in values) else "FAIL"
    selected_ok = report["core"] == "PASS" and all(report["products"][p][g] == "PASS" for p in selected for g in ("gate7", "gate8"))
    all_ok = selected_ok and not dirty and len(selected) == len(PRODUCTS)
    report["overall"] = "TESTS PASS — HEAD REVIEW PENDING" if all_ok else "INCOMPLETE"
    report["scope"] = "core" if args.core else "submitted" if args.submitted else args.product or "all"
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = status_table(report)
    (output / "summary.md").write_text(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(summary)
    print(summary)
    print(f"Evidence: {output.relative_to(ROOT)}")
    return 0 if selected_ok and (args.core or not dirty) else 1


if __name__ == "__main__":
    raise SystemExit(main())
