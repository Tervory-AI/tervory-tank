from decimal import Decimal
import json
from pathlib import Path

import pytest
from training_jobs import round_one
import tervor_dataset
import tervor_registry

ROOT = Path(__file__).resolve().parents[1]


def fixture_bundle(product):
    tenant = round_one.PLATFORM
    rows = [tervor_dataset.row(tenant=tenant, product=product, kind='public',
        source='synthetic pipeline fixture', provider='Tervory', licence='counsel pending', source_ref=str(i),
        task_type=product+'.answer', input={'text': 'training fixture '+str(i)}, output={'answer': str(i)}) for i in range(20)]
    cases = [dict(input={'text': 'held-out fixture '+str(i)}, expected={'answer': str(i)},
                  task_type=product+'.answer', holdout=True) for i in range(200)]
    gold = dict(tenant_id=str(tenant), product=product, region='za' if product=='zenas' else 'us-east',
                cases=cases, count=200, sha256=tervor_registry.digest(cases), holdout=True)
    return round_one.bundle(tenant, product, rows, gold)


@pytest.mark.asyncio
async def test_full_recorded_77611_ffl_base_to_tiger_and_resume_without_paid_jobs(tmp_path):
    datasets = tmp_path/'sets'
    datasets.mkdir()
    for product in round_one.PRODUCTS:
        (datasets/(product+'.json')).write_text(json.dumps(fixture_bundle(product)))
    report = await round_one.dry_run(ROOT/'tests/fixtures/base-atf/0925-ffl-list-complete.txt.gz',
        tmp_path/'checkpoint', datasets, version='tervor-lite-1.0', day='2026-11-07',
        rate=Decimal('0.016667'), minutes=120)
    assert report['paid_jobs'] == 0
    assert report['ffl']['source_records'] == report['ffl']['base_records'] == report['ffl']['tiger_receipts'] == 77611
    assert report['ffl']['states'] == 55 and report['ffl']['smallest_state'] == 'DC'
    assert report['ffl']['resume_verified'] and report['ffl']['external_requests'] == 0
    assert report['ffl']['model_cost_usd'] == 0
    assert report['ffl']['source_status'] == {'no_product_urls': 77611}
    assert report['compute_ceiling_usd'] == '6.000120'
    assert {p['model_id'] for p in report['adapters']} == {
        f'tervor-lite-1.0-{product}-20261107' for product in round_one.PRODUCTS}
    assert all(p['compute_ceiling_usd']=='2.000040' and not p['submitted'] for p in report['adapters'])


def test_round_one_rejects_gold_overlap_and_bad_quote():
    prepared = fixture_bundle('base')
    rows = prepared['training']['rows']
    rows[0]['input'] = prepared['gold']['cases'][0]['input']
    with pytest.raises(ValueError, match='Gold input'):
        round_one.bundle(round_one.PLATFORM, 'base', rows, prepared['gold'])
    for rate in (Decimal('NaN'), Decimal('-1'), Decimal(0)):
        with pytest.raises(ValueError, match='quoted rate'):
            round_one.adapter_plan('base', fixture_bundle('base'), version='tervor-lite-1.0',
                day='2026-11-07', rate=rate, minutes=120)
