"""market.series_fetch 1.3.0 (feedparser minor) clears the offline Skala eval gate.

The live gates (evals -> staging, source-review, founder approve) run on a deployed Tank;
this proves the same skala.run_evals result offline and that no approved case is dropped.
"""
import uuid

import httpx
import pytest

import skala

SKILL, VERSION = "market.series_fetch", "1.3.0"
# Approved on a live box when 1.2.1 was written (tests/test_skala_market_refusal_patches.py).
APPROVED = (("boston", "1.1.0"), ("za", "1.2.0"), ("either", "1.2.1"))


def packages():
    return {(p.id, p.version): p for p in skala.load_packages().values()}


def context(pkg):
    async def no_model(**kwargs):
        raise AssertionError("No real model in series_fetch evals")

    def no_network(request):
        raise AssertionError("No network in series_fetch evals")

    return skala.SkillContext(uuid.uuid4(), pkg.ref, pkg.agent, None, no_model,
                              httpx.AsyncClient(transport=httpx.MockTransport(no_network)))


def test_minor_is_a_new_version_with_refusal_cases():
    pkg = packages()[(SKILL, VERSION)]
    assert pkg.eval_threshold == 1.0
    assert len(pkg.cases) >= 5 and any(case.get("must_refuse") for case in pkg.cases)
    assert (pkg.path / "feeds" / "keyless.py").read_bytes().count(b"import feedparser") == 1


@pytest.mark.asyncio
async def test_minor_passes_every_eval_offline_and_is_eligible():
    pkg = packages()[(SKILL, VERSION)]
    result = await skala.run_evals(pkg, lambda: context(pkg))
    assert result["passed"] == result["total"] == len(pkg.cases), result["details"]
    assert result["score"] >= pkg.eval_threshold
    assert result["eligible"] is True, result["evidence_reason"]


@pytest.mark.parametrize("box,approved", APPROVED)
def test_minor_keeps_every_approved_case_fingerprint(box, approved):
    pkgs = packages()
    old = {skala.evidence_hash(case) for case in pkgs[(SKILL, approved)].cases}
    new = {skala.evidence_hash(case) for case in pkgs[(SKILL, VERSION)].cases}
    assert old <= new, f"{VERSION} drops {len(old - new)} of {box}'s approved {approved} cases"


def test_tank_image_installs_feedparser():
    # keyless.py imports feedparser at module level and adapters.py imports keyless.
    from pathlib import Path
    reqs = (Path(__file__).resolve().parents[1] / "tank" / "requirements.txt").read_text()
    market = (Path(__file__).resolve().parents[1] / "agents/market_lab/feeds/requirements.txt").read_text()
    pin = next(line for line in market.splitlines() if line.startswith("feedparser=="))
    assert pin in reqs.splitlines()
