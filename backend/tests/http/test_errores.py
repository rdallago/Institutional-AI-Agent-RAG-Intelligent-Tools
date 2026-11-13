import logging

import pytest
from fastapi.testclient import TestClient

from app.presentation.http.dependencies import get_listar_usuarios
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia


@pytest.mark.parametrize("exception,code", [
    (ErrorPersistencia("SELECT password FROM secret"), "ERROR_PERSISTENCIA"),
    (RuntimeError("postgresql://secret-credential@db"), "ERROR_INTERNO"),
])
def test_internal_errors_are_logged_without_sensitive_content(http_app, caplog, exception, code):
    class BrokenRepository:
        def ejecutar(self, query):
            raise exception

    http_app.dependency_overrides[get_listar_usuarios] = lambda: BrokenRepository()
    try:
        with TestClient(http_app, headers={"Authorization": "Bearer " + http_app.state.fixture_token}, raise_server_exceptions=False) as client, caplog.at_level(logging.ERROR, logger="app.http.errors"):
            response = client.get("/api/v1/usuarios")
        assert response.status_code == 500
        assert response.json()["error"]["codigo"] == code
        for output in (response.text, caplog.text):
            assert str(exception) not in output
            assert "secret-credential" not in output
            assert "SELECT password" not in output
        assert code in caplog.text and "ubicaciones=" in caplog.text
    finally:
        http_app.dependency_overrides.clear()


def test_unknown_routes_and_methods_have_consistent_errors(client):
    assert client.get("/missing").json()["error"]["codigo"] == "RUTA_NO_ENCONTRADA"
    response = client.patch("/api/v1/usuarios")
    assert response.status_code == 405 and "error" in response.json()
    assert response.headers["Allow"]


def test_unexpected_exception_does_not_escape_to_server_logging(http_app):
    class BrokenRepository:
        def ejecutar(self, query):
            raise RuntimeError("sensitive-driver-error")

    http_app.dependency_overrides[get_listar_usuarios] = lambda: BrokenRepository()
    try:
        # El valor True detecta si la excepción original llegaría al servidor ASGI.
        with TestClient(http_app, headers={"Authorization": "Bearer " + http_app.state.fixture_token}, raise_server_exceptions=True) as client:
            response = client.get("/api/v1/usuarios")
            assert response.status_code == 500
            assert "sensitive-driver-error" not in response.text
    finally:
        http_app.dependency_overrides.clear()
