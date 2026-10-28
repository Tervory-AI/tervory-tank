"""Read-only audit of the exact upstream tag; no imports of LiteLLM or network calls.

Usage: python tests/tank_batch_providers/verify_pinned_support.py UPSTREAM_CHECKOUT
"""
import ast
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
expected = 'ea7ca16dbc3904d9e59a9505f379a2ca3091821f'
revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
assert revision == expected, revision
pin = Path('litellm/Dockerfile').read_text()
assert 'FROM ghcr.io/berriai/litellm:v1.106.4' in pin
print(f'Repository pin: v1.106.4; upstream commit: {revision}')

main = ast.parse((root / 'litellm/batches/main.py').read_text())
create = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == 'create_batch')
provider_literals = {
    part.value for node in ast.walk(create) if isinstance(node, ast.Compare)
    for part in ast.walk(node) if isinstance(part, ast.Constant) and isinstance(part.value, str)
}
assert 'azure' in provider_literals and 'vertex_ai' in provider_literals
assert 'anthropic' not in provider_literals and 'gemini' not in provider_literals
print('create_batch dispatch: Azure and Vertex; no Anthropic or Gemini branch')

utils = ast.parse((root / 'litellm/utils.py').read_text())
config = next(node for node in ast.walk(utils) if isinstance(node, ast.FunctionDef)
              and node.name == 'get_provider_batches_config')
provider_enums = {node.attr for node in ast.walk(config) if isinstance(node, ast.Attribute)
                  and isinstance(node.value, ast.Name) and node.value.id == 'LlmProviders'}
assert provider_enums == {'BEDROCK', 'MISTRAL'}, provider_enums
print('Generic provider batch configurations: BEDROCK, MISTRAL only')

# Execute only the two standalone placeholder bodies. Postponed annotations avoid
# importing any SDK. The extracted methods contain no I/O or credential lookup.
filename = root / 'litellm/llms/anthropic/batches/transformation.py'
tree = ast.parse(filename.read_text())
cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'AnthropicBatchesConfig')
for name in ['transform_create_batch_request', 'transform_create_batch_response']:
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    assert len(method.body) == 2 and isinstance(method.body[1], ast.Raise)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), method], type_ignores=[])
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), str(filename), 'exec'), namespace)
    try:
        namespace[name](*([None] * len(method.args.args)))
    except NotImplementedError as error:
        assert str(error) == 'Batch creation not yet implemented for Anthropic'
        print(f'{name}: NotImplementedError: {error}')
    else:
        raise AssertionError(f'{name} unexpectedly implemented')
print('BLOCKER CONFIRMED: this pin cannot submit the required Anthropic provider batch')
