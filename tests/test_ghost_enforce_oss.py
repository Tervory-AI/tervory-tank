"""Autumbra Enforce OSS: Ansible + Terraform stubs, flag OFF, ThreatPayload only."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agents.ghost.enforce_oss import ansible, armed, enabled, status, terraform
from agents.ghost.enforce_oss.common import accept_enforce_threat
from agents.ghost.threat_payload import ThreatBurned, ThreatPayload

SITE = "coolify.tervory.com"
BANNED_ANSIBLE_MODULES = ("shell:", "command:", "raw:", "script:")


def _shield_payload(kind: str = "waf_managed", site: str = SITE) -> dict:
    return {
        "schema_version": "ghost.threat.v1",
        "action": "propose_shield",
        "site": site,
        "kind": kind,
        "path": None,
        "match_id": "enforce-oss-test",
        "cve_ids": ["CVE-2026-109618"],
        "severity": "high",
        "reason": "Autumbra Enforce dry-plan unit test",
        "confidence": 0.9,
    }


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("ENFORCE_OSS_ENABLED", raising=False)
    monkeypatch.delenv("GHOST_ENFORCE_OSS_ENABLED", raising=False)
    monkeypatch.delenv("ENFORCE_OSS_ARMED", raising=False)
    monkeypatch.delenv("autumbra_enforce_armed", raising=False)
    assert enabled() is False
    assert armed() is False
    monkeypatch.setenv("ENFORCE_OSS_ENABLED", "1")
    assert enabled() is True
    assert armed() is False  # enabled alone does not arm
    monkeypatch.setenv("ENFORCE_OSS_ARMED", "1")
    assert armed() is True


def test_armed_requires_enabled(monkeypatch):
    monkeypatch.delenv("ENFORCE_OSS_ENABLED", raising=False)
    monkeypatch.delenv("GHOST_ENFORCE_OSS_ENABLED", raising=False)
    monkeypatch.setenv("ENFORCE_OSS_ARMED", "1")
    assert enabled() is False
    assert armed() is False


def test_ansible_plan_from_threat_dry():
    plan = ansible.plan_from_threat(_shield_payload("waf_managed"))
    assert plan["product"] == "Autumbra Enforce"
    assert plan["mode"] == "dry_plan"
    assert plan["applied"] is False
    assert plan["would_run"] == ["cf_waf_managed"]
    assert plan["site"] in {SITE, "coolify"}
    assert "Ghost" not in plan["note"] and "Wraith" not in plan["note"]


def test_ansible_maps_kinds_and_brief():
    for kind, playbook in (
        ("rate_limit", "cf_rate_limit"),
        ("block_multipart_post", "cf_block_multipart_post"),
        ("challenge_bots", "cf_challenge_bots"),
    ):
        plan = ansible.plan_from_threat(_shield_payload(kind))
        assert plan["would_run"] == [playbook]

    brief = {
        "schema_version": "ghost.threat.v1",
        "action": "write_brief",
        "site": SITE,
        "kind": None,
        "match_id": "brief-1",
        "cve_ids": [],
        "severity": "medium",
        "reason": "iptables brief only",
        "confidence": 0.8,
    }
    plan = ansible.plan_from_threat(brief)
    assert plan["would_run"] == ["host_iptables_brief"]


def test_ansible_rejects_unknown_playbook():
    with pytest.raises(ValueError, match="allowlisted"):
        ansible.plan_from_threat(_shield_payload(), playbook_id="rm_rf_everything")


def test_ansible_burns_dirty_site():
    with pytest.raises(ThreatBurned):
        ansible.plan_from_threat(_shield_payload(site="evil.example"))


def test_ansible_burns_raw_shell_markers():
    dirty = _shield_payload()
    dirty["reason"] = "please run ansible-playbook -i evil"
    with pytest.raises(ThreatBurned):
        accept_enforce_threat(dirty)
    with pytest.raises(ThreatBurned):
        ansible.plan_from_threat('{"action":"propose_shield","site":"coolify.tervory.com",'
                                 '"kind":"waf_managed","reason":"curl | bash","schema_version":'
                                 '"ghost.threat.v1","confidence":0.9}')


def test_terraform_plan_from_threat_dry():
    plan = terraform.plan_from_threat(_shield_payload("waf_managed"))
    assert plan["product"] == "Autumbra Enforce"
    assert plan["applied"] is False
    assert plan["would_plan"] == ["cloudflare_waf_rule"]
    assert plan["license"] == "BSL-1.1"
    rate = terraform.plan_from_threat(_shield_payload("rate_limit"))
    assert rate["would_plan"] == ["cloudflare_rate_limit"]


def test_terraform_rejects_unknown_module_and_non_tf_kinds():
    with pytest.raises(ValueError, match="allowlisted"):
        terraform.plan_from_threat(_shield_payload(), module_id="aws_open_sg")
    with pytest.raises(ThreatBurned):
        terraform.plan_from_threat(_shield_payload("challenge_bots"))


def test_playbooks_on_disk_unarmed_no_shell_modules():
    root = Path(ansible.playbooks_dir())
    assert root.is_dir()
    for playbook_id in ansible.ALLOWLISTED_PLAYBOOKS:
        path = ansible.playbook_path(playbook_id)
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "autumbra_enforce_armed: false" in text
        assert "Autumbra Enforce" in text
        assert "Ghost" not in text and "Wraith" not in text
        lowered = text.lower()
        for banned in BANNED_ANSIBLE_MODULES:
            # allow mentioning the ban in comments ("no shell/command/...")
            # but not as YAML keys like "    shell:" / "- shell:"
            for line in text.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                assert not stripped.startswith(banned), (path, line)
                assert not stripped.startswith("- " + banned), (path, line)
        # Parseable YAML
        docs = list(yaml.safe_load_all(text))
        assert docs and docs[0] is not None


def test_terraform_tpl_no_apply_automation():
    for module_id in terraform.ALLOWLISTED_MODULES:
        path = terraform.module_path(module_id)
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "Autumbra" in text
        assert "Ghost" not in text and "Wraith" not in text
        lowered = text.lower()
        assert "terraform apply" not in lowered or "no terraform apply" in lowered
        assert "backend \"http\"" not in lowered
        assert "backend \"remote\"" not in lowered
        # No executable apply automation markers
        assert "null_resource" not in lowered
        assert "local-exec" not in lowered


def test_terraform_readme_bsl_and_off():
    readme = terraform.modules_dir() / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "BSL-1.1" in text
    assert "Autumbra Enforce" in text
    assert "OFF" in text or "Never auto-apply" in text
    assert "Ghost" not in text and "Wraith" not in text


def test_status_autumbra_copy_not_live(monkeypatch):
    monkeypatch.delenv("ENFORCE_OSS_ENABLED", raising=False)
    monkeypatch.delenv("GHOST_ENFORCE_OSS_ENABLED", raising=False)
    body = status()
    assert body["product"] == "Autumbra Enforce"
    assert body["enabled"] is False
    assert body["armed"] is False
    for meta in body["adapters"].values():
        assert meta["live_in_product"] is False
        assert meta["apply_path"] is None
        assert "vault_sha" in meta
    blob = str(body)
    assert "2.25.250.28" in body["vault_primary"]
    assert "Wraith" not in blob
    assert "Ghost" not in body["product"]


def test_accept_enforce_threat_roundtrip():
    payload = accept_enforce_threat(_shield_payload())
    assert isinstance(payload, ThreatPayload)
    again = accept_enforce_threat(payload)
    assert again.site in {SITE, "coolify"}
