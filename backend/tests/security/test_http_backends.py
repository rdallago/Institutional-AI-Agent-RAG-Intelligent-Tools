import pytest
from fastapi.testclient import TestClient

from app.bootstrap import create_app
from auth_support import PASSWORD, bootstrap_login
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


def test_auth_http_end_to_end_both_backends(backend_security):
    service, _ = backend_security
    admin_id, _ = bootstrap_login(service)
    # El repositorio HTTP no es la autoridad; el servicio utiliza su UoW real.
    with TestClient(create_app(repository=InMemoryUserRepository(), auth_service=service)) as client:
        response = client.post("/api/v1/auth/login", json={"email":"operator@example.com","password":PASSWORD})
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization":"Bearer " + token}
        assert client.get("/api/v1/auth/me", headers=headers).json()["id"] == str(admin_id)
        assert client.put("/api/v1/auth/password", headers=headers,
            json={"password_actual":PASSWORD,"password_nueva":PASSWORD+"new"}).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        response = client.post("/api/v1/auth/login", json={"email":"operator@example.com","password":PASSWORD+"new"})
        headers = {"Authorization":"Bearer " + response.json()["access_token"]}
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_valid_jwt_never_bypasses_unavailable_persistence(security, security_client, monkeypatch, caplog):
    from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia
    _, service, _, _, token = security
    def unavailable():
        raise ErrorPersistencia("sensitive-unavailable-detail")
    monkeypatch.setattr(service,"uow_factory",unavailable)
    response = security_client.get("/api/v1/auth/me",headers={"Authorization":"Bearer "+token})
    assert response.status_code == 500
    assert "sensitive-unavailable-detail" not in response.text+caplog.text


def test_proxy_header_does_not_change_limit_bucket(security_client):
    for number in range(6):
        response = security_client.post("/api/v1/auth/login",json={"email":"absent@example.com","password":PASSWORD},
            headers={"X-Forwarded-For":f"10.0.0.{number}"})
    assert response.status_code == 429 and response.headers["Retry-After"]
