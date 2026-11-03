"""Product additions and lifecycle cancellation use the existing assembly path."""
import asyncio
from importlib import import_module
from types import SimpleNamespace

import pytest


def test_temporary_product_extends_only_its_own_catalogue(tmp_path, monkeypatch):
    import command
    import command_tools as registry
    package = tmp_path / 'placeholder_package'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'placeholder_product.py').write_text('''
TOOLS = {'placeholder_product': ['placeholder.read']}
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = []
ADMIN_ONLY_TOOLS = REQUEST_BODY_TOOLS = CONFIRMED = frozenset()
def adapters(command):
    return {'placeholder.read': command.Adapter('GET', '/placeholder', command.Body, 'placeholder.read')}
''')
    monkeypatch.syspath_prepend(str(tmp_path))
    product = import_module('placeholder_package.placeholder_product')
    products = (*registry.PRODUCTS, product)
    assert registry.build_tools(products) == {**command.TOOLS, 'placeholder_product': ['placeholder.read']}
    actual = registry.build_adapters(vars(command), products)
    assert list(actual) == [*command.ADAPTERS, 'placeholder.read']
    assert {name: actual[name] for name in command.ADAPTERS} == command.ADAPTERS
    assert registry.build_founder_tools(products) == command.FOUNDER_TOOLS
    assert registry.build_admin_tools(products) == command.TENANT_ADMIN_TOOLS
    assert registry.build_set('CONFIRMED', products) == command.CONFIRMED


@pytest.mark.asyncio
async def test_product_tasks_start_and_cancel_in_original_order(monkeypatch):
    import routes_registry as registry
    events = []
    waiting = asyncio.Event()

    def module(name):
        async def work(tank):
            events.append(('start', name, tank))
            try:
                await waiting.wait()
            finally:
                events.append(('stop', name, tank))
        return SimpleNamespace(refresh_loop=work, publish_loop=work)

    monkeypatch.setattr(registry, 'import_module', module)
    tank = SimpleNamespace()
    await registry.startup_products(tank)
    await asyncio.sleep(0)
    await registry.shutdown_products(tank)
    assert [(event, name) for event, name, _ in events] == [
        ('start', 'trigger_bot'), ('start', 'trigger_publisher'),
        ('stop', 'trigger_bot'), ('stop', 'trigger_publisher')]
    assert all(owner is tank for _, _, owner in events)
    assert all(getattr(tank, hook.slot).cancelled() for hook in registry.PRODUCT_HOOKS)


@pytest.mark.asyncio
async def test_product_code_planner_registration_needs_no_shared_branch(tmp_path, monkeypatch):
    import command_tools as registry
    package = tmp_path / 'placeholder_planner_pkg'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'placeholder_product.py').write_text('''
from types import SimpleNamespace
async def code_plan(actor, messages, task_id):
    if messages and messages[-1].get('content') == 'placeholder-plan':
        return SimpleNamespace(content='placeholder-plan', ledger_id=task_id)
    return None
''')
    monkeypatch.syspath_prepend(str(tmp_path))
    product = import_module('placeholder_planner_pkg.placeholder_product')
    products = (*registry.PRODUCTS, product)
    result = await registry.plan_products(None, [{'role': 'user', 'content': 'placeholder-plan'}],
                                         'placeholder-task', products)
    assert result.content == 'placeholder-plan' and result.ledger_id == 'placeholder-task'
    assert await registry.plan_products(None, [{'role': 'user', 'content': 'placeholder-unmatched'}], None, products) is None
