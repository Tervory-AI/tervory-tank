"""Feed, resolver and draft publication boundaries; all I/O is isolated.

The PostCSS regression uses the real GHSA-r28c-9q8g-f849 affected range and
fixed release, retrieved from GitHub's public advisory on 2026-10-26.
"""
import importlib
import json
from pathlib import Path
import subprocess

import pytest

from agents.market_lab.supply_chain import Inventory, inventory, scan
from agents.market_lab.supply_chain import fixes
from agents.market_lab.supply_chain.http import Client, SourceError
from agents.market_lab.supply_chain.locks import Dependency, node_locks, python_locks
from agents.market_lab.supply_chain.sources import SOURCE_URLS
from agents.market_lab.supply_chain.watch import pages

GHSA = {
    "ghsa_id": "GHSA-r28c-9q8g-f849", "cve_id": "CVE-2026-73646", "severity": "high",
    "vulnerabilities": [{"package": {"ecosystem": "npm", "name": "postcss"},
                         "vulnerable_version_range": "<= 8.5.17", "first_patched_version": "8.5.18"}],
}
# The same real range expressed in the OSV input schema for the range evaluator.
OSV = {"id": GHSA["ghsa_id"], "aliases": [GHSA["cve_id"]], "affected": [
    {"package": {"ecosystem": "npm", "name": "postcss"},
     "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "8.5.18"}]}]},
]}


class AdvisoryClient:
    def __init__(self, *, osv=True, github=True):
        self.osv = osv
        self.github = github
        self.calls = []

    def json(self, url, body=None, *, method="GET"):
        self.calls.append((url, body, method))
        if url == SOURCE_URLS["cisa-kev"]:
            return {"catalogVersion": "2026.10.26", "vulnerabilities": []}
        if url == SOURCE_URLS["osv"] + "querybatch":
            return {"results": [{"vulns": [{"id": GHSA["ghsa_id"]}]} if self.osv else {} for _ in body["queries"]]}
        if url == SOURCE_URLS["osv"] + "vulns/" + GHSA["ghsa_id"]:
            return OSV
        if url.startswith(SOURCE_URLS["github"] + "advisories?"):
            return [GHSA] if self.github else []
        raise AssertionError("Unexpected source call")


def locked_postcss():
    return Inventory([Dependency("npm", "postcss", "8.4.31", "site/package-lock.json"),
                      Dependency("npm", "postcss", "8.4.31", "workspace/package-lock.json")],
                     {"site/package-lock.json": "software", "workspace/package-lock.json": "software"})


def test_all_sources_are_queried_and_same_fix_is_grouped_across_locks():
    client = AdvisoryClient()
    report = scan(locked_postcss(), client)
    assert report["complete"] and not report["errors"]
    assert len(report["findings"]) == len(report["fixes"]) == 1
    fix = report["fixes"][0]
    assert fix["fixed_version"] == "8.5.18"
    assert fix["locks"] == ["site/package-lock.json", "workspace/package-lock.json"]
    assert fix["advisories"] == ["CVE-2026-73646", "GHSA-r28c-9q8g-f849"]
    assert fix["source_ids"] == ["github", "osv"]
    assert fix["known_exploited"] == []  # A high advisory is not automatically a KEV match.
    assert len([call for call in client.calls if "advisories?" in call[0]]) == 1
    assert report["producer"] == "Market Lab"


@pytest.mark.parametrize("osv,github", [(False, True), (True, False)])
def test_either_advisory_source_can_find_a_vulnerability(osv, github):
    report = scan(locked_postcss(), AdvisoryClient(osv=osv, github=github))
    assert report["complete"] and report["fixes"][0]["fixed_version"] == "8.5.18"


def test_source_failure_is_not_a_clean_scan_or_permission_to_publish():
    class Unavailable(AdvisoryClient):
        def json(self, *args, **kwargs):
            raise SourceError("Source unavailable.")
    report = scan(locked_postcss(), Unavailable())
    assert not report["complete"] and report["errors"]
    with pytest.raises(fixes.FixError, match="Incomplete"):
        fixes.grouped_fixes(report)


def test_incomplete_batch_and_unknown_lock_stop_clean_status(tmp_path):
    class Truncated(AdvisoryClient):
        def json(self, url, *args, **kwargs):
            if url.endswith("querybatch"):
                return {"results": []}
            return super().json(url, *args, **kwargs)
    assert not scan(locked_postcss(), Truncated())["complete"]
    (tmp_path / "poetry.lock").write_text("unreadable")
    items = inventory(tmp_path, ["poetry.lock"])
    assert items.errors and "poetry.lock" in items.coverage
    assert not scan(items, AdvisoryClient())["complete"]


def test_withdrawn_advisory_is_not_a_fix():
    class Withdrawn(AdvisoryClient):
        def json(self, url, *args, **kwargs):
            data = super().json(url, *args, **kwargs)
            if "/vulns/" in url:
                return {**data, "withdrawn": "2026-10-26T00:00:00Z"}
            if "advisories?" in url:
                return [{**item, "withdrawn_at": "2026-10-26T00:00:00Z"} for item in data]
            return data
    report = scan(locked_postcss(), Withdrawn())
    assert report["complete"] and not report["fixes"]


def test_github_pagination_does_not_drop_the_last_page():
    class Paginated:
        def json(self, url):
            return [GHSA] * (100 if url.endswith("&page=1") else 1)
    assert len(pages(Paginated(), "https://api.github.com/advisories")) == 101


def test_python_markers_and_nested_node_versions_are_all_scanned():
    deps = python_locks("requirements.lock", 'httpx==0.28.1 ; python_version < "3.10" \\\n    --hash=sha256:' + "a" * 64 + "\n")
    assert deps[0].name == "httpx" and deps[0].version == "0.28.1"
    deps = node_locks("package-lock.json", {"packages": {
        "": {}, "node_modules/postcss": {"version": "8.5.18"},
        "node_modules/next/node_modules/postcss": {"version": "8.4.31"},
        "node_modules/@scope/pkg": {"version": "1.0.0"},
    }})
    assert [(dep.name, dep.version) for dep in deps] == [("postcss", "8.5.18"), ("postcss", "8.4.31"), ("@scope/pkg", "1.0.0")]


def test_real_repository_lock_formats_are_accounted_for():
    root = Path(__file__).resolve().parents[1]
    items = inventory(root)
    assert not items.errors
    assert len(items.coverage) >= 12
    assert items.coverage["agents/rig/forge/gpu/models.lock.json"].startswith("data-only:")
    assert any(dep.repository == "microsoft/TRELLIS.2" and len(dep.revision) == 40 for dep in items.dependencies)


def test_registry_update_replaces_hashes_and_preserves_python_markers():
    fix = {"package": "httpx", "versions": ["0.27.2"], "target": "0.28.1"}
    old = 'httpx==0.27.2 ; python_version >= "3.10" \\\n    --hash=sha256:' + "a" * 64 + "\nanyio==4.8.0\n"
    changed = fixes._replace_python(old, fix, ["b" * 64])
    assert 'httpx==0.28.1 ; python_version >= "3.10"' in changed
    assert "a" * 64 not in changed and "b" * 64 in changed
    assert "anyio==4.8.0" in changed


def test_node_resolver_only_updates_locks_and_disables_scripts(tmp_path, monkeypatch):
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"dependencies": {"postcss": "8.4.31"}}))
    (tmp_path / "package-lock.json").write_text("{}")
    commands = []
    monkeypatch.setattr(fixes, "command", lambda args, root: commands.append(args))
    fixes.node_fix(tmp_path, {"package": "postcss", "target": "8.5.18", "versions": ["8.4.31"], "locks": ["package-lock.json"]})
    assert json.loads(manifest.read_text())["dependencies"]["postcss"] == "8.5.18"
    assert all("--ignore-scripts" in args for args in commands)
    assert commands[0][:3] == ["npm", "update", "--package-lock-only"]
    assert commands[1][:2] == ["npm", "ci"]


