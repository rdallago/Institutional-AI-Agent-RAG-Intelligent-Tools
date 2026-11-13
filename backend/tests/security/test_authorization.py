from dataclasses import replace
from uuid import uuid4

import pytest

from auth_support import PASSWORD
from app.application.usuarios.dto import CrearUsuarioDatos, ListarUsuariosDatos
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.domain.usuarios.rol import Rol
from app.application.auth.exceptions import PermisoDenegado, AutenticacionRequerida


def ordinary_user(store, service):
    user = CrearUsuario(store.users).ejecutar(CrearUsuarioDatos(nombre="User", apellido="Test", email="user@example.com"))
    from auth_support import seed_legacy_credential
    seed_legacy_credential(service, user.id)
    token = service.login(user.email, PASSWORD, "127.0.0.6").access_token
    return user, token


@pytest.mark.parametrize("method,path", [("get","/api/v1/usuarios"),("get","/api/v1/auth/me"),
    ("delete","/api/v1/usuarios/00000000-0000-0000-0000-000000000001"),
    ("post","/api/v1/auth/logout")])
def test_missing_token_is_401(security_client, method, path):
    response = getattr(security_client, method)(path)
    assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"


def test_user_permissions_and_privilege_escalation(security, security_client):
    store, service, _, admin_id, _ = security
    user, token = ordinary_user(store, service)
    headers = {"Authorization": "Bearer " + token}
    assert security_client.get("/api/v1/auth/me", headers=headers).json()["id"] == str(user.id)
    assert security_client.get(f"/api/v1/usuarios/{user.id}", headers=headers).status_code == 200
    for target in (admin_id, uuid4()):
        response = security_client.get(f"/api/v1/usuarios/{target}", headers=headers)
        assert response.status_code == 404
    assert security_client.get("/api/v1/usuarios", headers=headers).status_code == 403
    payload = {"nombre":"Attacker","apellido":"Test","email":"attack@example.com","rol":"ADMIN"}
    assert security_client.post("/api/v1/usuarios", json={**payload, "password_inicial": PASSWORD}, headers=headers).status_code == 403
    assert security_client.put(f"/api/v1/usuarios/{user.id}", json={k:v for k,v in payload.items() if k!='rol'}, headers=headers).status_code == 403
    assert security_client.delete(f"/api/v1/usuarios/{admin_id}", headers=headers).status_code == 403
    assert security_client.patch(f"/api/v1/usuarios/{user.id}/reactivar", headers=headers).status_code == 403


def test_admin_policy_and_baja_revocation(security, security_client):
    store, service, _, admin_id, admin_token = security
    user, user_token = ordinary_user(store, service)
    headers = {"Authorization":"Bearer " + admin_token}
    assert security_client.delete(f"/api/v1/usuarios/{admin_id}", headers=headers).status_code == 403
    assert security_client.delete(f"/api/v1/usuarios/{user.id}", headers=headers).status_code == 204
    assert security_client.get("/api/v1/auth/me", headers={"Authorization":"Bearer " + user_token}).status_code == 401
    assert security_client.patch(f"/api/v1/usuarios/{user.id}/reactivar", headers=headers).status_code == 200
    assert security_client.get("/api/v1/auth/me", headers={"Authorization":"Bearer " + user_token}).status_code == 401


def test_current_role_is_read_from_backend(security):
    store, service, _, admin_id, token = security
    entity = store.users.obtener_por_id(admin_id)
    from app.domain.usuarios.usuario import Usuario
    store.users.actualizar(Usuario.reconstruir(id=entity.id, nombre=entity.nombre, apellido=entity.apellido,
        email=entity.email, activo=True, rol=Rol.USUARIO, fecha_creacion=entity.fecha_creacion))
    with pytest.raises(PermisoDenegado): service.manage(service.authenticate(token), "listar", ListarUsuariosDatos())


def test_login_errors_rate_limit_and_no_secrets(security, security_client, caplog):
    secrets = ["absent@example.com", PASSWORD + "wrong"]
    bodies = []
    for email in ("absent@example.com", "operator@example.com"):
        response = security_client.post("/api/v1/auth/login", json={"email":email,"password":PASSWORD+"wrong"})
        assert response.status_code == 401
        bodies.append(response.json())
    assert bodies[0] == bodies[1]
    for _ in range(6):
        response = security_client.post("/api/v1/auth/login", json={"email":"absent@example.com","password":PASSWORD})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    for value in secrets:
        assert value not in response.text and value not in caplog.text


def test_change_password_http_and_logout(security, security_client):
    _, service, _, _, token = security
    headers = {"Authorization":"Bearer " + token}
    response = security_client.put("/api/v1/auth/password", json={"password_actual":PASSWORD,"password_nueva":PASSWORD+"new"}, headers=headers)
    assert response.status_code == 204 and response.content == b""
    assert security_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    response = security_client.post("/api/v1/auth/login", json={"email":"operator@example.com","password":PASSWORD+"new"})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    headers = {"Authorization":"Bearer " + response.json()["access_token"]}
    assert security_client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert security_client.post("/api/v1/auth/logout", headers=headers).status_code == 204


def test_openapi_security(security_client):
    schema = security_client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    for path, methods in schema["paths"].items():
        for operation in methods.values():
            if path != "/api/v1/auth/login":
                assert operation["security"] == [{"BearerAuth": []}]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
