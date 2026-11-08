"""The reviewed Tiger opt-in also gates its new extraction-result cache."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tiger_savings import cached_extract


@pytest.mark.asyncio
@pytest.mark.parametrize('setting', [None, '', 'false', '0', 'no'])
async def test_disabled_cache_preserves_skill_path_without_storage(monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv('TIGER_BRAIN_ENABLED', raising=False)
    else:
        monkeypatch.setenv('TIGER_BRAIN_ENABLED', setting)
    expected = {'placeholder': 'ordinary skill result'}
    skill = AsyncMock(return_value=expected)
    storage = Mock(side_effect=AssertionError('Default-off must not access cache storage'))
    tank = SimpleNamespace(skala=SimpleNamespace(run_skill=skill), pool=storage)
    package = SimpleNamespace(id='tiger.price_extract')
    body = SimpleNamespace(preview=False, input={'placeholder': 'input'})
    context = SimpleNamespace()

    assert await cached_extract(tank, package, body, context) is expected
    skill.assert_awaited_once_with(package, body.input, context)
    storage.assert_not_called()
    assert context._tiger_cache_hit is False
