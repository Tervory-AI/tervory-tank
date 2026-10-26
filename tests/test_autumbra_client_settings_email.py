"""Client apply modes and owner update email paragraphs."""
from pathlib import Path

from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings, active_halves, load_settings, save_settings
from agents.ghost.owner_email import build_owner_update
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
