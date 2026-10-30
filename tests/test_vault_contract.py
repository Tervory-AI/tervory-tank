"""Validation never reflects submitted credential text; no network or DB."""
import secrets

import pytest
from fastapi import HTTPException

from vault_routes import clean, public_url, VAULTS


def test_existing_product_vault_names_are_bound_to_one_squad():
    assert VAULTS == {'base.vault': 'base', 'tiger.vault': 'tiger', 'rig.vault': 'rig', 'lab.vault': 'market_lab', 'tisan.vault': 'tisan', 'radix.vault': 'radix', 'zenas.vault': 'zenas'}


@pytest.mark.parametrize('kind', ['newline', 'too_long', 'wrong_type'])
def test_credential_validation_does_not_echo_value(kind):
    value = secrets.token_hex(32)
    invalid = value + '\n' if kind == 'newline' else value * 1000 if kind == 'too_long' else {'private': value}
    with pytest.raises(HTTPException) as caught:
        clean(invalid)
    assert value not in str(caught.value.detail)


@pytest.mark.parametrize('address', ['http://example.com/', 'https://localhost/', 'https://127.0.0.1/', 'https://10.0.0.1/', 'https://example.com/?key=not-a-key', 'https://example.com/#private', 'https://user@example.com/'])
def test_links_and_connections_require_public_https_without_credentials(address):
    with pytest.raises(HTTPException):
        public_url(address)


def test_readable_dataset_address_is_retained():
    assert public_url('https://example.com/reports/market.pdf') == 'https://example.com/reports/market.pdf'
