from unittest.mock import create_autospec

import pytest

from app.application.usuarios.ports.user_repository import UserRepository
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario


@pytest.fixture
def repositorio():
    repo = create_autospec(UserRepository, instance=True, spec_set=True)
    repo.obtener_por_id.return_value = None
    repo.obtener_por_email.return_value = None
    repo.listar.return_value = []
    return repo


@pytest.fixture
def usuario():
    return Usuario.crear(nombre="Ana", apellido="Pérez", email=Email("ana@ejemplo.com"))
