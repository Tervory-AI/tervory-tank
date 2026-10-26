"""Client apply modes and owner update email paragraphs."""
from pathlib import Path

from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings, active_halves, connect_copy, list_hands, load_settings, save_settings, set_hand
from agents.ghost.owner_email import FixtureEmailTransport, build_owner_update, send_owner_update
from agents.ghost.store import Store


def test_default_is_approve_each(tmp_path: Path):
    store = Store(tmp_path / "g.sqlite3")
    settings = load_settings(store, "00000000-0000-0000-0000-0000000000aa")
    assert settings.shield_mode is ApplyMode.approve_each
    assert settings.fix_mode is ApplyMode.approve_each
    stamp = settings.receipt_stamp()
    assert stamp["shield_mode"] == "I approve each one"


def test_client_can_change_modes_tervory_does_not(tmp_path: Path):
    store = Store(tmp_path / "g.sqlite3")
    tenant = "00000000-0000-0000-0000-0000000000bb"
    saved = save_settings(store, ClientAutumbraSettings(
        tenant_id=tenant,
        site_name="example.com",
        shield_mode=ApplyMode.auto_when_checks_pass,
        fix_mode=ApplyMode.never,
        cloudflare_connected=True,
    ))
    loaded = load_settings(store, tenant)
    assert loaded.shield_mode is ApplyMode.auto_when_checks_pass
    assert loaded.fix_mode is ApplyMode.never
    halves = active_halves(saved)
    assert halves["edge"] is True and halves["mailbox"] is False and halves["stack"] is True
    assert halves["block_in_seconds"] is True


def test_owner_email_three_fix_paragraphs():
    critical = [{
        "stack": "PHP", "name": "PHP", "rating": "critical",
        "advisory_id": "CVE-2026-109618",
        "advisory_url": "https://example.test/cve",
    }, {
        "stack": "Python", "rating": "critical", "advisory_id": "CVE-2026-1",
        "advisory_url": "https://example.test/cve2",
    }, {
        "stack": "Node", "rating": "critical", "advisory_id": "CVE-2026-2",
        "advisory_url": "https://example.test/cve3",
    }]
    base = dict(
        site_name="coolify.tervory.com",
        threats_found=10,
        critical=critical,
        receipt_url="https://protect.tervory.com/receipts/r1",
        pr_url="https://github.com/example/pr/1",
        fix_report_url="https://protect.tervory.com/report/1",
        undo_fix_url="https://protect.tervory.com/undo/fix",
        undo_shield_url="https://protect.tervory.com/undo/shield",
        shield={"blocked_addresses": 214, "source_name": "abuse.ch Feodo",
                "source_url": "https://feodotracker.abuse.ch"},
    )
    for mode, needle in [
        (ApplyMode.auto_when_checks_pass, "let us fix this kind of problem automatically"),
        (ApplyMode.approve_each, "approve fixes yourself"),
        (ApplyMode.never, "never touch your code"),
    ]:
        settings = ClientAutumbraSettings(
            tenant_id="00000000-0000-0000-0000-0000000000cc",
            site_name="coolify.tervory.com",
            fix_mode=mode,
        )
        mail = build_owner_update(settings=settings, **base)
        assert mail["subject"].startswith("Autumbra update for coolify.tervory.com: 10 threats found, 3 critical")
        assert needle in mail["body"]
        assert "Nothing from your logs was kept" in mail["body"]
        assert "214" in mail["body"]
        assert "payment provider and Cloudflare were never blocked" in mail["body"]
        # Only one of the three fix paragraphs.
        others = {
            ApplyMode.auto_when_checks_pass: "let us fix this kind of problem automatically",
            ApplyMode.approve_each: "approve fixes yourself",
            ApplyMode.never: "never touch your code",
        }
        for other_mode, other_needle in others.items():
            if other_mode is mode:
                continue
            assert other_needle not in mail["body"]


def test_three_fixture_clients_get_matching_paragraphs():
    """Three fixture clients — one per client mode — each get the matching paragraph."""
    fixtures = [
        ("00000000-0000-0000-0000-0000000000f1", ApplyMode.auto_when_checks_pass,
         "let us fix this kind of problem automatically"),
        ("00000000-0000-0000-0000-0000000000f2", ApplyMode.approve_each,
         "approve fixes yourself"),
        ("00000000-0000-0000-0000-0000000000f3", ApplyMode.never,
         "never touch your code"),
    ]
    critical = [{
        "stack": "PHP", "rating": "critical", "advisory_id": "CVE-2026-109618",
        "advisory_url": "https://example.test/cve",
    }]
    for tenant, mode, needle in fixtures:
        settings = ClientAutumbraSettings(
            tenant_id=tenant,
            site_name=f"fixture-{tenant[-2:]}.tervory.com",
            fix_mode=mode,
        )
        mail = build_owner_update(
            settings=settings,
            site_name=settings.site_name,
            threats_found=2,
            critical=critical,
            receipt_url="https://protect.tervory.com/receipts/r-fixture",
            pr_url="https://github.com/example/pr/1",
            fix_report_url="https://protect.tervory.com/report/1",
            undo_fix_url="https://protect.tervory.com/undo/fix",
        )
        assert needle in mail["body"]
        assert "Nothing from your logs was kept" in mail["body"]


