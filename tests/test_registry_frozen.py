"""Mechanical registry contract, captured before extraction from origin/main.

The JSON-formatted .golden file is a non-executable snapshot, not runtime
configuration. Its origin commit predates the extraction; updates need review.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).with_name('registry_frozen.golden')
ORIGIN_COMMIT = '5bf17ad19dd0318d30becfff3df4564b433f3344'


def _membership(command, function):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and ast.unparse(node.left) == 'action.tool':
            for right, operation in zip(node.comparators, node.ops):
                if isinstance(operation, ast.In) and isinstance(right, (ast.Set, ast.Name)):
                    values = eval(compile(ast.Expression(right), '<registry>', 'eval'), vars(command))
                    if 'base.list.save' in values:
                        return sorted(values)
    raise AssertionError('dispatch membership not found')


def _dispatch(command, tools):
    """Record the first arm of execute_card's tool-dispatch if/elif chain."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(command.execute_card)))
    start = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                 and ast.unparse(node.test) == "action.tool.startswith('mcp.')")
    tests = []
    branch = start
    while True:
        tests.append(compile(ast.Expression(branch.test), '<dispatch>', 'eval'))
        if len(branch.orelse) == 1 and isinstance(branch.orelse[0], ast.If):
            branch = branch.orelse[0]
        else:
            break
    return {tool: next((index for index, test in enumerate(tests)
                       if eval(test, vars(command), {'action': SimpleNamespace(tool=tool)})), len(tests))
            for tool in sorted(tools)}


def _tasks(function):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return [ast.unparse(node.args[0].func) for node in ast.walk(tree)
            if isinstance(node, ast.Call) and ast.unparse(node.func) == 'asyncio.create_task'
            and node.args and isinstance(node.args[0], ast.Call)]


def snapshot():
    sys.path[:0] = [str(ROOT / 'tank'), str(ROOT / 'agents/_chassis')]
    import command
    import main
    from fastapi.routing import iter_route_contexts
    command.command_repo.configured = lambda: True
    actors = {
        name: command.Actor(uuid.UUID(int=1), 'placeholder-user', founder,
                            frozenset(command.TOOLS), tenant_admin=admin)
        for name, founder, admin in [('member', False, False), ('tenant_admin', False, True), ('founder', True, False)]
    }
    lifecycle = {}
    for event in ('startup', 'shutdown'):
        handlers = getattr(main.app.router, 'on_' + event)
        lifecycle[event] = [{'module': f.__module__, 'name': f.__qualname__, 'tasks': _tasks(f)} for f in handlers]
    if 'routes_registry' in sys.modules:
        registry = sys.modules['routes_registry']
        for entry in lifecycle['startup']:
            if entry['name'] == '_startup':
                entry['tasks'] += [hook.function for hook in registry.PRODUCT_HOOKS]
    return {
        'tools': list(command.TOOLS.items()),
        'founder_tools': command.FOUNDER_TOOLS,
        'adapters': [[name, {**{key: value for key, value in vars(adapter).items() if key != 'arguments'},
                            'arguments': adapter.arguments.model_json_schema()}]
                     for name, adapter in command.ADAPTERS.items()],
        'dispatch': _dispatch(command, set(command.ADAPTERS) | {tool for actor in actors.values() for tool in command.allowed_tools(actor)}),
        'request_body_tools': _membership(command, command.adapter_request),
        'confirmed_dispatch_tools': _membership(command, command.execute_card),
        'allowed_tools': {name: command.allowed_tools(actor) for name, actor in actors.items()},
        'planning_message': {name: command.planning_message(actor) for name, actor in actors.items()},
        'routes': [{'path': route.path, 'methods': sorted(route.methods or []), 'name': route.name}
                   for route in iter_route_contexts(main.app.routes)],
        'lifecycle': lifecycle,
        'shutdown_tasks': ([hook.slot for hook in sys.modules['routes_registry'].PRODUCT_HOOKS]
                           if 'routes_registry' in sys.modules else []) + [
            node.func.value.id for node in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(main._shutdown))))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'cancel' and isinstance(node.func.value, ast.Name)],
        'schema': ''.join(line for line in (ROOT / 'tank/schema.sql').read_text().splitlines(keepends=True)
                          if not line.lstrip().startswith('--')),
    }


def fresh_snapshot():
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG') if key in os.environ}
    env.update(DATABASE_URL='postgresql://placeholder/placeholder', TANK_API_KEY='placeholder',
               LITELLM_MASTER_KEY='placeholder', TANK_REGION='us-east')
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--snapshot'], cwd=ROOT,
                            env=env, text=True, capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout)


def test_registry_matches_frozen_origin_main():
    expected = json.loads(GOLDEN.read_text())
    assert expected['origin_commit'] == ORIGIN_COMMIT
    assert fresh_snapshot() == expected['registry']


if __name__ == '__main__' and sys.argv[1:] == ['--snapshot']:
    # Placeholder values are only import-time offline fixtures; no startup or calls.
    os.environ.update(DATABASE_URL='postgresql://placeholder/placeholder', TANK_API_KEY='placeholder',
                      LITELLM_MASTER_KEY='placeholder', TANK_REGION='us-east')
    print(json.dumps(snapshot(), indent=2))
