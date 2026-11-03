"""Eval-only patches that add real must_refuse evidence to code-only skills (ZA staging gate)."""
import uuid

import httpx
import pytest

import skala

# (skill, previous version, patch). Code is unchanged; every previous case line is kept.
CODE = (
    ("base.business_data", "2.0.0", "2.0.1"), ("base.contacts", "1.1.0", "1.1.1"),
    ("base.extract", "2.0.0", "2.0.1"), ("base.normalize", "1.0.0", "1.0.1"),
    ("base.resolve", "1.0.0", "1.0.1"), ("ffl.profile", "1.1.0", "1.1.1"),
    ("market.gap_score", "1.1.0", "1.1.1"), ("tiger.price_extract", "1.1.0", "1.1.1"),
    ("tiger.price_structured", "1.0.0", "1.0.1"),
)
# Positive cases read real sites, so only the refusals are checked offline.
NETWORK = (("base.find_site", "1.7.0", "1.7.1"), ("base.scrape_site", "1.2.0", "1.2.1"))


def packages():
    return {(p.id, p.version): p for p in skala.load_packages().values()}


def context(pkg):
    async def no_model(**kwargs):
        raise AssertionError("No real model in eval patch tests")

    def no_network(request):
        raise AssertionError("No network in eval patch tests")

    return skala.SkillContext(uuid.uuid4(), pkg.ref, pkg.agent, None, no_model,
                              httpx.AsyncClient(transport=httpx.MockTransport(no_network)))


@pytest.mark.parametrize("skill,previous,patch", CODE + NETWORK)
def test_patch_keeps_code_and_every_previous_case(skill, previous, patch):
    pkgs = packages()
    pkg, old_pkg = pkgs[(skill, patch)], pkgs[(skill, previous)]
    for source in old_pkg.path.rglob("*.py"):
        assert (pkg.path / source.relative_to(old_pkg.path)).read_bytes() == source.read_bytes()
    old = {skala.evidence_hash(case) for case in old_pkg.cases}
    assert old <= {skala.evidence_hash(case) for case in pkg.cases}
    assert len(pkg.cases) >= 5 and any(case.get("must_refuse") for case in pkg.cases)


@pytest.mark.asyncio
@pytest.mark.parametrize("skill,previous,patch", CODE)
async def test_code_patch_passes_offline_and_is_eligible(skill, previous, patch):
    pkg = packages()[(skill, patch)]
    result = await skala.run_evals(pkg, lambda: context(pkg))
    assert result["passed"] == result["total"] == len(pkg.cases), result["details"]
    assert result["eligible"] is True, result["evidence_reason"]
    assert not any(detail["used_model"] for detail in result["details"])


@pytest.mark.asyncio
@pytest.mark.parametrize("skill,previous,patch", NETWORK)
async def test_network_patch_refuses_without_the_network(skill, previous, patch):
    pkg = packages()[(skill, patch)]
    result = await skala.run_evals(pkg, lambda: context(pkg))
    refused = [d for case, d in zip(pkg.cases, result["details"]) if case.get("must_refuse")]
    assert refused and all(d["passed"] for d in refused), refused
    assert result["eligible"] is True, result["evidence_reason"]
