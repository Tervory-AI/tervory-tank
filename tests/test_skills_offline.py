"""Run every rung-3 skill's eval cases with no network, no database and no keys.

ctx.http raises, ctx.model raises, and ctx.env is empty. A case is network-bound
when that http error escapes run(), or when the skill catches it and the scored
output no longer matches (the case needed a live response). Those cases are
skipped. An offline case that fails still fails this test.
"""
import importlib.util
from pathlib import Path

import pytest
import skala

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tank" / "skills"
_REQUIRED = ("skill.yaml", "CHANGELOG.md", "evals/cases.jsonl")


class NetworkBlocked(Exception):
    """Raised by the stub HTTP client. Skills that need the network hit this."""


class StubHttp:
    def __init__(self) -> None:
        self.called = False

    def __getattr__(self, name: str):
        async def _call(*_args: object, **_kwargs: object) -> None:
            self.called = True
            raise NetworkBlocked(name)

        return _call


class StubCtx:
    def __init__(self) -> None:
        self.http = StubHttp()
        self.env: dict[str, str] = {}
        self.tenant_id = "00000000-0000-0000-0000-000000000001"  # platform tenant, as Skala evals run

    async def model(self, *_args: object, **_kwargs: object) -> str:
        raise RuntimeError("offline stub: model is not available")


def _from_network(exc: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, NetworkBlocked):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _load_run(pkg: skala.SkillPackage):
    path = pkg.path / "run.py"
    module_name = f"skill_{pkg.id}_{pkg.version}".replace(".", "_").replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"{pkg.ref}: missing run.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, "run", None)
    assert run is not None, f"{pkg.ref}: run.py has no run()"
    return run


def test_every_skill_package_has_required_files() -> None:
    missing: list[str] = []
    packages = [
        path
        for path in SKILLS.glob("*/*")
        if path.is_dir() and path.name != "__pycache__" and not path.name.startswith(".")
    ]
    assert packages, "no skill packages under tank/skills"
    for package in sorted(packages):
        for rel in _REQUIRED:
            if not (package / rel).is_file():
                missing.append(f"{package.relative_to(SKILLS)} missing {rel}")
    assert not missing, "\n".join(missing)


@pytest.mark.asyncio
async def test_rung3_offline_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    # Room-backed checkers (trigger.languagetool) need a room key before they call the
    # room; a placeholder lets them reach the stub http, so their cases count as network-bound.
    monkeypatch.setenv("TANK_KEY_TRIGGER", "offline-placeholder")
    packages = [pkg for pkg in skala.load_packages(SKILLS).values()
                if pkg.rung == 3 and pkg.id not in {"tisan.figma", "tisan.scaffold", "tisan.build"}]
    assert packages, "no rung-3 skills found"
    lines: list[str] = []
    failures: list[str] = []
    for pkg in sorted(packages, key=lambda item: item.ref):
        run = _load_run(pkg)
        passed = skipped = failed = 0
        for index, case in enumerate(pkg.cases):
            name = case.get("name") or f"case {index}"
            ctx = StubCtx()
            try:
                output = await run(case.get("input") or {}, ctx)
            except Exception as exc:  # noqa: BLE001 — a raised stub http call means the case needs the network
                if _from_network(exc):
                    skipped += 1
                    continue
                # Same rule as skala.run_evals: a must_refuse case passes when run() raises
                # exactly the expected exception type and message.
                expected_error = case.get("expected_error") or {}
                if (case.get("must_refuse") and type(exc).__name__ == expected_error.get("type")
                        and str(exc) == expected_error.get("message")):
                    passed += 1
                    continue
                failed += 1
                failures.append(f"{pkg.ref} / {name}: error: {exc}")
                continue
            ok, why = skala.score_case(case.get("expected") or {}, output, case.get("tolerance") or "exact")
            if case.get("expected_error"):
                ok, why = False, "expected refusal exception was not raised"
            if ok:
                passed += 1
            elif ctx.http.called:
                skipped += 1
            else:
                failed += 1
                failures.append(f"{pkg.ref} / {name}: {why}")
        lines.append(
            f"{pkg.ref}: {passed} passed, {skipped} network-skipped, {failed} failed ({len(pkg.cases)} cases)"
        )
    report = "\n".join(lines)
    print(report)
    assert not failures, report + "\n" + "\n".join(failures)
