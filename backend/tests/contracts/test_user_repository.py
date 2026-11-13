from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from app.application.usuarios.dto import EstadoUsuarios, ListarUsuariosDatos
from app.application.usuarios.ports.user_repository import (
    EmailDuplicadoRepositorio, IdentidadDuplicadaRepositorio, UsuarioAusenteRepositorio,
)
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.postgres)])
def repository(request):
    if request.param == "memory":
        return InMemoryUserRepository()
    return request.getfixturevalue("postgres_repository")


def user(email="ana@example.com"):
    return Usuario.crear(nombre="Ana", apellido="Pérez", email=Email(email))


def test_empty_reads_and_missing_update(repository):
    assert repository.obtener_por_id(uuid4()) is None
    assert repository.obtener_por_email(Email("none@example.com")) is None
    assert repository.listar(ListarUsuariosDatos()) == []
    with pytest.raises(UsuarioAusenteRepositorio):
        repository.actualizar(user())
    assert repository.listar(ListarUsuariosDatos()) == []


def test_independent_entities_and_explicit_update(repository):
    original = user()
    repository.agregar(original)
    original.dar_de_baja()
    for loaded in (
        repository.obtener_por_id(original.id),
        repository.obtener_por_email(original.email),
        repository.listar(ListarUsuariosDatos())[0],
    ):
        assert loaded.activo
        loaded.dar_de_baja()
        assert repository.obtener_por_id(original.id).activo
    repository.actualizar(original)
    original.reactivar()
    assert not repository.obtener_por_id(original.id).activo


@pytest.mark.parametrize("active", [True, False])
def test_global_email_unique_and_duplicate_failure_is_atomic(repository, active):
    owner = user()
    if not active:
        owner.dar_de_baja()
    repository.agregar(owner)
    with pytest.raises(EmailDuplicadoRepositorio) as conflict:
        repository.agregar(user("ANA@example.com"))
    assert (conflict.value.usuario_id, conflict.value.activo) == (owner.id, active)
    other = user("other@example.com")
    repository.agregar(other)
    other.modificar_datos(nombre="Changed", apellido="Other", email=owner.email)
    with pytest.raises(EmailDuplicadoRepositorio):
        repository.actualizar(other)
    restored = repository.obtener_por_id(other.id)
    assert restored.nombre == "Ana"
    assert restored.email == Email("other@example.com")
    # Una escritura nueva después del fallo demuestra que no queda una sesión abortada.
    repository.agregar(user("after@example.com"))


def test_duplicate_identity_has_priority_and_does_not_overwrite(repository):
    original = user()
    repository.agregar(original)
    original.dar_de_baja()
    with pytest.raises(IdentidadDuplicadaRepositorio):
        repository.agregar(original)
    assert repository.obtener_por_id(original.id).activo


def test_update_releases_previous_email_and_accepts_own_email(repository):
    original = user()
    repository.agregar(original)
    repository.actualizar(original)
    original.modificar_datos(nombre="Ana", apellido="Díaz", email=Email("new@example.com"))
    repository.actualizar(original)
    repository.agregar(user())
    assert repository.obtener_por_email(Email("new@example.com")).id == original.id


def test_filter_order_before_pagination_and_uuid_tiebreak(repository):
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    for number in [4, 3, 2, 1]:
        entity = user(f"a{number}@example.com")
        repository.agregar(Usuario.reconstruir(
            id=UUID(int=number), nombre=entity.nombre, apellido=entity.apellido,
            email=entity.email, rol=entity.rol, activo=number % 2 == 0, fecha_creacion=instant,
        ))
    assert [u.id.int for u in repository.listar(ListarUsuariosDatos())] == [2, 4]
    assert [u.id.int for u in repository.listar(ListarUsuariosDatos(estado=EstadoUsuarios.INACTIVOS))] == [1, 3]
    assert [u.id.int for u in repository.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS, limite=2, desplazamiento=1))] == [2, 3]
    assert [u.id.int for u in repository.listar(ListarUsuariosDatos(limite=1, desplazamiento=1))] == [4]
    assert repository.listar(ListarUsuariosDatos(desplazamiento=10)) == []


@pytest.mark.parametrize("operation", ["agregar", "actualizar"])
def test_concurrent_writes_enforce_email_uniqueness(repository, operation):
    barrier = Barrier(8)
    entities = [user(f"parallel{i}@example.com") for i in range(8)]
    if operation == "actualizar":
        for entity in entities:
            repository.agregar(entity)

    def write(entity):
        entity.modificar_datos(nombre="Ana", apellido="Pérez", email=Email("shared@example.com"))
        barrier.wait(timeout=20)
        try:
            getattr(repository, operation)(entity)
            return True
        except EmailDuplicadoRepositorio:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(write, entities))
    assert sum(results) == 1
    assert len(repository.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS))) == (8 if operation == "actualizar" else 1)
