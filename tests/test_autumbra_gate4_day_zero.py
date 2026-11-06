from pathlib import Path
import subprocess

from agents.ghost.client_settings import ClientAutumbraSettings
from agents.ghost.owner_email import build_owner_update


def test_actual_day_zero_pages_and_data_readers():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(["node", "tests/autumbra_gate4_ui.cjs"], cwd=root, check=True, timeout=60)


def test_new_owner_email_has_zero_counts_first_action_and_no_claimed_work():
    result = build_owner_update(settings=ClientAutumbraSettings(tenant_id="new-client"),
        site_name="", threats_found=0, critical=[], checks_run=0)
    assert "0 threats found, 0 critical" in result["subject"]
    assert "0 actions" in result["body"]
    assert "Connect your site's log feed to start a check." in result["body"]
    assert "acted" not in result["body"]
    assert "1,204" not in result["body"]


def test_quiet_existing_client_retains_real_counts_without_claiming_actions():
    result = build_owner_update(settings=ClientAutumbraSettings(tenant_id="existing-client"),
        site_name="", threats_found=0, critical=[], checks_run=27)
    assert "27" in result["body"] and "0 actions" in result["body"]
    assert "start a check" not in result["body"]
    assert "acted" not in result["body"]
