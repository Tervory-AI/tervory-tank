"""Rehearse the actual Skala handlers in disposable data with fake providers."""
import argparse
import json
import os

import check

JOBS = {
    'intake': (('TANK_KEY_TRIGGER',), [
        'tests/skala_intake/test_intake.py::test_each_package_meets_real_skala_gate',
        'tests/skala_intake/test_intake.py::test_persisted_ready_bulk_approval_room_execution_tenant_scope_and_rollback']),
    'revalidation': (('DATABASE_URL', 'TANK_API_KEY', 'LITELLM_MASTER_KEY'), [
        'tests/skala_b3_b4/test_lifecycle.py::test_upsert_runs_exactly_affected_approved_skills_once',
        'tests/skala_b3_b4/test_lifecycle.py::test_graduation_to_code_calls_no_model',
        'tests/skala_b3_b4/test_lifecycle.py::test_background_worker_drains_policy_swap_and_stops_before_pool']),
    'collect': (('DATABASE_URL',), [
        'tests/test_skala_gate4_jobs.py::test_dry_run_collector_reads_receipts_and_resumes']),
    'gold': (('DATABASE_URL',), [
        'tests/test_skala_finish_jobs.py::test_trigger_package_gold_can_be_reviewed_without_models',
        'tests/test_skala_finish_jobs.py::test_gold_schedule_retries_partial_sources_and_records_one_completion']),
    'retest': (('DATABASE_URL',), [
        'tests/test_skala_finish_jobs.py::test_weekly_retest_records_real_code_score_and_keeps_holdouts_out']),
    'export': (('HF_TOKEN', 'HF_ORG'), [
        'tests/test_skala_gate4_jobs.py::test_dry_run_export_archives_exact_payload_before_private_upload',
        'tests/test_skala_gate4_jobs.py::test_missing_archive_setting_blocks_hf_and_keeps_retryable_receipt',
        'tests/test_skala_finish_jobs.py::test_private_export_retries_without_repeating_completed_agents']),
    'training': (('HF_TOKEN', 'HF_ORG'), [
        'tests/test_skala_gate4_jobs.py::test_dry_run_training_start_stops_before_launch',
        'tests/test_skala_gate4_jobs.py::test_dry_run_training_receipt_records_actual_bill_once',
        'tests/test_skala_gate4_jobs.py::test_training_command_names_missing_settings_before_provider_access',
        'tests/test_skala_gate4_jobs.py::test_training_cli_rejects_dry_run_with_submit']),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.add_argument('--job', choices=['all', *JOBS], default='all')
    args = parser.parse_args()
    chosen = list(JOBS) if args.job == 'all' else [args.job]
    missing = {name: [key for key in JOBS[name][0] if not os.environ.get(key, '').strip()] for name in chosen}
    check.CACHE.mkdir(exist_ok=True)
    check.LOGS.mkdir(exist_ok=True)
    check.vendor.verify()
    selectors = sorted({node for name in chosen for node in JOBS[name][1]})
    with check.runtime_tree(check.product_files(), check.node_modules()) as tree:
        report = check.pytest(tree, selectors, 'product')
    jobs = []
    for name in chosen:
        matches = {node: outcome for node, outcome in report['results'].items()
            if any(node == selector or node.startswith(selector + '[') for selector in JOBS[name][1])}
        complete = all(any(node == selector or node.startswith(selector + '[') for node in matches)
                       for selector in JOBS[name][1])
        jobs.append({'job': name, 'checks': len(matches),
            'status': 'passed' if complete and all(value == 'passed' for value in matches.values()) else 'failed',
            'missing_settings': missing[name]})
    result = {'mode': 'dry-run', 'data': 'disposable', 'providers': 'fake', 'jobs': jobs}
    (check.LOGS / 'dry-run.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if report['exitstatus'] == 0 and all(job['status'] == 'passed' for job in jobs) else 1


if __name__ == '__main__':
    raise SystemExit(main())
