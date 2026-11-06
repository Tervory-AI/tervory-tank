#!/usr/bin/env python3
"""Run Trigger's scheduled/data paths against disposable, offline fixtures."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ('DATABASE_URL', 'TANK_KEY', 'TANK_API_KEY', 'TRIGGER_SIGNIN_WORKSPACE_SECRET',
    'TRIGGER_CRM_URL', 'TRIGGER_CRM_TENANT_BINDINGS', 'TRIGGER_CRM_PAT_CONNECTOR',
    'TRIGGER_GOOGLE_OAUTH_CLIENT_ID', 'TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET',
    'TRIGGER_META_APP_ID', 'TRIGGER_META_APP_SECRET', 'TANK_VAULT_KEY',
    'TRIGGER_WHATSAPP_APP_SECRET', 'TRIGGER_WHATSAPP_VERIFY_TOKEN',
    'TRIGGER_WHATSAPP_TOKEN_CONNECTOR', 'TRIGGER_WHATSAPP_BINDINGS',
    'TRIGGER_BOT_HANDOVER_ADDRESSES', 'TRIGGER_BOT_TRUSTED_PROXY_CIDRS',
    'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM')


def missing_settings():
    return [name for name in SETTINGS if not os.environ.get(name)]


TARGETS = [
    'tests/test_trigger_crm.py', 'tests/trigger_bot_b1/test_rig_bridge.py',
    'tests/trigger_w4/test_console_widget.py::test_rig_keeps_request_metadata_without_inventing_a_price',
    'tests/trigger_first_build/test_trigger.py::test_real_free_checkers_find_issues',
    'tests/trigger_first_build/test_trigger.py::test_check_calls_only_internal_checker_and_preserves_text',
    'tests/trigger_m1/test_m1_queue.py', 'tests/trigger_m1/test_m1_delivery.py',
    'tests/trigger_m1/test_m1_reconcile.py', 'tests/trigger_m1/test_m1_metrics.py',
    'tests/trigger_m2/test_meta.py', 'tests/trigger_bot_b1/test_retention.py',
    'tests/trigger_bot_b1/test_database.py::test_hybrid_index_rechecks_tenant_staleness_and_source_removal',
    'tests/trigger_bot_b1/test_database.py::test_bot_policy_reuses_writing_route_and_faq_records_zero_cost',
    'tests/trigger_bot_b3/test_whatsapp.py', 'tests/test_trigger_w1.py',
    'tests/trigger_finish/test_jobs_and_sources.py',
]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.parse_args(argv)
    # Never inherit a production DSN or provider credentials into the fixture runner.
    env = {k: v for k, v in os.environ.items() if not (k.endswith('DATABASE_URL') or
        k.startswith(('TRIGGER_', 'SMTP_', 'TANK_')) or k in {'DATABASE_URL', 'LITELLM_MASTER_KEY'})}
    try:
        from pgserver._commands import POSTGRES_BIN_PATH
        with tempfile.TemporaryDirectory(prefix='trigger-dry-run-') as temp:
            base = Path(temp)
            data, stage = base / 'postgres', base / 'source'
            vendor = ROOT / 'vendor/tervory-tank'
            if vendor.is_dir():
                shutil.copytree(vendor, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            else:
                stage.mkdir()
            files = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard'], text=True).splitlines()
            for name in set(files):
                if name.startswith('vendor/') or not (ROOT / name).is_file():
                    continue
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, target)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            binaries = Path(POSTGRES_BIN_PATH)
            subprocess.run([str(binaries/'initdb'), '-D', str(data), '--auth=trust', '-U', 'postgres'], check=True, stdout=subprocess.DEVNULL)
            subprocess.run([str(binaries/'pg_ctl'), '-D', str(data), '-l', str(base/'postgres.log'),
                '-o', f'-h 127.0.0.1 -p {port} -k {base}', '-w', 'start'], check=True, stdout=subprocess.DEVNULL)
            try:
                env['POOL_SCHEMA_DATABASE_URL'] = f'postgresql://postgres@127.0.0.1:{port}/postgres'
                env['PYTHONPATH'] = os.pathsep.join(str(stage/p) for p in ('tests', 'agents', 'agents/_chassis', 'tank'))
                report = base / 'results.xml'
                result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rs', '-p', 'no:cacheprovider',
                    '--disable-socket', '--allow-unix-socket', '--allow-hosts=127.0.0.1,localhost',
                    '--timeout=90', '--junitxml='+str(report), *TARGETS], cwd=stage, env=env)
                cases = list(ET.parse(report).iter('testcase')) if report.exists() else []
                skipped = sum(case.find('skipped') is not None for case in cases)
                success = result.returncode == 0 and bool(cases) and not skipped
                print(json.dumps({'dry_run': True, 'ok': success, 'cases': len(cases), 'skipped': skipped,
                    'missing_settings': missing_settings(),
                    'scheduled_jobs': ['publication', 'reconciliation', 'retention', 'source refresh', 'WhatsApp month/window'],
                    'data_runs': ['CRM', 'website', 'document', 'FAQ', 'Rig', 'Google', 'Facebook', 'writing checks'],
                    'training': 'Private approved feedback pairs; Trigger has no standalone training launch.'}))
                return 0 if success else 1
            finally:
                subprocess.run([str(binaries/'pg_ctl'), '-D', str(data), '-m', 'fast', '-w', 'stop'], check=True, stdout=subprocess.DEVNULL)
    except (ImportError, OSError, subprocess.CalledProcessError) as error:
        print(json.dumps({'dry_run': True, 'ok': False, 'missing_prerequisite': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