def test_quiet_week_owner_email():
    settings = ClientAutumbraSettings(
        tenant_id="00000000-0000-0000-0000-0000000000q1",
        site_name="coolify.tervory.com",
    )
    mail = build_owner_update(
        settings=settings,
        site_name="coolify.tervory.com",
        threats_found=0,
        critical=[],
        checks_run=128,
        receipt_url="https://protect.tervory.com/receipts/quiet",
    )
    assert "Quiet week." in mail["body"]
    assert "128" in mail["body"]
    assert "0 threats" in mail["body"]
    assert "approve fixes yourself" not in mail["body"]


def test_advisory_links_appear_in_body():
    settings = ClientAutumbraSettings(
        tenant_id="00000000-0000-0000-0000-0000000000q2",
        fix_mode=ApplyMode.approve_each,
    )
    mail = build_owner_update(
        settings=settings,
        site_name="coolify.tervory.com",
        threats_found=1,
        critical=[{
            "stack": "PHP", "rating": "critical", "advisory_id": "CVE-2026-109618",
            "advisory_url": "https://example.test/cve",
        }],
        receipt_url="https://protect.tervory.com/receipts/r1",
        pr_url="https://github.com/example/pr/1",
    )
    assert "https://example.test/cve" in mail["body"]
    assert "CVE-2026-109618" in mail["body"]


def test_block_in_seconds_copy_gated_on_hand():
    bare = ClientAutumbraSettings(tenant_id="00000000-0000-0000-0000-0000000000h1")
    copy = connect_copy(bare)
    assert copy["block_in_seconds"] is None
    assert copy["block_in_seconds_gated"]
    assert "Pro" not in (copy.get("no_pro") or "")
    lit = set_hand(bare, "host_firewall", connected=True)
    lit_copy = connect_copy(lit)
    assert lit_copy["block_in_seconds"]
    assert lit_copy["block_in_seconds_gated"] is None
    assert active_halves(lit)["block_in_seconds"] is True


def test_agnostic_hands_catalog_no_required_provider():
    settings = ClientAutumbraSettings(tenant_id="00000000-0000-0000-0000-0000000000h2")
    hands = list_hands(settings)
    assert {h["hand"] for h in hands} >= {"cloudflare", "shopify", "host_firewall", "google_workspace"}
    assert all(h["required"] is False and h["pro_required"] is False for h in hands)


def test_owner_email_sender_is_called_for_three_fixture_clients():
    transport = FixtureEmailTransport()
    critical = [{
        "stack": "PHP", "rating": "critical", "advisory_id": "CVE-2026-109618",
        "advisory_url": "https://example.test/cve",
    }]
    fixtures = [
        ("00000000-0000-0000-0000-0000000000f1", ApplyMode.auto_when_checks_pass,
         "let us fix this kind of problem automatically", "auto@example.test"),
        ("00000000-0000-0000-0000-0000000000f2", ApplyMode.approve_each,
         "approve fixes yourself", "approve@example.test"),
        ("00000000-0000-0000-0000-0000000000f3", ApplyMode.never,
         "never touch your code", "never@example.test"),
    ]
    for tenant, mode, needle, to in fixtures:
        settings = ClientAutumbraSettings(
            tenant_id=tenant, site_name="fixture.tervory.com", fix_mode=mode, owner_email=to,
        )
        mail = build_owner_update(
            settings=settings,
            site_name=settings.site_name,
            threats_found=1,
            critical=critical,
            receipt_url="https://protect.tervory.com/r",
            pr_url="https://github.com/example/pr/1",
            fix_report_url="https://protect.tervory.com/report",
            undo_fix_url="https://protect.tervory.com/undo",
        )
        sent = send_owner_update(mail, to=to, transport=transport)
        assert sent["sent"] is True
        assert needle in sent["body"]
        assert "https://example.test/cve" in sent["body"]
    assert len(transport.sent) == 3
    assert {row["to"] for row in transport.sent} == {
        "auto@example.test", "approve@example.test", "never@example.test",
    }
