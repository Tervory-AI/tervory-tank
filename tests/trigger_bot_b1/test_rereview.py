"""Second-review regressions, offline except for disposable local PostgreSQL."""
import asyncpg
import pytest
from test_database import A, B, B1
from test_database import database as database
from test_engine import POINT, answer, passage
from trigger_bot_grounding import DATES, PRICE_OR_STOCK, grounded


@pytest.mark.parametrize('form', ['9am', '5pm', '2x', '3kg', '25th'])
def test_every_digit_run_requires_cited_evidence(form):
    output = {'answer': form, 'passage_ids': [str(POINT)]}
    assert grounded(output, [passage(text='Store policy')]) is None
    assert grounded(output, [passage(text='Policy: ' + form)])
    assert grounded({'answer': ''.join(c for c in form if c.isdigit()),
                     'passage_ids': [str(POINT)]}, [passage(text=form)])


@pytest.mark.parametrize('text', ['the 5th', 'size 10 and 12', 'the 12 targets'])
@pytest.mark.asyncio
async def test_ordinary_numbers_reach_answer_path(text):
    assert not PRICE_OR_STOCK.search(text)
    result, route, _, _ = await answer(passages=[passage(text=text)],
        output={'answer': text, 'passage_ids': [str(POINT)]})
    assert result['answer'] == text
    route.assert_awaited_once()


@pytest.mark.parametrize('text', ['usd 1299', '1299 usd', 'R1 299'])
@pytest.mark.asyncio
async def test_currency_prices_require_live_rig(text):
    assert PRICE_OR_STOCK.search(text)
    result, route, _, _ = await answer(passages=[passage(text=text)])
    assert result['state'] == 'handed_over'
    route.assert_not_awaited()
    assert grounded({'answer': text, 'passage_ids': [str(POINT)]},
                    [passage(text='1299 targets and 1 of 299 boxes')]) is None
    assert grounded({'answer': text, 'passage_ids': [str(POINT)]}, [passage(text=text)]) or text.startswith('R')


@pytest.mark.parametrize('code', ['ZAR', 'USD', 'EUR', 'GBP', 'NAD', 'BWP', 'AUD', 'CAD'])
@pytest.mark.parametrize('suffix', [False, True])
def test_currency_codes_are_case_insensitive(code, suffix):
    text = '1299 ' + code.lower() if suffix else code.lower() + ' 1299'
    assert PRICE_OR_STOCK.search(text)
    assert grounded({'answer': text, 'passage_ids': [str(POINT)]},
                    [passage(text=code + ' 1299')])


@pytest.mark.parametrize('text', ['You may return it within 30 days', 'May', 'now', 'soon', 'later'])
def test_ordinary_words_are_not_dates(text):
    assert not DATES.search(text)
    assert grounded({'answer': text, 'passage_ids': [str(POINT)]}, [passage(text='Returns within 30 days')])


@pytest.mark.parametrize('text', ['May 5', '5 May', 'May 2026', '2026 May'])
def test_may_adjacent_to_day_or_year_requires_date_evidence(text):
    assert DATES.search(text)
    output = {'answer': text, 'passage_ids': [str(POINT)]}
    assert grounded(output, [passage(text='Hours 5 to 2026')]) is None
    assert grounded(output, [passage(text=text)])


@pytest.mark.asyncio
async def test_limit_migration_cleans_orphans_is_idempotent_and_cascades(database):
    # Recreate the legacy state, only inside the fixture's disposable database.
    await database.execute('ALTER TABLE tank.trigger_bot_limits DROP CONSTRAINT trigger_bot_limits_window_fk')
    await database.execute('ALTER TABLE tank.trigger_bot_limits DROP CONSTRAINT trigger_bot_limits_hits_positive')
    await database.execute('''INSERT INTO tank.trigger_bot_limits(tenant_id,window_id,route,client_hash,hits)
        VALUES($1,1,'browse',$2,1)''', A, b'orphan')
    await database.execute(B1)
    await database.execute(B1)
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_limits') == 0
    for tenant in (A, B):
        await database.execute('''INSERT INTO tank.trigger_bot_windows(tenant_id,window_id,salt)
            VALUES($1,2,$2)''', tenant, b'placeholder')
        await database.execute('''INSERT INTO tank.trigger_bot_limits(tenant_id,window_id,route,client_hash,hits)
            VALUES($1,2,'browse',$2,1)''', tenant, b'placeholder')
    with pytest.raises(asyncpg.CheckViolationError):
        await database.execute('UPDATE tank.trigger_bot_limits SET hits=0 WHERE tenant_id=$1', A)
    await database.execute('DELETE FROM tank.trigger_bot_windows WHERE tenant_id=$1 AND window_id=2', A)
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_limits WHERE tenant_id=$1', A) == 0
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_limits WHERE tenant_id=$1', B) == 1
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await database.execute('''INSERT INTO tank.trigger_bot_limits(tenant_id,window_id,route,client_hash,hits)
            VALUES($1,3,'browse',$2,1)''', A, b'placeholder')
