"""Trigger sign-in acceptance: maintained OIDC integration and both native regions."""
from pathlib import Path
import os
import subprocess

import pytest

import test_command as command_proofs
import test_device_login as device_proofs

command_pool = command_proofs.command_pool
runtime = command_proofs.runtime
device = device_proofs.device
signin_provider = device_proofs.signin_provider

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def require_disposable_database():
    assert os.environ.get('POOL_SCHEMA_DATABASE_URL'), 'Trigger sign-in acceptance requires disposable PostgreSQL'


@pytest.mark.parametrize('row', ['S01', 'S02', 'S03', 'S06'])
def test_workspace_signin_signout_switch_and_founder_boundary(row):
    result = subprocess.run(['node', 'tests/acceptance/trigger_signin.cjs', row], cwd=ROOT,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert row + ' passed' in result.stdout
    if row == 'S06':
        page = subprocess.run(['node', 'tests/tank_founder_boundary.cjs'], cwd=ROOT,
                              capture_output=True, text=True, timeout=90)
        assert page.returncode == 0, page.stdout + page.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize('signin_provider', ['us-east'], indirect=True)
async def test_s04_cli_us_native_device_signin_and_signout(device, signin_provider):
    await device_proofs.test_native_grant_logout_and_region_boundary(device, signin_provider)


@pytest.mark.asyncio
@pytest.mark.parametrize('signin_provider', ['za'], indirect=True)
async def test_s05_cli_za_native_device_signin_and_signout(device, signin_provider):
    await device_proofs.test_native_grant_logout_and_region_boundary(device, signin_provider)
