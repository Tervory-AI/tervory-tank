"""Bounded, tenant-owned search vocabulary; no catalogue defaults."""
from __future__ import annotations

from contextvars import ContextVar
from functools import lru_cache, wraps
import json
import logging
import re
from typing import Any

_LOG = logging.getLogger(__name__)
_CURRENT: ContextVar[dict[str, Any]] = ContextVar('rig_search_vocabulary', default={})
_FIELDS = {'centre_category': str, 'carry_category': str, 'part_categories': list,
           'category_words': dict, 'part_tail': dict, 'sight_words': list,
           'colour_words': list, 'size_patterns': dict, 'attribute_key': str,
           'modifier_words': list, 'spec_words': list, 'loose_words': str,
           'model_words': dict, 'unsold': dict, 'sentences': dict}

@lru_cache(maxsize=256)
def _compile(text: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(text, flags)

def validate(raw: Any) -> dict[str, Any]:
    """Ignore the whole object on any error; log a fixed reason, never input."""
    if raw is None:
        return {}
    reason = 'shape'
    try:
        if not isinstance(raw, dict) or set(raw) != set(_FIELDS):
            raise ValueError
        if any(not isinstance(raw[key], kind) for key, kind in _FIELDS.items()):
            raise ValueError
        reason = 'limit'
        # Bound before serialization, including nesting and total entries.
        budget = [0]
        def check(node: Any, depth: int = 0) -> None:
            budget[0] += 1
            if depth > 5 or budget[0] > 2048:
                raise ValueError
            if isinstance(node, str):
                if len(node) > 2048:
                    raise ValueError
            elif isinstance(node, list):
                if len(node) > 256:
                    raise ValueError
                for item in node:
                    check(item, depth + 1)
            elif isinstance(node, dict):
                if len(node) > 256:
                    raise ValueError
                for key, item in node.items():
                    if not isinstance(key, str) or len(key) > 100:
                        raise ValueError
                    check(item, depth + 1)
            else:
                raise ValueError
        check(raw)
        if len(json.dumps(raw).encode('utf8')) > 32768:
            raise ValueError
        reason = 'shape'
        for key in ('part_categories', 'sight_words', 'colour_words', 'modifier_words', 'spec_words'):
            if any(not isinstance(item, str) for item in raw[key]):
                raise ValueError
        for key in ('category_words', 'part_tail', 'size_patterns', 'model_words', 'unsold', 'sentences'):
            if any(not isinstance(item, str) for item in raw[key].values()):
                raise ValueError
        reason = 'pattern'
        if len(raw['size_patterns']) > 32:
            raise ValueError
        for key, text in {**raw['size_patterns'], 'loose': raw['loose_words']}.items():
            if len(text) > 512:
                raise ValueError
            _compile(text, 0 if key == 'thread' else re.IGNORECASE)
        # Validate format templates without interpreting field access or allowing
        # attribute/index traversal. Templates only substitute positional slots.
        reason = 'template'
        import string
        for text in raw['sentences'].values():
            for _, field, spec, conversion in string.Formatter().parse(text):
                if field is not None and (not field.isdecimal() or int(field) > 15 or spec or conversion not in (None, 's', 'r', 'a')):
                    raise ValueError
        return raw
    except (ValueError, TypeError, re.error, RecursionError, OverflowError):
        _LOG.warning('Guided search vocabulary ignored: %s', reason)
        return {}

def value(role: str, default: Any) -> Any:
    return _CURRENT.get().get(role, default)

def term(group: str, role: str) -> str:
    return str(value(group, {}).get(role, ''))

def pattern_text(role: str) -> str:
    return str(value('loose_words', '') if role == 'loose' else value('size_patterns', {}).get(role, r'(?!)'))

def pattern(role: str) -> re.Pattern[str]:
    return _compile(pattern_text(role), 0 if role == 'thread' else re.IGNORECASE)

def say(role: str, *args: Any) -> str:
    return term('sentences', role).format(*args)

def scoped(function):
    """Each synchronous entry has its own vocabulary, reset even on failure."""
    @wraps(function)
    def run(*args, **kwargs):
        raw = kwargs.pop('vocabulary', None)
        if function.__name__ == 'shop_search':
            raw = (args[0].get('shop') or {}).get('vocabulary')
        selected = validate(raw)
        if not selected:
            if function.__name__ == 'shop_search':
                from rigbox.rank import search
                return search(args[0])
            if function.__name__ == 'prepare_reservation':
                return ''
            return args[0]
        token = _CURRENT.set(selected)
        try:
            return function(*args, **kwargs)
        finally:
            _CURRENT.reset(token)
    return run
