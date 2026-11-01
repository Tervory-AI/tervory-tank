"""Read isolation checks against the drill's restored copy, never a supplied DSN."""
import json
import os
import re

import pytest

from ops.restore_drill import Sandbox, command, counts, identifier


def restored_box():
    name = os.environ.get('RESTORE_DRILL_PG', '')
    if not re.fullmatch(r'restore-drill-[a-f0-9]{32}-pg', name):
        pytest.skip('Only the restore drill may select this disposable container')
    label = command('docker', 'inspect', '--format', '{{index .Config.Labels "tervory.restore-drill"}}', name).decode().strip()
    assert label == name.removesuffix('-pg'), 'Disposable container ownership label is missing'
    box = Sandbox()
    box.pg = name
    return box


def pytest_generate_tests(metafunc):
    if 'relation' in metafunc.fixturenames:
        name = os.environ.get('RESTORE_DRILL_PG', '')
        if not name:
            metafunc.parametrize('relation', [None])
        else:
            box = restored_box()
            tables = list(counts(box))
            metafunc.parametrize('relation', tables or [None])


@pytest.fixture(scope='module')
def box():
    box = restored_box()
    box.sql('CREATE ROLE restore_drill_reader NOSUPERUSER NOBYPASSRLS;')
    for relation in counts(box):
        schema = relation.split('.')[0]
        box.sql(f'GRANT USAGE ON SCHEMA {schema} TO restore_drill_reader; '
                f'GRANT SELECT ON {relation} TO restore_drill_reader;')
    return box


def test_restored_tenant_boundary(box, relation):
    assert relation is not None, 'No restored tenant tables were tested'
    # Assert FORCE and a restrictive policy as well as behaviour on restored rows.
    literal = relation.replace("'", "''")
    assert box.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='{literal}'::regclass") == 't'
    assert int(box.sql(f"SELECT count(*) FROM pg_policy WHERE polrelid='{literal}'::regclass AND NOT polpermissive")) > 0
    assert box.sql(f"BEGIN; SET LOCAL ROLE restore_drill_reader; SELECT count(*) FROM {relation}; ROLLBACK").splitlines()[-2] == '0'
    groups = json.loads(box.sql(f"SELECT coalesce(json_agg(x),'[]') FROM (SELECT tenant_id::text AS tenant,count(*) AS n FROM {relation} WHERE tenant_id IS NOT NULL GROUP BY tenant_id) x"))
    for group in groups:
        # UUID cast verifies values before SQL interpolation; identifiers never enter output.
        from uuid import UUID
        tenant = str(UUID(group['tenant']))
        output = box.sql(f"BEGIN; SET LOCAL ROLE restore_drill_reader; SET LOCAL app.tenant_id='{tenant}'; SELECT count(*) FROM {relation}; ROLLBACK")
        assert int(output.splitlines()[-2]) == group['n']
    absent = 'ffffffff-ffff-ffff-ffff-ffffffffffff'
    expected = next((g['n'] for g in groups if g['tenant'] == absent), 0)
    output = box.sql(f"BEGIN; SET LOCAL ROLE restore_drill_reader; SET LOCAL app.tenant_id='{absent}'; SELECT count(*) FROM {relation}; ROLLBACK")
    assert int(output.splitlines()[-2]) == expected
