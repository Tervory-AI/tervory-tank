"""Read-only feed boundaries; all I/O is isolated.

The PostCSS regression uses the real GHSA-r28c-9q8g-f849 affected range and
fixed release, retrieved from GitHub's public advisory on 2026-10-26.
"""
import importlib
import json
from pathlib import Path

import pytest

from agents.market_lab.supply_chain import Inventory, inventory, scan
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


def test_source_failure_is_not_a_clean_scan():
    class Unavailable(AdvisoryClient):
        def json(self, *args, **kwargs):
            raise SourceError("Source unavailable.")
    report = scan(locked_postcss(), Unavailable())
    assert not report["complete"] and report["errors"]


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






def test_import_has_no_network_or_publication_side_effect(monkeypatch):
    monkeypatch.setattr(Client, "json", lambda *a, **kw: pytest.fail("Import called network"))
    module = importlib.import_module("agents.market_lab.supply_chain")
    assert callable(module.scan) and callable(module.inventory)


@pytest.mark.parametrize("url", ["http://api.github.com/advisories", "https://unlisted.invalid/feed", "https://user@api.github.com/advisories"])
def test_http_refuses_unlisted_or_credential_bearing_source_urls(url):
    with pytest.raises(SourceError, match="allowlist"):
        Client().json(url)


@pytest.mark.parametrize("method,url,body", [
    ("POST", "https://api.github.com/repos/placeholder/repo/pulls", {}),
    ("DELETE", "https://api.github.com/repos/placeholder/repo/git/refs/heads/main", None),
    ("PATCH", "https://api.github.com/repos/placeholder/repo", {}),
    ("POST", SOURCE_URLS["cisa-kev"], {}),
    ("POST", SOURCE_URLS["osv"] + "vulns/placeholder", {}),
    ("GET", "https://api.github.com/advisories", {}),
])
def test_http_cannot_write_even_with_a_token(method, url, body, monkeypatch):
    from agents.market_lab.supply_chain import http
    monkeypatch.setattr(http, "build_opener", lambda *args: pytest.fail("Forbidden request reached transport"))
    with pytest.raises(SourceError, match="read-only"):
        Client("placeholder-read-token").json(url, body, method=method)


@pytest.mark.parametrize("case,expected", [("findings", 1), ("clean", 0), ("incomplete", 1)])
def test_read_only_cli_persists_report_and_fails_on_findings_or_missing_coverage(case, expected, monkeypatch, tmp_path):
    from agents.market_lab.supply_chain import __main__ as cli
    import sys

    class Unavailable(AdvisoryClient):
        def json(self, *args, **kwargs):
            raise SourceError("Source unavailable.")

    provider = (Unavailable() if case == "incomplete" else
                AdvisoryClient(osv=case != "clean", github=case != "clean"))
    monkeypatch.setattr(cli, "Client", lambda token: provider)
    monkeypatch.setattr(cli, "inventory", lambda root: locked_postcss())
    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["watch", "--root", str(tmp_path), "--report", str(report)])
    assert cli.main() == expected
    data = json.loads(report.read_text())
    assert data["complete"] is (case != "incomplete")
    assert bool(data["findings"]) is (case == "findings")
    assert all(method == "GET" or (url.endswith("querybatch") and method == "POST")
               for url, _, method in provider.calls)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.json"]


def test_removed_publish_option_is_rejected_before_any_io(monkeypatch, tmp_path):
    from agents.market_lab.supply_chain import __main__ as cli
    import sys
    monkeypatch.setattr(cli, "Client", lambda *args: pytest.fail("No I/O permitted"))
    monkeypatch.setattr(sys, "argv", ["watch", "--report", str(tmp_path / "report.json"), "--publish"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 2 and not list(tmp_path.iterdir())






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
    assert run["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    assert "--publish" not in run["run"]
    assert "SUPPLY_CHAIN_GITHUB_TOKEN" not in json.dumps(workflow)


@pytest.mark.parametrize('name,version', [('torch', '2.10.0'), ('torchvision', '0.25.0')])
def test_hash_pinned_cpu_wheels_preserve_package_and_local_version(name, version):
    url = f'https://download.pytorch.org/whl/cpu/{name}-{version}%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl'
    text = f'{name} @ {url} ' + '--hash=sha256:' + 'a' * 64
    assert python_locks('requirements.lock', text) == [Dependency('PyPI', name, version + '+cpu', 'requirements.lock')]


@pytest.mark.parametrize('source', [
    'http://wheels.example/torch-2.10.0-cp312-cp312-linux_x86_64.whl',
    'https://user:dummy@wheels.example/torch-2.10.0-cp312-cp312-linux_x86_64.whl',
    'https://wheels.example/other-2.10.0-cp312-cp312-linux_x86_64.whl',
    'https://wheels.example/torch-2.10.0.tar.gz',
    'https://wheels.example/torch-2.10.0-cp312-cp312-linux_x86_64.whl?download=1',
    'https://wheels.example/torch-2.10.0-cp312-cp312-linux_x86_64.whl#fragment',
    'https://wheels.example/torch-bad.whl',
    'git+https://wheels.example/torch.git',
])
def test_unknown_direct_sources_still_make_inventory_incomplete(tmp_path, source):
    lock = tmp_path / 'requirements.lock'
    lock.write_text('torch @ ' + source + ' --hash=sha256:' + 'a' * 64)
    result = inventory(tmp_path, ['requirements.lock'])
    assert result.errors and result.coverage['requirements.lock'].startswith('unreadable')


@pytest.mark.parametrize('suffix', ['', ' --hash=sha256:abc', ' --hash=sha256:' + 'g' * 64,
    ' --hash=sha256:' + 'a' * 64 + ' --trusted-host wheels.example'])
def test_direct_wheels_require_only_valid_hash_options(suffix):
    with pytest.raises(ValueError):
        python_locks('requirements.lock', 'torch @ https://wheels.example/torch-2.10.0-cp312-cp312-linux_x86_64.whl' + suffix)
