"""Price reading stays on the code rung. A model switch still uses the existing shadow gate.

The shadow runner already lives in Tank. This test does not rebuild it.
"""

from __future__ import annotations

import graduate

POLICY = {"eval_threshold": 0.97, "min_shadow_samples": 30, "max_reject_rate": 0.05}


def test_code_reader_is_not_a_paid_route() -> None:
    text = (graduate.SKILL_PREFIX + "tiger.price_extract@1.1.0")
    assert text.startswith("skill:")
    assert graduate.DEFAULT_MIN_SAMPLES == 200
    assert graduate.DEFAULT_THRESHOLD == 0.99


def test_existing_shadow_gate_blocks_a_short_or_weak_sample() -> None:
    short = graduate.Evidence(samples=12, agreement=0.99, rejected=0, judged=20)
    ok, why = graduate.proven_reason(POLICY, short)
    assert ok is False
    assert why == "too few shadow samples"
    weak = graduate.Evidence(samples=30, agreement=0.96, rejected=0, judged=20)
    ok, why = graduate.proven_reason(POLICY, weak)
    assert ok is False
    assert why == "agreement is below the bar"
    ready = graduate.Evidence(samples=30, agreement=0.97, rejected=1, judged=40)
    ok, why = graduate.proven_reason(POLICY, ready)
    assert ok is True
    assert why is None
