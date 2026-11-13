from auth_support import PASSWORD
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario


BASE = "/api/v1/usuarios"
DATA = {"nombre": "Ana", "apellido": "Pérez", "email": "ana@example.com"}


def test_create_serializes_domain_and_location(client):
    response = client.post(BASE, json={**DATA, "password_inicial": PASSWORD, "nombre": " Ana ", "email": " ANA@example.com "})
    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["nombre"] == "Ana" and body["email"] == "ana@example.com"
    assert body["rol"] == "USUARIO" and body["activo"] is True
    assert datetime.fromisoformat(body["fecha_creacion"]).utcoffset() == timedelta(0)
    assert response.headers["Location"] == f"http://testserver{BASE}/{body['id']}"
    assert client.get(response.headers["Location"]).json() == body


def test_create_accepts_existing_admin_role_without_authorization_feature(client):
    assert client.post(BASE, json={**DATA, "password_inicial": PASSWORD, "rol": "ADMIN"}).json()["rol"] == "ADMIN"


def test_full_lifecycle_preserves_identity_date_role_and_idempotence(client, memory_repository):
    original = client.post(BASE, json={**DATA, "password_inicial": PASSWORD, "rol": "ADMIN"}).json()
    path = f"{BASE}/{original['id']}"
    edited = client.put(path, json={**DATA, "apellido": "Díaz"})
    assert edited.status_code == 200
    assert edited.json() == {**original, "apellido": "Díaz"}
    for _ in range(2):
        response = client.delete(path)
        assert response.status_code == 204 and response.content == b""
        assert "content-type" not in response.headers
    assert not client.get(path).json()["activo"]
    assert client.get(BASE).json() == []
    assert client.get(BASE, params={"estado": "inactivos"}).json() == [{**edited.json(), "activo": False}]
    assert memory_repository.obtener_por_id(UUID(original["id"])) is not None
    # Edición de inactivo no lo reactiva.
    changed = client.put(path, json={**DATA, "nombre": "Ana María"}).json()
    assert changed["activo"] is False
    for _ in range(2):
        response = client.patch(path + "/reactivar")
        assert response.status_code == 200
        assert response.json() == {**changed, "activo": True}
    assert client.get(path).json()["fecha_creacion"] == original["fecha_creacion"]


def test_email_conflicts_and_explicit_reactivation(client):
    original = client.post(BASE, json={**DATA, "password_inicial": PASSWORD}).json()
    assert client.post(BASE, json={**DATA, "password_inicial": PASSWORD}).json()["error"]["codigo"] == "USUARIO_ACTIVO_EXISTENTE"
    other = client.post(BASE, json={**DATA, "password_inicial": PASSWORD, "email": "other@example.com"}).json()
    path = f"{BASE}/{original['id']}"
    client.delete(path)
    conflict = client.post(BASE, json={**DATA, "password_inicial": PASSWORD, "nombre": "Changed"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["codigo"] == "USUARIO_INACTIVO_REACTIVABLE"
    assert conflict.json()["error"]["usuario_id"] == original["id"]
    assert client.get(path).json() == {**original, "activo": False}
    response = client.put(f"{BASE}/{other['id']}", json={**DATA, "nombre": "Changed"})
    assert response.status_code == 409 and response.json()["error"]["codigo"] == "EMAIL_EN_USO"
    assert client.get(f"{BASE}/{other['id']}").json() == other


def test_list_defaults_filter_before_pagination_and_stable_order(client, memory_repository):
    instant = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    for number in reversed(range(1, 26)):
        memory_repository.agregar(Usuario.reconstruir(
            id=UUID(int=number), nombre="Ana", apellido="Pérez", email=Email(f"a{number}@example.com"),
            activo=number % 2 == 0, rol=Rol.USUARIO, fecha_creacion=instant,
        ))
    assert [UUID(item["id"]).int for item in client.get(BASE).json()] == list(range(2, 26, 2))
    response = client.get(BASE, params={"estado": "inactivos", "limite": 2, "desplazamiento": 1})
    assert [UUID(item["id"]).int for item in response.json()] == [3, 5]
    assert len(client.get(BASE, params={"estado": "todos"}).json()) == 20
    assert client.get(BASE, params={"desplazamiento": 100}).json() == []


@pytest.mark.parametrize("method,suffix", [("get", ""), ("put", ""), ("delete", ""), ("patch", "/reactivar")])
def test_missing_user_is_404(client, method, suffix):
    kwargs = {"json": DATA} if method == "put" else {}
    response = getattr(client, method)(f"{BASE}/{uuid4()}{suffix}", **kwargs)
    assert response.status_code == 404
    assert response.json()["error"]["codigo"] == "USUARIO_NO_ENCONTRADO"
