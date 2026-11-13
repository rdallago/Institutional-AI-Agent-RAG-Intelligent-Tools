import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.bootstrap import create_app
from postgres_support import require_test_connection
from auth_support import PASSWORD, auth_config, build_auth, bootstrap_login
from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork


pytestmark = [pytest.mark.postgres, pytest.mark.usefixtures("initial_provisioning_test_gate")]
BASE = "/api/v1/usuarios"
DATA = {"nombre": "Ana", "apellido": "Pérez", "email": "http@example.com"}


def test_http_persistence_survives_clients_and_owned_engines(postgres_repository, postgres_resources, monkeypatch):
    import app.bootstrap as bootstrap

    config, engine, sessions = postgres_resources
    security_config = auth_config()
    service = build_auth(lambda: PostgresSecurityUnitOfWork(sessions), security_config)
    admin_id, token = bootstrap_login(service)
    headers = {"Authorization": "Bearer " + token}
    config.require_test_database()
    with engine.connect() as connection:
        require_test_connection(connection, config)
    owned = []
    original = bootstrap.crear_persistencia_postgresql

    def track(selected_config):
        selected_config.require_test_database()
        result = original(selected_config)
        owned.append(result[0])
        return result

    monkeypatch.setattr(bootstrap, "crear_persistencia_postgresql", track)
    with TestClient(create_app(database_config=config, auth_config=security_config), headers=headers) as client:
        created = client.post(BASE, json={**DATA, "password_inicial": PASSWORD})
        assert created.status_code == 201
        body = created.json()
    assert owned[0].pool.checkedout() == 0
    with TestClient(create_app(database_config=config, auth_config=security_config), headers=headers) as client:
        path = f"{BASE}/{body['id']}"
        assert client.get(path).json() == body
        assert client.put(path, json={**DATA, "apellido": "Díaz"}).status_code == 200
        assert client.delete(path).status_code == 204
        assert client.delete(path).content == b""
        assert [item["id"] for item in client.get(BASE).json()] == [str(admin_id)]
        assert len(client.get(BASE, params={"estado": "inactivos"}).json()) == 1
        with engine.connect() as connection:
            row = connection.execute(text("SELECT activo, id::text FROM public.usuarios WHERE id=:id"), {"id": body["id"]}).one()
            assert tuple(row) == (False, body["id"])
        conflict = client.post(BASE, json={**DATA, "password_inicial": PASSWORD})
        assert conflict.status_code == 409
        assert conflict.json()["error"]["usuario_id"] == body["id"]
        restored = client.patch(path + "/reactivar")
        assert restored.status_code == 200 and restored.json()["activo"]
        assert restored.json()["fecha_creacion"] == body["fecha_creacion"]
        assert client.patch(path + "/reactivar").json() == restored.json()
    assert owned[1].pool.checkedout() == 0


def test_invalid_stored_email_returns_500_not_request_422(postgres_repository, postgres_resources, caplog):
    config, engine, sessions = postgres_resources
    security_config = auth_config()
    service = build_auth(lambda: PostgresSecurityUnitOfWork(sessions), security_config)
    admin_id, token = bootstrap_login(service)
    headers = {"Authorization": "Bearer " + token}
    with TestClient(create_app(repository=postgres_repository, auth_service=service), headers=headers) as client:
        created = client.post(BASE, json={**DATA, "password_inicial": PASSWORD}).json()
        with engine.begin() as connection:
            require_test_connection(connection, config)
            # El CHECK exige normalización; el formato completo pertenece al dominio.
            connection.execute(text("UPDATE public.usuarios SET email='invalid-stored-value' WHERE id=:id"), {"id": created["id"]})
        for path in (BASE, f"{BASE}/{created['id']}"):
            response = client.get(path)
            assert response.status_code == 500
            assert response.json()["error"]["codigo"] == "ERROR_PERSISTENCIA"
            assert "invalid-stored-value" not in response.text
        assert "invalid-stored-value" not in caplog.text
