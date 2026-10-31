"""Miss records carry enough to diagnose a miss: the (redacted) answer with its
quoted sentence(s), and why each rule-card quote did or did not count.

Every text is passed through the existing PII redaction (engine._clean_piece)
after secrets are cut out. Nothing here changes how a case is scored.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.zenas.core import selftest  # noqa: E402
from agents.zenas.core.ladder_store import LadderMemory  # noqa: E402

QUOTE = "This is an appeal against an order made by the Competition Tribunal."
HOLDING = "The Tribunal was entitled to find that the conduct was an abuse of dominance."
DOC = {
    "name": "Phutuma Networks (Pty) Ltd v Telkom SA Ltd",
    "citation": "CAC 108",
    "quote": QUOTE,
    "text": "[1] " + QUOTE + " [2] The facts are not in dispute. [3] " + HOLDING + " The appeal is dismissed.",
}
TRAP_OK = "I cannot find that case. I could not verify it, so I have left it out."
ENV_SECRET = "zz-offline-env-secret-value-0123456789"
EMAIL = "someone.private@example.org"
# Built at runtime so the committed-secret scan never sees a key-shaped literal.
SK = "sk-" + "offlinePLACEHOLDER0123456789abcdef"


def _run(monkeypatch, real_answer):
    calls = {"n": 0}

    async def answer_question(*args, question: str, **kwargs):
        index = calls["n"]
        calls["n"] += 1
        return {"ok": True, "memo": {"text": TRAP_OK}} if index < 40 else real_answer(index, question)

    monkeypatch.setattr("agents.zenas.core.service.answer_question", answer_question)
    ladder = LadderMemory()
    out = asyncio.run(selftest.run_selftest(ladder, region="za", library=[DOC], model=object()))
    made = next(run for run in out["runs"] if str(run["area"]).startswith("Made-up"))
    stored = next(row for row in ladder.selftests if row["detail"].get("made_up"))
    return made, stored["detail"]


def _card(memo, quotes):
    return {
        "ok": True,
        "memo": {"text": memo},
        "rule_card": {"elements": [{"citation": c, "quote": q, "test": "t"} for c, q in quotes]},
    }


def test_long_answer_keeps_the_quoted_sentence_and_redacts(monkeypatch):
    monkeypatch.setenv("ZENAS_FAKE_API_TOKEN", ENV_SECRET)
    paraphrase = "The Tribunal could properly find that the conduct amounted to abuse of dominance."
    padding = " ".join(["The court then dealt with the background at some length."] * 40)
    memo = (
        f"CAC 108. Contact {EMAIL}. Key {SK}. Env {ENV_SECRET}. {padding} "
        f"The court said: “{paraphrase}” {padding}"
    )
    made, detail = _run(monkeypatch, lambda i, q: _card(memo, [("CAC 108", paraphrase)]))
    assert made["passed"] == 40  # scoring unchanged: a paraphrase still misses
    miss = made["misses"][0]
    assert miss["reason"] == "real: the answer does not quote the court's sentence"
    excerpt = miss["answer_excerpt"]
    assert len(excerpt) <= selftest._MISS_ANSWER_CHARS
    assert paraphrase in excerpt  # the quoted sentence survives the bound
    assert miss["answer_chars"] > len(excerpt)
    assert miss["quotes"] == [{"quote": paraphrase, "check": "not verbatim in the stored judgment text"}]
    assert miss["library_chars"] == len(" ".join(DOC["text"].split()))
    for blob in (json.dumps(made), json.dumps(detail)):
        assert EMAIL not in blob
        assert SK not in blob
        assert ENV_SECRET not in blob
    assert "[Email]" in excerpt


def test_quote_checks_explain_each_card_quote(monkeypatch):
    memo = "CAC 108 dismissed the appeal."  # supported quote not repeated in the memo
    quotes = [
        ("CAC 108", HOLDING),
        ("CAC 108", "abuse of dominance."),
        ("CAC 108", HOLDING.replace("entitled", "permitted")),
        ("CAC 200", QUOTE),
    ]
    made, _ = _run(monkeypatch, lambda i, q: _card(memo, quotes))
    assert made["passed"] == 40
    miss = made["misses"][0]
    assert [row["check"] for row in miss["quotes"]] == [
        "supported, not in the answer",
        "too short to be a quote",
        "not verbatim in the stored judgment text",
    ]
    assert miss["other_citations"] == ["CAC 200"]
    assert all(row["check"] in selftest.QUOTE_CHECKS for row in miss["quotes"])


def test_passing_runs_are_unchanged(monkeypatch):
    made, _ = _run(monkeypatch, lambda i, q: _card(f"CAC 108: “{HOLDING}”", [("CAC 108", HOLDING)]))
    assert made["passed"] == 50 and made["misses"] == []


def test_old_stored_rows_are_redacted_on_read():
    """Rows stored before this change hold a raw answer start; it is masked on the way out."""
    raw = [
        {
            "case": "real-03",
            "kind": "real",
            "citation": "CAC 108",
            "reason": "real: the answer does not quote the court's sentence",
            "question": "What did CAC 108 hold?",
            "answer": f"CAC 108 per {EMAIL} token={ENV_SECRET} and {SK}",
            "expected_quote": QUOTE,
            "quotes": [{"quote": QUOTE, "check": "made-up check"}],
        }
    ]
    out = selftest._public_misses(raw)
    blob = json.dumps(out)
    assert EMAIL not in blob and SK not in blob and ENV_SECRET not in blob
    assert out[0]["answer_excerpt"].startswith("CAC 108")
    assert out[0]["quotes"][0]["check"] == "unknown"
    assert "answer" not in out[0]


def test_secret_shapes_are_cut_before_the_mask():
    text = (
        "Bearer abcdefghijklmnop1234 postgresql://user:pw123456@db:5432/x "
        "https://host/path?api_" + "key=abcdef12345 " + "pass" + "word: hunter2hunter2 " + "gh" + "p_" + "a" * 36
    )
    cleaned = selftest._diagnostic_text(text)
    for leaked in ("abcdefghijklmnop1234", "pw123456", "abcdef12345", "hunter2hunter2", "a" * 36):
        assert leaked not in cleaned


def test_excerpt_is_bounded_even_with_many_quotes():
    masked = " ".join(f"Para {i}: “{'word ' * 20}end.”" for i in range(80))
    excerpt = selftest._answer_excerpt(masked)
    assert len(excerpt) <= selftest._MISS_ANSWER_CHARS
    assert excerpt.startswith("Para 0")


# Review of #512, point 6: one runtime-built fake per secret shape. Every fake is
# assembled from pieces so no committed line looks like a key (the scanner is untouched).
def _fill(n, alphabet="AbCdEfGhJkMnPqRsTuVwXyZ23456789"):
    return "".join(alphabet[(i * 7) % len(alphabet)] for i in range(n))


_HEX = "0123456789abcdef"
SHAPES = {
    "stripe live secret": ("sk" + "_live_" + _fill(24),),
    "stripe restricted": ("rk" + "_live_" + _fill(24),),
    "github fine-grained pat": ("github" + "_pat_" + _fill(22) + "_" + _fill(59),),
    "google api key": ("AI" + "za" + _fill(35),),
    "jwt": ("ey" + "J" + _fill(24) + "." + "ey" + "J" + _fill(30) + "." + _fill(43),),
    "pem private key": (
        "-----BEGIN " + "RSA PRIVATE" + " KEY-----\n" + _fill(64) + "\n" + _fill(64) + "\n-----END " + "RSA PRIVATE" + " KEY-----",
    ),
    "json api_key": ('{"api' + '_key": "' + _fill(32) + '"}', _fill(32)),
    "authorization token header": ("Authorization: " + "Token " + _fill(40),),
    "aws secret access key": ("aws_secret" + "_access_key = " + _fill(40),),
    "coolify sanctum token": ("12" + "|" + _fill(48),),
    "long hex secret": (_fill(64, _HEX),),
    "hex after a key word": ("r2 secret " + _fill(40, _HEX),),
}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_each_secret_shape_is_cut(name):
    secret, *inner = SHAPES[name]
    text = f"The court held the appeal fails. {secret} Costs follow."
    cleaned = selftest._diagnostic_text(text)
    check = inner[0] if inner else secret
    assert check not in cleaned, name
    # No long run of the fake survives either (catches partial masking such as digit-only cuts).
    body = check.replace("\n", "")
    for start in range(0, max(1, len(body) - 12), 6):
        assert body[start : start + 12] not in cleaned.replace(" ", ""), name
    assert "The court held the appeal fails." in cleaned and "Costs follow." in cleaned


def test_secret_shapes_are_cut_in_citations_too():
    for name, (secret, *inner) in SHAPES.items():
        assert (inner[0] if inner else secret) not in selftest._citation_text(f"CAC 1 {secret}"), name


# Review of #512, point 7: a citation keeps its case number. Only secrets are cut.
def test_other_citations_keep_za_case_numbers(monkeypatch):
    memo = "CAC 108 dismissed the appeal."
    quotes = [("CAC 108", HOLDING), ("GP 09/2025", QUOTE), ("[2025] ZAGPJHC 1234", QUOTE)]
    made, detail = _run(monkeypatch, lambda i, q: _card(memo, quotes))
    miss = made["misses"][0]
    assert miss["other_citations"] == ["GP 09/2025", "[2025] ZAGPJHC 1234"]
    assert detail["misses"][0]["other_citations"] == ["GP 09/2025", "[2025] ZAGPJHC 1234"]
    # The same string run through the PII mask loses its number, which is why it is not masked.
    assert "09/2025" not in selftest._diagnostic_text("GP 09/2025")


def test_old_rows_keep_citation_numbers_on_read(monkeypatch):
    monkeypatch.setenv("ZENAS_FAKE_API_TOKEN", ENV_SECRET)
    out = selftest._public_misses([{"case": "real-01", "kind": "real", "citation": "CAC 108",
                                    "reason": selftest.MISS_REASONS[7], "other_citations": ["GP 09/2025", "x " + ENV_SECRET]}])
    assert out[0]["other_citations"][0] == "GP 09/2025"
    assert ENV_SECRET not in json.dumps(out)
