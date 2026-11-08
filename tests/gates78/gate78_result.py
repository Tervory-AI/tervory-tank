"""Machine-readable pytest evidence; missing, skipped and xfailed are not passes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--gate78-result", required=True)


class Evidence:
    def __init__(self, path):
        self.path = Path(path)
        self.selected = []
        self.outcomes = {}
        self.collection_errors = []

    def pytest_collection_finish(self, session):
        self.selected = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(report.nodeid)

    def pytest_runtest_logreport(self, report):
        phases = self.outcomes.setdefault(report.nodeid, {})
        phases[report.when] = (
            "xfail" if hasattr(report, "wasxfail") else report.outcome
        )

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        cases = {}
        for node in self.selected:
            phases = self.outcomes.get(node, {})
            cases[node] = (
                "PASS" if all(phases.get(phase) == "passed" for phase in ("setup", "call", "teardown"))
                else "FAIL"
            )
        ok = bool(cases) and all(value == "PASS" for value in cases.values())
        ok = ok and not self.collection_errors and exitstatus == 0
        if not ok:
            session.exitstatus = 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "exit_code": int(session.exitstatus), "cases": cases,
            "collection_errors": self.collection_errors,
        }, indent=2) + "\n")


def pytest_configure(config):
    config.pluginmanager.register(Evidence(config.getoption("--gate78-result")), "gate78-evidence")
