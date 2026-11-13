from auth_support import PASSWORD
import pytest


BASE = "/api/v1/usuarios"
DATA = {"nombre": "Ana", "apellido": "Pérez", "email": "ana@example.com"}


@pytest.mark.parametrize("change", [
    {"nombre": " "}, {"apellido": ""}, {"email": "invalid"}, {"email": "á@example.com"},
    {"nombre": 1}, {"apellido": None}, {"email": False}, {"rol": "admin"},
    {"activo": False}, {"id": "anything"}, {"fecha_creacion": "anything"},
    {"nombre": "x" * 101}, {"apellido": "x" * 101},
])
def test_create_invalid_input_never_writes(client, memory_repository, change):
    response = client.post(BASE, json={**DATA, "password_inicial": PASSWORD, **change})
    assert response.status_code == 422
    assert "error" in response.json()
    from app.application.usuarios.dto import ListarUsuariosDatos
    assert memory_repository.listar(ListarUsuariosDatos()) == []


@pytest.mark.parametrize("payload", [{}, {"nombre": "Ana"}, [], None])
def test_incomplete_or_non_object_body(client, payload):
    assert client.post(BASE, json=payload).status_code == 422


def test_put_requires_all_fields_and_forbids_role_and_state(client):
    original = client.post(BASE, json={**DATA, "password_inicial": PASSWORD}).json()
    path = f"{BASE}/{original['id']}"
    for body in ({"nombre": "Other"}, {**DATA, "rol": "ADMIN"}, {**DATA, "activo": False}):
        assert client.put(path, json=body).status_code == 422
        assert client.get(path).json() == original


@pytest.mark.parametrize("params", [
    {"estado": "unknown"}, {"limite": 0}, {"limite": 101}, {"limite": "false"},
    {"desplazamiento": -1}, {"desplazamiento": "1.5"},
])
def test_invalid_queries(client, params):
    assert client.get(BASE, params=params).status_code == 422


@pytest.mark.parametrize("method,suffix", [("get", ""), ("put", ""), ("delete", ""), ("patch", "/reactivar")])
def test_invalid_uuid(client, method, suffix):
    kwargs = {"json": DATA} if method == "put" else {}
    assert getattr(client, method)(BASE + "/bad-uuid" + suffix, **kwargs).status_code == 422


def test_state_actions_reject_business_fields_and_accept_empty_body(client):
    original = client.post(BASE, json={**DATA, "password_inicial": PASSWORD}).json()
    path = f"{BASE}/{original['id']}"
    response = client.request("DELETE", path, json={"activo": False})
    assert response.status_code == 422 and client.get(path).json()["activo"]
    assert client.request("DELETE", path, json={}).status_code == 204
    assert client.patch(path + "/reactivar", json={"activo": True}).status_code == 422
    assert not client.get(path).json()["activo"]
    assert client.patch(path + "/reactivar", json={}).status_code == 200


def test_malformed_json_and_unknown_fields_do_not_echo_sensitive_values(client):
    marker = "sensitive-unit-test-value"
    response = client.post(BASE, content='{"secret":"' + marker, headers={"Content-Type": "application/json"})
    assert response.status_code == 422 and marker not in response.text
    response = client.post(BASE, json={**DATA, "password_inicial": PASSWORD, marker: marker})
    assert response.status_code == 422 and marker not in response.text
