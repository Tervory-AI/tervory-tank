"""Remove offline engine deployments before the LiteLLM router is initialized."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile

import yaml
import engine_runtime


def configure(config):
    config = deepcopy(config)
    # DECISION only an explicit shared C1 setting initializes Redis caching.
    settings = config.setdefault('litellm_settings', {})
    settings['cache'] = os.environ.get('ENGINE_C1_ENABLED') == '1'
    if not settings['cache']:
        settings.pop('cache_params', None)
    rows = []
    for row in config.get('model_list', []):
        name = row['model_name']
        if not engine_runtime.available(name):
            continue
        if name in engine_runtime.LOCAL:
            url = engine_runtime.local_url(name)
            row['litellm_params']['api_base'] = url if url.endswith('/v1') else url + '/v1'
        rows.append(row)
    config['model_list'] = rows
    # Retain the disabled model's fallback key so an older caller falls through
    # to an existing hosted seat. No attempt ever reaches an offline local host.
    for section in ('litellm_settings', 'router_settings'):
        settings = config.get(section, {})
        for key in ('fallbacks', 'context_window_fallbacks', 'content_policy_fallbacks'):
            if key in settings:
                settings[key] = [{name: [m for m in targets if engine_runtime.available(m)]}
                                 for chain in settings[key] for name, targets in chain.items()]
    # The HTTP proxy validates model names before router fallbacks run. Hidden
    # aliases let old local requests reach the next configured serving rung
    # without advertising an offline model or probing its absent service.
    names = {row['model_name'] for row in rows}
    chains = {name: targets for section in ('litellm_settings', 'router_settings')
              for chain in config.get(section, {}).get('fallbacks', []) for name, targets in chain.items()}
    for name in engine_runtime.LOCAL:
        if not engine_runtime.available(name):
            target = next((model for model in chains.get(name, []) if model in names), None)
            if target:
                config.setdefault('router_settings', {}).setdefault('model_group_alias', {})[name] = {
                    'model': target, 'hidden': True}
    return config


def main(args):
    args = list(args)
    index = args.index('--config') + 1
    config = configure(yaml.safe_load(Path(args[index]).read_text()))
    # Baked-in config contains environment references, not resolved credentials.
    with tempfile.NamedTemporaryFile(mode='w', prefix='litellm-engine-', suffix='.yaml', delete=False) as file:
        yaml.safe_dump(config, file, sort_keys=False)
        args[index] = file.name
    # The generated YAML is outside /app; preserve imports for its baked-in
    # callback and for spawned proxy workers without copying application code.
    app = str(Path(__file__).resolve().parent)
    os.environ['PYTHONPATH'] = os.pathsep.join(filter(None, (app, os.environ.get('PYTHONPATH'))))
    print(engine_runtime.local_status(), flush=True)
    # Match the pinned upstream entrypoint, including its optional tracing hook.
    command = ['litellm', *args]
    if os.environ.get('USE_DDTRACE', '').lower() == 'true':
        os.environ['DD_TRACE_OPENAI_ENABLED'] = 'False'
        command = ['ddtrace-run', *command]
    os.execvp(command[0], command)


if __name__ == '__main__':
    main(sys.argv[1:])
