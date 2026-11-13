from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import app.bootstrap as bootstrap
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


def test_creation_and_main_import_do_not_load_database_or_connect(monkeypatch):
    import app.infrastructure.configuration.database as config
    import app.infrastructure.persistence.database as database

    def forbidden(*args, **kwargs):
        raise AssertionError("No configurar ni conectar al importar")

    monkeypatch.setattr(config, "load_database_config", forbidden)
    monkeypatch.setattr(database, "build_engine", forbidden)
    application = bootstrap.create_app()
    import importlib
    import app.main
    importlib.reload(app.main)
    assert application.openapi()["paths"]


@pytest.mark.parametrize("failure", [False, True])
def test_owned_engine_is_disposed_even_when_lifespan_body_fails(monkeypatch, failure):
    engine = Mock()
    repo = InMemoryUserRepository()
    factory = Mock(return_value=(engine, repo))
    monkeypatch.setattr(bootstrap, "crear_persistencia_postgresql", factory)
    auth = Mock(); auth.manage.return_value = []
    from app.infrastructure.configuration.llm import LLMConfig
    app = bootstrap.create_app(auth_service=auth, llm_config=LLMConfig(testing=True,environment='test'))
    assert not factory.called
    try:
        with TestClient(app, headers={"Authorization": "Bearer fixture"}) as client:
            assert client.get("/api/v1/usuarios").json() == []
            factory.assert_called_once_with(None)
            if failure:
                raise RuntimeError("test exit")
    except RuntimeError:
        assert failure
    engine.dispose.assert_called_once_with()
    assert not hasattr(app.state, "user_repository")


def test_injected_repository_never_loads_postgres(monkeypatch):
    import app.infrastructure.configuration.database as config
    load = Mock(side_effect=AssertionError("No leer configuración PostgreSQL"))
    monkeypatch.setattr(config, "load_database_config", load)
    auth = Mock(); auth.manage.return_value = []
    with TestClient(bootstrap.create_app(repository=InMemoryUserRepository(), auth_service=auth), headers={"Authorization": "Bearer fixture"}) as client:
        assert client.get("/api/v1/usuarios").json() == []
    load.assert_not_called()


def test_manual_test_factory_always_requests_test_configuration(monkeypatch):
    import app.infrastructure.configuration.database as config
    load = Mock(return_value=object())
    monkeypatch.setattr(config, "load_database_config", load)
    from app.infrastructure.configuration import auth as auth_config_module
    monkeypatch.setattr(auth_config_module, "load_auth_config", lambda **kwargs: object())
    bootstrap.create_test_database_app()
    load.assert_called_once_with(testing=True)
