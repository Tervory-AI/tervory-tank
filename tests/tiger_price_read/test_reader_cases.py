"""Offline cases for tiger.price_extract 1.1.0. No network."""

from __future__ import annotations

import asyncio
from pathlib import Path

import skala

from reader import reader

PKG = Path(__file__).resolve().parents[2] / "tank" / "skills" / "tiger.price_extract" / "1.1.0"


def test_package_cases_match() -> None:
    package = skala.load_packages(PKG.parent.parent)[("tiger.price_extract", "1.1.0")]
    assert package.rung == 3
    assert package.task_type is None
    assert package.cases

    async def once() -> list[str]:
        failures = []
        for case in package.cases:
            output = await reader.run(case["input"], None)
            ok, why = skala.score_case(case["expected"], output, case["tolerance"])
            if not ok:
                failures.append(f"{case.get('name')}: {why} -> {output}")
        return failures

    failures = asyncio.run(once())
    assert not failures, "\n".join(failures)
