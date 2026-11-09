#!/usr/bin/env python3
"""Opt-in isolated Redis proof; never points at a production Docker daemon."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ['docker','--host=unix:///var/run/docker.sock']
SELECTORS = ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')


def docker(*args,timeout=30,check=True):
    env = {k:v for k,v in os.environ.items() if k not in SELECTORS}
    result = subprocess.run([*DOCKER,*args],env=env,capture_output=True,text=True,timeout=timeout,check=False)
    if check and result.returncode:
        raise RuntimeError('Managed-local Docker operation failed')
    return result


def source_matches(pins):
    ref=pins['source_commit']
    if not re.fullmatch('[a-f0-9]{40}',ref):
        raise ValueError('Recorded source requires a full commit SHA')
    files={}
    for name,expected in pins['source_sha256'].items():
        if Path(name).name!=name:
            raise ValueError('Unexpected source path')
        content=subprocess.run(['git','show',ref+':litellm/'+name],cwd=ROOT,
            capture_output=True,check=True).stdout
        if hashlib.sha256(content).hexdigest()!=expected:
            raise ValueError('Deployed callback/config source hash mismatch')
        files[name]=content
    return files


def extract_report(stdout):
    records = [line.split('=',1)[1] for line in stdout.splitlines() if line.startswith('CACHE_ACCEPTANCE_REPORT=')]
    if len(records)!=1:
        raise ValueError('Missing or duplicate acceptance report')
    result = json.loads(records[0])
    if result.get('passed') is not True or result.get('production_outage_proof') is not False or len(result.get('cases',[]))!=9:
        raise ValueError('Incomplete isolated acceptance')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-isolated',required=True,action='store_true')
    parser.add_argument('--pull',action='store_true')
    parser.add_argument('--candidate-ref',help='Full local commit SHA; replace only the callback source for candidate proof')
    args = parser.parse_args()
    if args.candidate_ref and not re.fullmatch('[a-f0-9]{40}',args.candidate_ref):
        raise ValueError('Candidate requires a full commit SHA')
    pins = json.loads((ROOT/'tools/cache_redis/pins.json').read_text())
    source_files=source_matches(pins)
    for image in (pins['gateway_image'],pins['redis_image']):
        if '@sha256:' not in image:
            raise ValueError('Immutable image digest required')
    run_id = uuid.uuid4().hex[:12]
    prefix = ROOT.name+'-'+run_id
    network,redis,gateway = prefix+'-network',prefix+'-redis',prefix+'-gateway'
    directory = ROOT/'.checks/cache-redis'
    directory.mkdir(parents=True,exist_ok=True)
    report = {'passed':False,'scope':'isolated-pinned-base-image-and-deployed-source-equivalence',
        'production_outage_proof':False,'production_settings_changed':False,'pins':pins,
        'harness_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('tank/cache_redis_probe.py','scripts/cache_redis_acceptance.py')},
        'bounds':{'pull_seconds_per_image':600,'probe_seconds':600,'gateway_cpus':2,'gateway_memory':'2g',
                  'redis_cpus':1,'redis_memory':'128m','cold_request_seconds':70}}
    snapshot = tempfile.TemporaryDirectory(prefix='gateway-source-',dir=directory)
    source = Path(snapshot.name)
    source.chmod(0o755)
    for name in pins['source_sha256']:
        destination=source/name
        destination.write_bytes(source_files[name])
        destination.chmod(0o444)
    if args.candidate_ref:
        candidate=subprocess.run(['git','show',args.candidate_ref+':litellm/tenant_traces.py'],
            cwd=ROOT,capture_output=True,check=True).stdout
        leaf=source/'tenant_traces.py'
        leaf.unlink();leaf.write_bytes(candidate);leaf.chmod(0o444)
        report['candidate_callback_ref']=args.candidate_ref
        report['candidate_callback_sha256']=hashlib.sha256(candidate).hexdigest()
        report['source_mode']='explicit-callback-source-override'
        report['candidate_deployment_status']='not-verified-by-harness'
    else:
        report['source_mode']='recorded-source-control'
    report['effective_source_sha256']={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in pins['source_sha256']}
    probe=source/'probe.py'
    probe.write_bytes((ROOT/'tank/cache_redis_probe.py').read_bytes())
    probe.chmod(0o444)
    try:
        report['phase']='daemon-and-images'
        docker('info','--format','{{.ServerVersion}}')
        if args.pull:
            for image in (pins['gateway_image'],pins['redis_image']):
                docker('pull',image,timeout=600)
        report['local_image_ids'] = {name:docker('image','inspect',pins[name+'_image'],'--format','{{.Id}}').stdout.strip()
                                     for name in ('gateway','redis')}
        docker('network','create','--internal','--label','tervory.test=1','--label','tervory.acceptance='+run_id,network)
        report['internal_network'] = docker('network','inspect',network,'--format','{{.Internal}}').stdout.strip()=='true'
        if not report['internal_network']:
            raise ValueError('Internal-only network required')
        common = ['--rm','--label','tervory.test=1','--label','tervory.acceptance='+run_id,
                  '--network',network,'--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=128']
        report['phase']='redis-startup'
        docker('run','-d',*common,'--name',redis,'--network-alias','redis','--cpus=1','--memory=128m',
               '--user','999:999','--read-only','--tmpfs','/data:rw,noexec,nosuid,size=64m,mode=1777',pins['redis_image'],
               'redis-server','--bind','0.0.0.0','--save','','--appendonly','no')
        for _ in range(30):
            if docker('exec',redis,'redis-cli','ping',timeout=3,check=False).stdout.strip()=='PONG':
                break
            time.sleep(.2)
        else:
            raise TimeoutError('Disposable Redis startup failed')
        report['phase']='gateway-proof'
        command = ['run',*common,'--name',gateway,'--cpus=2','--memory=2g','--read-only',
            '--tmpfs','/tmp:rw,nosuid,size=256m','--user','10001:10001',
            '--mount',f'type=bind,source={source},target=/contract/source,readonly',
            '--mount',f'type=bind,source={probe},target=/contract/probe.py,readonly',
            '--env','PYTHONPATH=/contract/source','--env','ENGINE_C1_ENABLED=1',
            '--env','LITELLM_LOCAL_MODEL_COST_MAP=True','--env','LITELLM_LOG=ERROR',
            '--env','PYTHONDONTWRITEBYTECODE=1']
        for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
            command += ['--env',name+'=']
        command += ['--env','NO_PROXY=*','--env','no_proxy=*','--entrypoint','python',pins['gateway_image'],'/contract/probe.py']
        result = docker(*command,timeout=600,check=False)
        (directory/'gateway.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError('Isolated gateway probe failed; inspect task-local gateway.log')
        report.update(extract_report(result.stdout),phase='complete')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(passed=False,error_type=type(error).__name__)
    finally:
        for name in (gateway,redis):
            owner = docker('inspect',name,'--format','{{index .Config.Labels "tervory.acceptance"}}',check=False)
            if owner.returncode==0 and owner.stdout.strip()==run_id:
                docker('rm','-f',name,check=False)
        owner = docker('network','inspect',network,'--format','{{index .Labels "tervory.acceptance"}}',check=False)
        if owner.returncode==0 and owner.stdout.strip()==run_id:
            docker('network','rm',network,check=False)
        snapshot.cleanup()
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
