"""Gaps in the retailer job: settings, keys, SMTP recovery and event recording."""
import json
from uuid import uuid4

import pytest

from test_rig_quotes import service
from rigbox.quotes.keys import embed_snippet, issue_embed_key
from rigbox.quotes.senders import DeliveryError, EmailHandoff, RetailerHandoff
from rigbox.reserve import SmtpMailer
from rigbox.retailer import Retailer
from rigbox.service import RigError, hash_key


@pytest.mark.asyncio
async def test_store_settings_and_keys_are_bound_to_the_authenticated_tenant():
    rig = await service()
    a, b = str(uuid4()), str(uuid4())
    retail = Retailer(rig)
    await retail.set_settings(a, {'name': 'Fixture A', 'email': 'a@fixture.test', 'tenant_id': b})
    assert (await retail.panel(b))['settings'] == {'name': '', 'email': ''}
    assert (await retail.panel(a))['settings']['email'] == 'a@fixture.test'
    with pytest.raises(RigError):
        await retail.embed_key(b, {'origins': ['https://b.fixture.test']})
    issued = await issue_embed_key(rig.store, a, ['https://a.fixture.test'])
    key = await rig.store.key(hash_key(issued['publishable_key']))
    assert key['tenant_id'] == a and key['origins'] == ['https://a.fixture.test']
    assert issued['publishable_key'] not in json.dumps(rig.store.keys)
    snippet = embed_snippet(issued['publishable_key'])
    assert '/widget/assets/tervory-rig.' in snippet and 'integrity="sha384-' in snippet


@pytest.mark.asyncio
@pytest.mark.parametrize('origin', ['https://a.test/path', 'https://a.test?key=wrong', 'https://user:pass@a.test',
                                  'https://*.a.test', 'http://a.test', 'https://a.test:bad', 'https://a.test\n', None])
async def test_bad_embed_origins_never_issue_a_key(origin):
    rig = await service()
    before = dict(rig.store.keys)
    with pytest.raises(RigError):
        await issue_embed_key(rig.store, str(uuid4()), [origin])
    assert rig.store.keys == before


@pytest.mark.asyncio
async def test_email_uses_existing_transport_and_a_stable_reference(monkeypatch):
    captured = []
    class Mail:
        async def send(self, letter): captured.append(letter)
    monkeypatch.setattr(SmtpMailer, 'from_env', lambda: Mail())
    quote = {'id': 'req_' + uuid4().hex, 'payload': {'kind': 'link', 'url': 'https://store.test/item', 'note': 'Blue'},
             'contact': {'name': 'Fixture Shopper', 'email': 'shopper@fixture.test'}}
    await RetailerHandoff(None).send(tenant_id=str(uuid4()), email='store@fixture.test', webhook=None, quote=quote)
    letter = captured[0]
    assert letter['to'] == 'store@fixture.test' and letter['reply_to'] == 'shopper@fixture.test'
    assert quote['id'] in letter['subject'] and quote['id'] in letter['text'] and quote['id'] in letter['message_id']
    assert 'https://store.test/item' in letter['text'] and 'Note: Blue' in letter['text']
    class Broken:
        async def send(self, letter): raise RuntimeError('private remote SMTP response')
    monkeypatch.setattr(SmtpMailer, 'from_env', lambda: Broken())
    with pytest.raises(DeliveryError, match='^email_unavailable$'):
        await EmailHandoff().send('store@fixture.test', quote)


@pytest.mark.asyncio
async def test_cached_misses_are_distinct_tenant_private_training_events():
    rig = await service()
    a, b = str(uuid4()), str(uuid4())
    for tenant in [a, a, b]:
        assert (await rig.search(tenant, 'unmatchedfixture', 10))['results'] == []
    events = rig.store.training_events
    assert len(events) == 3 and len({e['source_ref'] for e in events}) == 3
    assert [e['tenant_id'] for e in events] == [a, a, b]
    assert all(e['source'] == 'rig_no_result' and e['output'] == {'results': []} for e in events)