def test_import_has_no_network_or_publication_side_effect(monkeypatch):
    monkeypatch.setattr(Client, "json", lambda *a, **kw: pytest.fail("Import called network"))
    module = importlib.import_module("agents.market_lab.supply_chain")
    assert callable(module.scan) and callable(module.inventory)


@pytest.mark.parametrize("url", ["http://api.github.com/advisories", "https://unlisted.invalid/feed", "https://user@api.github.com/advisories"])
def test_http_refuses_unlisted_or_credential_bearing_source_urls(url):
    with pytest.raises(SourceError, match="allowlist"):
        Client().json(url)


def test_one_draft_per_fix_never_overwrites_an_existing_review_branch(tmp_path):
    class Existing:
        token = "present"  # Sentinel, not a credential; the fake has no network method.
        def json(self, url, body=None, *, method="GET"):
            assert method == "GET"
            if url.endswith("/tervory-tank"):
                return {"default_branch": "main"}
            if "/git/ref/" in url:
                return {"object": {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path).decode().strip()}}
            if "/pulls?" in url:
                return [{"html_url": "https://github.com/zenascapetown-code/tervory-tank/pull/329"}]
            raise AssertionError(url)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Policy test", "-c", "user.email=policy-test@localhost", "commit", "--allow-empty", "-qm", "main"], check=True)
    report = scan(locked_postcss(), AdvisoryClient())
    assert len(fixes.publish(tmp_path, report, Existing(), "zenascapetown-code/tervory-tank")) == 1
    fix = fixes.grouped_fixes(report)[0]
    changed_advisories = {**fix, "advisories": [*fix["advisories"], "CVE-2026-73646"]}
    assert fixes.fix_key(fix) == fixes.fix_key(changed_advisories)


