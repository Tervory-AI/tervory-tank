"""Load current room sources in a local pinned runtime; no network or engine mount."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    image = parser.parse_args().image
    if image.startswith('-'):
        parser.error('an existing local image reference is required')
    root = Path(__file__).resolve().parents[2]
    subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL, check=True)
    args = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
            '--memory', '512m', '--entrypoint', 'python']
    for name in ['app.py', 'builder.py', 'pipeline.py', 'repo_scan.py', 'scaffold.py', 'promotion.py',
                 'promotion_api.py', 'publish.py', 'figma.py', 'gold_sources.py', 'quotes.py',
                 'review_store.py', 'schema.sql']:
        args += ['--mount', f'type=bind,source={root}/agents/tisan/{name},target=/app/{name},readonly']
    args += ['--mount', f'type=bind,source={root}/agents/_chassis/chassis,target=/app/chassis,readonly',
             image, '-c', "import app; schema=app.app.openapi(); "
             "assert '/pipeline/start' in schema['paths']; "
             "assert '/promotion/rollback' in schema['paths']; "
             "assert app.app.state.job_timeouts['pipeline']==2400; "
             "print('Current room routes passed in the pinned runtime: network none, read-only, no Docker socket.')"]
    subprocess.run(args, check=True, timeout=60)


if __name__ == '__main__':
    main()
