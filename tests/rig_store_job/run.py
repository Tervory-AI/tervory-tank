"""Disposable cloud-only real Tank job. Requires local Docker, Node, Chromium, openssl."""
import base64
import json
import os
import secrets
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
PROOF = Path(tempfile.mkdtemp(prefix='rig-store-job-'))
PREFIX = 'rig-job-' + secrets.token_hex(4)
DOCKER = ['docker', '--host=unix:///var/run/docker.sock']
ENV = {k:v for k,v in os.environ.items() if k not in {'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'}}
ENV['BUILDX_CONFIG'] = str(PROOF/'buildx')
ENV['npm_config_cache'] = str(PROOF/'npm-cache')
containers = []


def command(args, **kwargs):
    return subprocess.run(args, env=ENV, cwd=ROOT, check=True, **kwargs)


def docker(*args):
    return command(DOCKER + list(args), capture_output=True, text=True).stdout.strip()


def envfile(name, values):
    target = PROOF/(name+'.env')
    target.write_text(''.join(f'{k}={v}\n' for k,v in values.items()))
    target.chmod(0o600)
    return str(target)


def start(role, *args):
    name = PREFIX+'-'+role
    docker('run','-d','--name',name,'--network',PREFIX,*args)
    containers.append(name)
    return name


def wait_health(url):
    local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(60):
        try:
            with local.open(url+'/health',timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError('Fixture service did not become healthy')


def main():
    print('Evidence directory:',PROOF,flush=True)
    image='rig-store-job-runtime'
    ca=os.environ.get('CODEX_PROXY_CERT','/etc/ssl/certs/ca-certificates.crt')
    with (PROOF/'build.log').open('w') as log:
        command(DOCKER+['build','--secret','id=proxy_ca,src='+ca,'-f','tests/rig_store_job/Dockerfile','-t',image,'.'],stdout=log,stderr=subprocess.STDOUT)
    command(['npm','install','--prefix',str(PROOF/'browser'),'--no-audit','--no-fund','--ignore-scripts','esbuild@0.28.2','playwright@1.64.1'],stdout=subprocess.DEVNULL)
    database_credential=secrets.token_hex(32)
    internal='tank,agent-rig,postgres,redis,mail,localhost,127.0.0.1'
    common={'DATABASE_URL':f'postgresql://tervory:{database_credential}@postgres:5432/tervory',
        'TANK_API_KEY':secrets.token_hex(32),'TANK_KEY_RIG':secrets.token_hex(32),
        'RIG_RETAILER_KEY':secrets.token_hex(32),'LITELLM_MASTER_KEY':secrets.token_hex(32),
        'TANK_VAULT_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'TANK_REGION':'us-east','NO_PROXY':internal,'no_proxy':internal}
    common_file=envfile('common',common)
    pg_file=envfile('postgres',{'POSTGRES_USER':'tervory','POSTGRES_DB':'tervory','POSTGRES_PASSWORD':database_credential})
    rig_file=envfile('rig',{**common,'TANK_URL':'http://tank:8000','TANK_KEY':common['TANK_KEY_RIG'],
        'DATA_DIR':'/tmp/rig-data','CATALOGUE_DIR':'/empty','RIG_TRUSTED_PROXY_CIDRS':'172.16.0.0/12',
        'SMTP_HOST':'mail','SMTP_PORT':'1025','SMTP_FROM':'quotes@rig.test','SSL_CERT_FILE':'/proof/mail.crt',
        'PYTHONPATH':'/repo/agents/_chassis:/repo/agents/rig'})
    (PROOF/'fixture.json').write_text(json.dumps({'store_a':str(uuid4()),'store_b':str(uuid4())}))
    command(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(PROOF/'mail.key'),'-out',str(PROOF/'mail.crt'),'-days','2','-subj','/CN=mail','-addext','subjectAltName=DNS:mail'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (PROOF/'mail.key').chmod(0o600)
    docker('network','create',PREFIX)
    mounts=['-v',str(ROOT)+':/repo:ro','-v',str(PROOF)+':/proof']
    try:
        pg=start('postgres','--network-alias','postgres','--env-file',pg_file,'postgres:16.15')
        start('redis','--network-alias','redis','redis:7.4.12@sha256:bd28fff4b665fdf1b73e8b5b73ec05d2f858f4fa3c8ea0d7c9bc09f7f6bf7039')
        for _ in range(40):
            try:
                docker('exec',pg,'pg_isready','-U','tervory')
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        start('mail','--network-alias','mail',*mounts,image,'python','/repo/tests/rig_store_job/mail.py')
        tank=start('tank','--network-alias','tank','--env-file',common_file,*mounts,'-w','/repo/tank','-p','127.0.0.1::8000',image,'uvicorn','main:app','--host','0.0.0.0','--port','8000','--no-access-log')
        rig=start('rig','--network-alias','agent-rig','--env-file',rig_file,*mounts,'-w','/repo/agents/rig','-p','127.0.0.1::8000',image,'uvicorn','rigbox.three_d.asgi:app','--host','0.0.0.0','--port','8000','--no-proxy-headers','--no-access-log')
        tank_url='http://'+docker('port',tank,'8000/tcp')
        rig_url='http://'+docker('port',rig,'8000/tcp')
        wait_health(tank_url);wait_health(rig_url)
        with (PROOF/'startup-tail.txt').open('w') as log:
            for name in (tank,rig):
                result=command(DOCKER+['logs','--tail','12',name],capture_output=True,text=True)
                log.write(('Tank' if name==tank else 'Rig')+' startup\n'+result.stdout+result.stderr)
        print('Real Tank and production Rig entry point are healthy.',flush=True)
        docker('exec',tank,'python','/repo/tests/rig_store_job/database.py')
        with (PROOF/'job-output.txt').open('w') as out:
            def record(text):
                print(text,flush=True);out.write(text+'\n');out.flush()
            browser_env={**ENV,'RIG_PROOF_DIR':str(PROOF),'RIG_TANK_URL':tank_url,'RIG_API_URL':rig_url,
                'RIG_ESBUILD_PATH':str(PROOF/'browser/node_modules/esbuild'),
                'RIG_PLAYWRIGHT_PATH':str(PROOF/'browser/node_modules/playwright')}
            result=subprocess.run(['node','tests/rig_store_job/browser.cjs'],env=browser_env,cwd=ROOT,capture_output=True,text=True)
            record(result.stdout)
            if result.returncode:
                record(result.stderr);raise RuntimeError('Browser job failed; see private evidence directory')
            record(docker('exec',tank,'python','/repo/tests/rig_store_job/checks.py'))
            docker('restart',tank)
            tank_url='http://'+docker('port',tank,'8000/tcp')
            wait_health(tank_url)
            record(docker('exec',tank,'python','/repo/tests/rig_store_job/training.py'))
        print('PASS complete real-stack store job; evidence retained at',PROOF,flush=True)
    finally:
        for name in containers:
            result=command(DOCKER+['logs','--tail','25',name],capture_output=True,text=True)
            (PROOF/(name+'-tail.txt')).write_text(result.stdout+result.stderr)
        for name in reversed(containers):
            docker('rm','-f','-v',name)
        docker('network','rm',PREFIX)


if __name__=='__main__':
    main()
