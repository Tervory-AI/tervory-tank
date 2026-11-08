"""Code first for catalogue facts; any remaining inference uses Tank's ladder."""
from collections import OrderedDict
import hashlib
import json
import time

from .claims import grounded_answer
from .ground import fit_suggest
from .logic import _why, approved


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)


def code_result(task, payload):
    if task == 'rig.ask':
        # The existing grounding rules already prove both row facts and approved
        # relations. A model choosing the same row identifiers adds no knowledge.
        rows = [str(row.get('id') or row.get('sku')) for row in payload['products']]
        answer = grounded_answer(payload, encoded({'cites': rows}))
        return {'cites': answer['cites']}
    if task == 'rig.explain':
        centre, part, fit = (payload[name] for name in ('centre', 'part', 'fit'))
        lines = _why(centre, [(part, fit)]) if approved(fit) else []
        return {'why': [line for line in lines if line != f"Fits {centre.get('name')}"]}
    if task == 'rig.fit_suggest':
        # Only explicit catalogue references can propose a fit. Similar names,
        # colours and unconstrained prose never establish physical compatibility.
        products = payload['products']
        candidates = []
        for product in products:
            attributes = product.get('attributes') or {}
            for field in ('fits_sku', 'fits_family'):
                targets = attributes.get(field, [])
                if isinstance(targets, str):
                    targets = [targets]
                if not isinstance(targets, list):
                    continue
                for target in targets:
                    if isinstance(target, str) and target and target != product['id']:
                        candidates.append({'part_sku': product['id'], field: target,
                                           'confidence': 1.0, 'rule': {}})
        # Reuse the existing validator and mandatory human-review boundary.
        result = fit_suggest(payload, encoded({'fits': candidates}))
        unique = {encoded(row): row for row in result['fits']}
        return {'fits': list(unique.values())}
    raise ValueError('Unsupported structured Rig task')


class Models:
    def __init__(self, tank, *, clock=time.monotonic):
        self.tank, self.clock = tank, clock
        self.cache = OrderedDict()

    async def structured(self, tenant, task, payload):
        # The full catalogue/fit snapshot participates in the key: no stale
        # prices, revoked fits, or answers leaking between stores.
        key = (str(tenant), task, hashlib.sha256(encoded(payload).encode()).hexdigest())
        cached = self.cache.get(key)
        if cached is not None and self.clock() - cached[0] < 300:
            self.cache.move_to_end(key)
            return cached[1]
        result = encoded(code_result(task, payload))
        self.cache[key] = (self.clock(), result)
        self.cache.move_to_end(key)
        while len(self.cache) > 256:
            self.cache.popitem(last=False)
        return result
