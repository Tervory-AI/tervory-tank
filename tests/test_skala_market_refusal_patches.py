"""Eval-only market patches that keep both Tank boxes' approved case fingerprints."""
import uuid

import httpx
import pytest

import skala

# (skill, previous version, patch)
PATCHES = (
    ("market.series_fetch", "1.2.0", "1.2.1"),
    ("market.shift_detect", "1.0.1", "1.0.2"),
    ("market.surge_detect", "1.0.1", "1.0.2"),
)
# Approved on a live box when these patches were written: (skill, box, approved version, patch).
APPROVED_BASELINES = (
    ("market.series_fetch", "boston", "1.1.0", "1.2.1"), ("market.series_fetch", "za", "1.2.0", "1.2.1"),
    ("market.shift_detect", "boston", "1.0.0", "1.0.2"), ("market.shift_detect", "za", "1.0.1", "1.0.2"),
    ("market.surge_detect", "boston", "1.0.0", "1.0.2"), ("market.surge_detect", "za", "1.0.1", "1.0.2"),
)


def packages():
    return {(p.id, p.version): p for p in skala.load_packages().values()}


def context(pkg):
    async def no_model(**kwargs):
        raise AssertionError("No real model in eval patch tests")

    def no_network(request):
        raise AssertionError("No network in eval patch tests")

    return skala.SkillContext(uuid.uuid4(), pkg.ref, pkg.agent, None, no_model,
                              httpx.AsyncClient(transport=httpx.MockTransport(no_network)))


@pytest.mark.parametrize("skill,previous,patch", PATCHES)
def test_patch_code_is_unchanged(skill, previous, patch):
    pkg = packages()[(skill, patch)]
    old = pkg.path.parent / previous
    for source in old.rglob("*.py"):
        assert (pkg.path / source.relative_to(old)).read_bytes() == source.read_bytes()
    assert len(pkg.cases) >= 5 and any(case.get("must_refuse") for case in pkg.cases)


@pytest.mark.asyncio
@pytest.mark.parametrize("skill,previous,patch", PATCHES)
async def test_patch_passes_offline_and_is_eligible(skill, previous, patch):
    pkg = packages()[(skill, patch)]
    result = await skala.run_evals(pkg, lambda: context(pkg))
    assert result["passed"] == result["total"] == len(pkg.cases), result["details"]
    assert result["eligible"] is True, result["evidence_reason"]


@pytest.mark.parametrize("skill,box,approved,patch", APPROVED_BASELINES)
def test_patch_keeps_every_approved_case_fingerprint(skill, box, approved, patch):
    # approval_reason refuses a version that drops or changes any approved case. The hash is
    # over the parsed JSON, so 10.0 and 10 differ: approved lines must be carried verbatim.
    pkgs = packages()
    old = {skala.evidence_hash(case) for case in pkgs[(skill, approved)].cases}
    new = {skala.evidence_hash(case) for case in pkgs[(skill, patch)].cases}
    assert old <= new, f"{skill} {patch} drops {len(old - new)} of {box}'s approved {approved} cases"
