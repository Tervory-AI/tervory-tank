"""Focused acceptance guard tests; no containers, providers or Redis in unit CI."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from cache_redis_probe import validate_case


@pytest.fixture
def driver():
    spec=importlib.util.spec_from_file_location('redis_acceptance_driver','scripts/cache_redis_acceptance.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('hit,cost,calls',[(False,'.00002',1),(True,'0',1)])
def test_truthful_cache_and_synthetic_price_signals(hit,cost,calls):
    result={'status':200,'version':'1.106.4','cache_layer':'C1' if hit else None,'synthetic_cost_header':cost}
    validate_case(result,hit=hit,calls=calls,expected_calls=1)


@pytest.mark.parametrize('change',[
    {'cache_layer':'C1'},{'synthetic_cost_header':'0'},{'status':500},{'version':'0.0.0'},
])
def test_unavailable_redis_cannot_claim_a_hit_or_free_upstream(change):
    result={'status':200,'version':'1.106.4','cache_layer':None,'synthetic_cost_header':'.00002',**change}
    with pytest.raises(AssertionError):
        validate_case(result,hit=False,calls=2,expected_calls=2)


def test_reuse_requires_no_extra_upstream_call():
    result={'status':200,'version':'1.106.4','cache_layer':'C1','synthetic_cost_header':'0'}
    with pytest.raises(AssertionError):
        validate_case(result,hit=True,calls=2,expected_calls=1)


def test_driver_ignores_remote_docker_selectors_and_keeps_registry_config(driver,monkeypatch):
    for name in driver.SELECTORS:
        monkeypatch.setenv(name,'placeholder-remote-forbidden')
    monkeypatch.setenv('DOCKER_CONFIG','placeholder-registry-config')
    seen=[]
    def run(command,**kwargs):
        seen.append((command,kwargs))
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(driver.subprocess,'run',run)
    driver.docker('info')
    command,kwargs=seen[0]
    assert command[:2]==['docker','--host=unix:///var/run/docker.sock']
    assert all(name not in kwargs['env'] for name in driver.SELECTORS)
    assert kwargs['env']['DOCKER_CONFIG']=='placeholder-registry-config'
    assert kwargs['timeout']==30 and kwargs['capture_output'] is True


def test_source_equivalence_is_hash_checked_before_execution(driver):
    pins=json.loads(Path('tools/cache_redis/pins.json').read_text())
    driver.source_matches(pins)
    altered=deepcopy(pins)
    altered['source_sha256']['response_cache.py']='0'*64
    with pytest.raises(ValueError,match='source hash mismatch'):
        driver.source_matches(altered)
    assert '@sha256:' in pins['gateway_image'] and '@sha256:' in pins['redis_image']
    assert pins['reported_deployed_image_id']!='sha256:5aba1de29b3469c13b842102b0820f654e4d3288c2ad56559f1506e25334a4a1'


@pytest.mark.parametrize('change',[{'passed':False},{'production_outage_proof':True},{'cases':[]}])
def test_missing_or_wrong_scope_evidence_fails_closed(driver,change):
    result={'passed':True,'production_outage_proof':False,'cases':[{}]*9,**change}
    with pytest.raises(ValueError):
        driver.extract_report('CACHE_ACCEPTANCE_REPORT='+json.dumps(result))
    with pytest.raises(ValueError):
        driver.extract_report('no report')


def test_duplicate_report_rejected(driver):
    result=json.dumps({'passed':True,'production_outage_proof':False,'cases':[{}]*9})
    with pytest.raises(ValueError):
        driver.extract_report('CACHE_ACCEPTANCE_REPORT='+result+'\nCACHE_ACCEPTANCE_REPORT='+result)


@pytest.mark.parametrize('seconds,enabled,expected',[(5,True,5.5),(0,False,0),(90,True,90.5)])
def test_recovery_wait_uses_sdk_setting_without_overriding_it(seconds,enabled,expected):
    from cache_redis_probe import recovery_delay
    assert recovery_delay({'redis_breaker':{'recovery_timeout':seconds,'enabled':enabled}})==expected


@pytest.mark.parametrize('seconds',[float('nan'),-1,91,'unbounded'])
def test_recovery_wait_is_bounded(seconds):
    from cache_redis_probe import recovery_delay
    with pytest.raises(ValueError):
        recovery_delay({'redis_breaker':{'recovery_timeout':seconds,'enabled':True}})


def test_recorded_source_is_reproducible_after_a_callback_merge(driver,monkeypatch):
    pins=json.loads(Path('tools/cache_redis/pins.json').read_text())
    files=driver.source_matches(pins)
    assert set(files)==set(pins['source_sha256'])
    calls=[]
    original=driver.subprocess.run
    def git_only(command,**kwargs):
        calls.append(command)
        return original(command,**kwargs)
    monkeypatch.setattr(driver.subprocess,'run',git_only)
    driver.source_matches(pins)
    assert all(command[:2]==['git','show'] for command in calls)
    assert all(command[2].startswith(pins['source_commit']+':litellm/') for command in calls)
