"""Reuse Tiger's loopback mailbox and isolate every named external setting."""
import pytest
from test_tiger_alert_email import catcher as catcher


@pytest.fixture(autouse=True)
def no_live_configuration(monkeypatch):
    for name in (
        "ZENAS_SMTP_HOST", "ZENAS_SMTP_PORT", "ZENAS_SMTP_FROM", "ZENAS_SMTP_USER",
        "ZENAS_SMTP_PASSWORD", "ZENAS_SMTP_ALERT_ADDRESSES", "CONGRESS_GOV_API_KEY",
        "LEGISCAN_API_KEY", "LAWS_AFRICA_API_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
