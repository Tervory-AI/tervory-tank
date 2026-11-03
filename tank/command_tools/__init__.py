"""Ordered assembly of product declarations; adding a tool edits its product only."""
from importlib import import_module
from types import SimpleNamespace

PRODUCTS = ('trigger', 'base', 'tiger', 'market_lab', 'rig', 'tisan', 'radix', 'zenas', 'mcp', 'skala', 'worker')
FOUNDER_ORDER = (('base', 3), ('trigger', 1), ('skala', 6), ('tisan', 1), ('worker', 4), ('mcp', 3), ('radix', 3), ('tisan', 4))
ADAPTER_ORDER = (('tisan', 4), ('base', 3), ('mcp', 3), ('trigger', 11), ('worker', 3), ('base', 2), ('tiger', 4), ('base', 7), ('tiger', 7), ('market_lab', 7), ('tiger', 1), ('market_lab', 1), ('rig', 3), ('tisan', 1), ('radix', 3), ('tisan', 1), ('radix', 3), ('zenas', 7), ('skala', 6), ('trigger', 26))

def product_modules(products=PRODUCTS):
    return [import_module("command_tools." + name) if isinstance(name, str) else name for name in products]


def build_tools(products=PRODUCTS):
    return {squad: list(tools) for module in product_modules(products) for squad, tools in module.TOOLS.items()}


def _ordered(groups, order):
    offsets = {name: 0 for name in groups}
    result = []
    for name, count in order:
        start = offsets[name]
        result.extend(groups[name][start:start + count])
        offsets[name] += count
    # New declarations append without changing any existing entry's position.
    for name, values in groups.items():
        result.extend(values[offsets[name]:])
    return result


def build_founder_tools(products=PRODUCTS):
    groups = {module.__name__.rsplit(".", 1)[-1]: module.FOUNDER_TOOLS for module in product_modules(products)}
    return _ordered(groups, FOUNDER_ORDER)


def build_set(name, products=PRODUCTS):
    return frozenset(tool for module in product_modules(products) for tool in getattr(module, name))


def build_admin_tools(products=PRODUCTS):
    return [tool for module in product_modules(products) for tool in module.TENANT_ADMIN_TOOLS]


def build_adapters(namespace, products=PRODUCTS):
    command = SimpleNamespace(**namespace)
    groups = {module.__name__.rsplit(".", 1)[-1]: list(module.adapters(command).items()) for module in product_modules(products)}
    return dict(_ordered(groups, ADAPTER_ORDER))