@pytest.mark.parametrize("orphan", ["none", "matching", "different"])
def test_draft_payload_contains_real_changes_and_never_a_merge_operation(tmp_path, monkeypatch, orphan):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path).decode().strip()
    git("init", "-q")
    git("config", "user.name", "Policy test")
    git("config", "user.email", "policy-test@localhost")
    (tmp_path / "package.json").write_text('{"dependencies":{"postcss":"8.4.31"}}')
    git("add", ".")
    git("commit", "-qm", "main")
    calls = []
    class GitHub:
        token = "present"
        def json(self, url, body=None, *, method="GET"):
            calls.append((url, body, method))
            if url.endswith("/tervory-tank"):
                return {"default_branch": "main"}
            if "/git/ref/" in url:
                return {"object": {"sha": "b" * 40 if "autumbra" in url else git("rev-parse", "HEAD")}}
            if "/pulls?" in url:
                return []
            if "/git/commits/" in url:
                if url.endswith("/" + "b" * 40):
                    return {"tree": {"sha": ("b" if orphan == "matching" else "c") * 40},
                            "message": "Autumbra: fix postcss at 8.5.18"}
                return {"tree": {"sha": "a" * 40}}
            if url.endswith("/git/refs") and orphan != "none":
                raise SourceError("Ref exists", status=422)
            if url.endswith("/pulls"):
                return {"html_url": "https://github.com/zenascapetown-code/tervory-tank/pull/329"}
            return {"sha": "b" * 40}
    def prepare(root, fix, client, tracked):
        (root / "package.json").write_text('{"dependencies":{"postcss":"8.5.18"}}')
    monkeypatch.setattr(fixes, "prepare", prepare)
    if orphan == "different":
        with pytest.raises(fixes.PublicationError, match="preserved"):
            fixes.publish(tmp_path, scan(locked_postcss(), AdvisoryClient()), GitHub(), "zenascapetown-code/tervory-tank")
        assert not any(url.endswith("/pulls") for url, _, _ in calls)
        return
    fixes.publish(tmp_path, scan(locked_postcss(), AdvisoryClient()), GitHub(), "zenascapetown-code/tervory-tank")
    pull = next(body for url, body, method in calls if url.endswith("/pulls"))
    assert pull["draft"] is True and pull["base"] == "main"
    assert any("8.5.18" in body.get("content", "") for _, body, _ in calls if body)
    assert all(method in {"GET", "POST"} and not url.endswith("/merge") for url, _, method in calls)
    assert (tmp_path / "package.json").read_text().endswith('"8.4.31"}}')


def test_nightly_is_default_branch_only_and_does_not_run_pr_code():
    import yaml
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/supply-chain.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert triggers["schedule"][0]["cron"] == "23 2 * * *"
    job = workflow["jobs"]["watch"]
    assert "default_branch" in job["if"] and "github.ref" in job["if"]
    assert workflow["permissions"] == {"contents": "read"}
    steps = job["steps"]
    assert steps[0]["with"]["persist-credentials"] is False
    run = next(step for step in steps if step.get("name", "").startswith("Scan every lock"))
    assert "secrets.SUPPLY_CHAIN_GITHUB_TOKEN" in run["env"]["GH_TOKEN"]
    assert "--publish" in run["run"]


def test_fix_cannot_introduce_a_new_vulnerable_transitive_dependency(tmp_path, monkeypatch):
    monkeypatch.setattr(fixes, "python_fix", lambda *args: None)
    monkeypatch.setattr(fixes, "inventory", lambda *args: Inventory([], {"requirements.lock": "software"}))
    monkeypatch.setattr(fixes, "scan", lambda *args: {"complete": True, "findings": [
        {"ecosystem": "PyPI", "package": "starlette", "version": "0.36.3", "locks": ["requirements.lock"]},
    ]})
    fix = {"ecosystem": "PyPI", "package": "httpx", "versions": ["0.27.2"], "target": "0.28.1",
           "locks": ["requirements.lock"], "baseline_findings": []}
    with pytest.raises(fixes.FixError, match="new vulnerable dependency"):
        fixes.prepare(tmp_path, fix, AdvisoryClient(), [])
