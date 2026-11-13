import pytest
from sqlalchemy import text

from app.application.usuarios.dto import CrearUsuarioDatos, ListarUsuariosDatos, ModificarUsuarioDatos, EstadoUsuarios
from app.application.usuarios.exceptions import EmailEnUso, UsuarioActivoExistente, UsuarioInactivoReactivable
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository, ErrorPersistencia


pytestmark = pytest.mark.postgres


def test_commit_visible_from_independent_engine(postgres_repository, postgres_resources):
    config, _, _ = postgres_resources
    created = CrearUsuario(postgres_repository).ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="Pérez", email="persist@example.com"))
    second_engine = build_engine(config)
    try:
        second = SQLAlchemyUserRepository(build_session_factory(second_engine))
        restored = ObtenerUsuario(second).ejecutar(created.id)
        assert restored == created
    finally:
        second_engine.dispose()


def test_full_use_case_lifecycle_and_conflicts(postgres_repository):
    repo = postgres_repository
    created = CrearUsuario(repo).ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="Pérez", email="ana@example.com"))
    with pytest.raises(UsuarioActivoExistente):
        CrearUsuario(repo).ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="Persona", email=created.email))
    changed = ModificarUsuario(repo).ejecutar(created.id, ModificarUsuarioDatos(nombre="Ana", apellido="Díaz", email=created.email))
    assert changed.id == created.id and changed.fecha_creacion == created.fecha_creacion
    inactive = DarDeBajaUsuario(repo).ejecutar(created.id)
    assert DarDeBajaUsuario(repo).ejecutar(created.id) == inactive
    with pytest.raises(UsuarioInactivoReactivable) as conflict:
        CrearUsuario(repo).ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="Persona", email=created.email))
    assert conflict.value.usuario_id == created.id
    assert not ObtenerUsuario(repo).ejecutar(created.id).activo
    assert ReactivarUsuario(repo).ejecutar(created.id) == changed
    assert ReactivarUsuario(repo).ejecutar(created.id) == changed
    assert len(repo.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS))) == 1


def test_edit_conflict_does_not_persist_partial_changes(postgres_repository):
    repo = postgres_repository
    first = CrearUsuario(repo).ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="Pérez", email="first@example.com"))
    second = CrearUsuario(repo).ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="Persona", email="second@example.com"))
    DarDeBajaUsuario(repo).ejecutar(second.id)
    with pytest.raises(EmailEnUso):
        ModificarUsuario(repo).ejecutar(first.id, ModificarUsuarioDatos(nombre="Changed", apellido="Changed", email=second.email))
    assert ObtenerUsuario(repo).ejecutar(first.id) == first


def test_check_failure_rolls_back_and_next_operation_works(postgres_repository, monkeypatch):
    import app.infrastructure.persistence.repositories.sqlalchemy_user_repository as module

    entity = Usuario.crear(nombre="Ana", apellido="Pérez", email=Email("rollback@example.com"))
    postgres_repository.agregar(entity)
    original_mapper = module.to_model

    def invalid_model(user):
        model = original_mapper(user)
        model.nombre = ""
        return model

    with monkeypatch.context() as patch:
        patch.setattr(module, "to_model", invalid_model)
        with pytest.raises(ErrorPersistencia):
            postgres_repository.actualizar(entity)
    assert postgres_repository.obtener_por_id(entity.id).nombre == "Ana"
    entity.modificar_datos(nombre="Valid", apellido="Pérez", email=entity.email)
    postgres_repository.actualizar(entity)
    assert postgres_repository.obtener_por_id(entity.id).nombre == "Valid"


def test_database_uses_timezone_and_no_server_generated_identity(postgres_repository, postgres_resources):
    _, engine, _ = postgres_resources
    with engine.connect() as connection:
        assert connection.execute(text("SHOW timezone")).scalar_one() == "UTC"
        columns = connection.execute(text(
            "SELECT column_name, column_default, is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='usuarios'"
        )).all()
        assert len(columns) == 7
        assert all(default is None and nullable == "NO" for _, default, nullable in columns)
