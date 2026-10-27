"""Never-block list, IP-in-log gate, actions-per-hour cap."""
from agents.ghost.never_block import ActionCap, classify_never_block, extract_ips, may_block_ip


def test_extract_ips_from_raw_log():
    raw = "2026-10-26T12:00:00Z src=203.0.113.50 path=/wp-login.php\nother 198.51.100.10\n"
    assert extract_ips(raw) == ["203.0.113.50", "198.51.100.10"]


def test_may_block_requires_ip_in_raw_log():
    ok, why = may_block_ip("203.0.113.50", raw_log="no address here")
    assert ok is False and "raw log" in why


def test_never_block_cloudflare_and_payment_and_own():
    # Cloudflare published range sample
    assert classify_never_block("104.16.1.1") == "Cloudflare"
    # Stripe representative
    assert classify_never_block("54.187.174.169") == "payment provider"
    assert classify_never_block("203.0.113.50", client_own_cidrs=["203.0.113.0/24"]) == "client own address"
    assert classify_never_block("203.0.113.50") is None


def test_may_block_attacker_present_in_log():
    raw = "attack from 203.0.113.77 on /admin"
    ok, why = may_block_ip("203.0.113.77", raw_log=raw)
    assert ok is True and why == "ok"


def test_action_cap_per_hour():
    cap = ActionCap(limit=2, clock=lambda: 1_000.0)
    assert cap.allow("t1")[0] is True
    assert cap.allow("t1")[0] is True
    ok, why = cap.allow("t1")
    assert ok is False and "cap" in why
    # Other tenant unaffected.
    assert cap.allow("t2")[0] is True
