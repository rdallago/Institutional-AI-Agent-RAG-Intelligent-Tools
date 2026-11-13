"""Comparacion offline de los unicos CHECK reformulados autorizados."""
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[3] / 'infra/pgvector/maintenance_93e.py'
spec = importlib.util.spec_from_file_location('maintenance_93e_checks', path)
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


@pytest.mark.parametrize('identity', list(maintenance.CHECK_VARIANTS))
def test_only_known_array_cast_pair(identity):
    a, b = sorted(maintenance.CHECK_VARIANTS[identity])
    assert maintenance.constraints_equivalent(*identity, a, b)
    assert maintenance.constraints_equivalent(*identity, b, a)
    assert not maintenance.constraints_equivalent('another_table', identity[1], a, b)


@pytest.mark.parametrize('identity', list(maintenance.CHECK_VARIANTS))
@pytest.mark.parametrize('mutation', ['operator', 'value', 'column', 'condition', 'null', 'collation'])
def test_real_changes_rejected(identity, mutation):
    a, b = sorted(maintenance.CHECK_VARIANTS[identity])
    if mutation == 'operator': changed = b.replace(' = ANY', ' <> ANY')
    elif mutation == 'value': changed = b.replace("'ADMIN'", "'ROOT'").replace("'email_ip'", "'email'")
    elif mutation == 'column': changed = b.replace('(rol)', '(otro)').replace('(ambito)', '(otro)')
    elif mutation == 'condition': changed = b[:-1] + ' OR true)'
    elif mutation == 'null': changed = b.replace('ARRAY[', 'ARRAY[NULL,')
    else: changed = b + ' COLLATE "C"'
    assert changed != b
    assert not maintenance.constraints_equivalent(*identity, a, changed)


def test_snapshot_other_fields_remain_strict():
    identity = ('usuarios', 'ck_usuarios_rol')
    a, b = sorted(maintenance.CHECK_VARIANTS[identity])
    left = {'constraints': [[*identity, a]], 'records': {'count': 2}}
    right = {'constraints': [[*identity, b]], 'records': {'count': 2}}
    assert maintenance.snapshots_equal(left, right)
    right['records'] = {'count': 3}
    assert not maintenance.snapshots_equal(left, right)
    assert not maintenance.constraints_equivalent('x', 'other', 'CHECK (a>0)', 'CHECK (a>=0)')
