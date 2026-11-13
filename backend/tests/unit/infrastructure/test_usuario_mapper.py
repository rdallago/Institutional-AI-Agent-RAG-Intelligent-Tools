from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.usuarios.email import Email
from app.domain.usuarios.exceptions import FechaCreacionInvalida
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.mappers.usuario import to_domain, to_model


def test_roundtrip_preserves_identity_state_role_and_instant():
    original = Usuario.crear(nombre=" Ana ", apellido="Pérez", email=Email("ANA@example.com"), rol=Rol.ADMIN)
    original.dar_de_baja()
    model = to_model(original)
    restored = to_domain(model)
    assert restored.id == original.id
    assert restored.fecha_creacion == original.fecha_creacion
    assert restored.email == original.email
    assert restored.rol is Rol.ADMIN
    assert restored.activo is False
    restored.reactivar()
    assert not original.activo and not model.activo


def test_read_normalizes_timezone_without_generating_a_new_instant():
    model = to_model(Usuario.crear(nombre="A", apellido="B", email=Email("a@example.com")))
    model.fecha_creacion = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-3)))
    assert to_domain(model).fecha_creacion == datetime(2026, 1, 1, 3, tzinfo=UTC)


def test_invalid_persisted_date_is_not_silently_repaired():
    model = to_model(Usuario.crear(nombre="A", apellido="B", email=Email("a@example.com")))
    model.fecha_creacion = datetime(2026, 1, 1)
    with pytest.raises(FechaCreacionInvalida):
        to_domain(model)
