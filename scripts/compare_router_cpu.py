#!/usr/bin/env python3
"""Opt-in local CPU execution, one immutable classifier at a time."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tank'))
from route_comparison import ArchAdapter, RouteLLMAdapter, configuration, digest, validate
from router_cpu import download, run_worker, sha256, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-cpu', action='store_true', required=True)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--tenant', required=True)
    args = parser.parse_args()
    if args.python.absolute() != ROOT/'.venv/bin/python':
        raise ValueError('Only the task-local .venv/bin/python is supported')
    data_path = ROOT / 'tests/fixtures/route_comparison/examples.json'
    data = json.loads(data_path.read_text())
    validate(data['examples'])
    rows = [r for r in data['examples'] if r['tenant_id'] == args.tenant]
    if not rows or len(rows) > 8:
        raise ValueError('Select between one and eight tenant-scoped examples')
    config = configuration(data['policy'])
    if config is None:
        raise ValueError('Invalid route pair')
    manifest_path = ROOT / 'tools/router_cpu/checkpoints.json'
    specs = json.loads(manifest_path.read_text())
    work = ROOT / '.checks/router-cpu'
    work.mkdir(parents=True, exist_ok=True)
    report = {'mode':'measured-cpu', 'commercial_permission':'pending-counsel-review',
        'sample_kind':'authored synthetic; preference labels not downstream answer-quality gold',
        'data_file_sha256':sha256(data_path),'selected_examples_sha256':digest(rows),
        'configuration_sha256':digest({'policy':data['policy'],'routes':data['routes']}),
        'checkpoint_manifest_sha256':sha256(manifest_path),
        'requirements_lock_sha256':sha256(ROOT/'tools/router_cpu/requirements.lock'),
        'source_hashes':{name:sha256(ROOT/name) for name in
            ('tank/router_cpu_worker.py','scripts/compare_router_cpu.py','tank/router_cpu.py','tank/route_comparison.py','tank/routellm_build.py')},
        'limits':{'torch_threads':2,'rss_watchdog_gib':12,'address_space_gib':24,'wall_seconds_per_model':600,
                  'cpu_seconds_per_model':600,'download_seconds_per_model':1800,'input_tokens_arch':1024,'generated_tokens_arch':32,
                  'download_bytes_total_manifest':sum(f['bytes'] for s in specs.values() for f in s['files'])},
        'models':{},'downstream_answer_quality':None,'inference_cost_usd':None,'cost_status':'unknown',
        'savings_usd':None}
    for name,spec in specs.items():
        model_report = {'revision':spec['revision'],'checkpoint_files':spec['files'],'status':'unrun'}
        report['models'][name] = model_report
        try:
            cache = work/'checkpoints'
            if args.download:
                model_report['phase']='download'
                download({name:spec}, cache)
            folder = cache/name
            model_report['phase']='verify'
            verify(folder,spec['files'])
            request,output = work/f'{name}-request.json',work/f'{name}-output.json'
            request.write_text(json.dumps({'model':name,'checkpoint':str(folder), 'routes':data['routes'],
                'examples':[{'id':r['id'],'messages':r['messages']} for r in rows]}))
            model_report['phase']='cpu'
            actual = run_worker('cpu',ROOT/'tank/router_cpu_worker.py',request,output)
            by_id = {r['id']:r for r in actual.pop('results')}
            if set(by_id) != {r['id'] for r in rows}:
                raise ValueError('Incomplete classifier results')
            splits = {}
            for split in ('development','holdout'):
                cases = [r for r in rows if r['split']==split]
                counts = dict(examples=len(cases),reference_matches=0,abstentions=0,escalations=0)
                times = []
                for row in cases:
                    value = by_id[row['id']]['value']
                    adapter = (ArchAdapter(lambda payload,v=value:v,config,data['routes']) if name=='arch'
                               else RouteLLMAdapter(lambda prompt,v=value:v,config))
                    decision = adapter.classify(row['messages'])
                    counts['reference_matches'] += int(decision.route==row['reference_route'])
                    counts['abstentions'] += int(decision.abstained)
                    counts['escalations'] += int(decision.escalated)
                    times.append(by_id[row['id']]['classifier_ms'])
                splits[split] = {**counts,'classifier_latency_ms':times}
            model_report.update({'status':'measured','phase':'complete',**actual,'splits':splits,
                'inference_cost_usd':None,'cost_status':'unknown'})
        except Exception as error:
            model_report.update(status='technical-blocker',error_type=type(error).__name__,
                                http_status=getattr(error,'code',None))
        (work/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))
    return int(any(m['status']!='measured' for m in report['models'].values()))


if __name__ == '__main__':
    sys.exit(main())
