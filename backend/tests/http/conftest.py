import pytest
from fastapi.testclient import TestClient

from app.bootstrap import create_app
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository
from fastapi import Depends
from typing import Annotated
from app.application.auth.service import Principal
from app.presentation.http.auth.dependencies import get_current_user
from app.presentation.http import dependencies as deps
from auth_support import memory_auth, bootstrap_login


@pytest.fixture
def memory_repository():
    return InMemoryUserRepository()


@pytest.fixture
def http_app(memory_repository, monkeypatch):
    import app.bootstrap as bootstrap

    def forbidden(*args, **kwargs):
        raise AssertionError("Una prueba HTTP de memoria no debe configurar PostgreSQL")

    monkeypatch.setattr(bootstrap, "crear_persistencia_postgresql", forbidden)
    _, service, _ = memory_auth()
    _, token = bootstrap_login(service)
    application = create_app(repository=memory_repository, auth_service=service)
    application.state.fixture_token = token
    # Cobertura de transporte previa: actor real en repositorio de autenticación
    # separado; casos de negocio sustituidos para conservar sus datos/orden originales.
    from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
    from app.application.usuarios.use_cases.listar_usuarios import ListarUsuarios
    from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
    from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
    from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
    from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario

    def authorized_case(case_class):
        def provide(principal: Annotated[Principal, Depends(get_current_user)]):
            return case_class(memory_repository)
        return provide

    # Estos casos prueban transporte/perfiles puros; el aprovisionamiento real se
    # verifica por separado contra AuthService sin sustituir sus casos.
    class ProfileTransportCreate:
        def ejecutar(self, datos, password_inicial):
            return CrearUsuario(memory_repository).ejecutar(datos)

    def provide_transport_create(principal: Annotated[Principal, Depends(get_current_user)]):
        return ProfileTransportCreate()

    for dependency, case in [(deps.get_crear_usuario, CrearUsuario), (deps.get_listar_usuarios, ListarUsuarios),
        (deps.get_obtener_usuario, ObtenerUsuario), (deps.get_modificar_usuario, ModificarUsuario),
        (deps.get_dar_de_baja_usuario, DarDeBajaUsuario), (deps.get_reactivar_usuario, ReactivarUsuario)]:
        application.dependency_overrides[dependency] = authorized_case(case)
    application.dependency_overrides[deps.get_crear_usuario] = provide_transport_create
    return application


@pytest.fixture
def client(http_app):
    with TestClient(http_app, headers={"Authorization": "Bearer " + http_app.state.fixture_token}) as result:
        yield result
