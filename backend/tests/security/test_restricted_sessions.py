"""Sesiones y permisos reales; fixtures ficticias en memoria y usuarios_test."""
from dataclasses import asdict, replace
from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from auth_support import PASSWORD
from app.application.auth.exceptions import (
    AutenticacionRequerida, CambioPasswordRequerido, CredencialesInvalidas,
)
from app.application.auth.service import Principal
from app.application.usuarios.dto import (
    CrearUsuarioDatos, EstadoUsuarios, ListarUsuariosDatos, ModificarUsuarioDatos, UsuarioResultado,
)
from app.bootstrap import create_app
from app.domain.auth.models import Credencial
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


@pytest.fixture(params=[Rol.ADMIN, Rol.USUARIO])
def restricted(request, backend_security):
    service, factory = backend_security
    now = service.clock()
    user = Usuario.crear(nombre="Restricted", apellido="Fixture",
        email=Email("restricted@example.com"), rol=request.param)
    other = Usuario.crear(nombre="Other", apellido="Fixture", email=Email("other@example.com"))
    encoded = service.hasher.hash(PASSWORD)
    with factory() as uow:
        uow.usuarios.agregar(user)
        uow.usuarios.agregar(other)
        uow.put_credential(Credencial(user.id, encoded, now, now,
            debe_cambiar_password=False, password_inicial_hash=None))
    normal = service.login(str(user.email), PASSWORD, "127.0.0.2")
    with factory() as uow:
        uow.put_credential(replace(uow.credential(user.id),
            debe_cambiar_password=True, password_inicial_hash=encoded))
    pending = service.login(str(user.email), PASSWORD, "127.0.0.2")
    with TestClient(create_app(repository=InMemoryUserRepository(), auth_service=service)) as client:
        yield service, factory, user, other, normal, pending, client


def headers(result):
    return {"Authorization": "Bearer " + result.access_token}


def snapshot(factory):
    with factory() as uow:
        profiles = uow.usuarios.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS))
        return [UsuarioResultado.desde_entidad(profile) for profile in profiles]


def test_login_persists_scope_and_keeps_jwt_contract(restricted):
    service, factory, user, _, normal, pending, client = restricted
    assert normal.debe_cambiar_password is False
    assert pending.debe_cambiar_password is True
    for result, expected in ((normal, False), (pending, True)):
        user_id, session_id = service.tokens.verify(result.access_token)
        with factory() as uow:
            session = uow.session(session_id)
            assert user_id == session.usuario_id == user.id
            assert session.restringida is expected
            assert session.expira_at - session.creada_at == timedelta(seconds=900)
        claims = jwt.decode(result.access_token, options={"verify_signature": False})
        assert set(claims) == {"sub", "jti", "iat", "exp", "iss", "aud", "token_use"}
        assert claims["exp"] - claims["iat"] == 900
        assert claims["token_use"] == "access"
    response = client.post("/api/v1/auth/login", json={"email": str(user.email), "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["debe_cambiar_password"] is True
    assert response.json()["expires_in"] == 900
    assert response.headers["Cache-Control"] == "no-store"


def test_all_normal_routes_deny_admin_and_user_pending_without_leaks(restricted, caplog):
    _, factory, user, other, _, pending, client = restricted
    before = snapshot(factory)
    routes = [
        ("POST", f"/api/v1/usuarios/{other.id}/credencial-inicial", {"password_inicial": PASSWORD}),
        ("GET", "/api/v1/usuarios", None),
        ("GET", f"/api/v1/usuarios/{user.id}", None),
        ("GET", f"/api/v1/usuarios/{other.id}", None),
        ("GET", f"/api/v1/usuarios/{uuid4()}", None),
        ("POST", "/api/v1/usuarios", {"nombre": "New", "apellido": "Fixture", "email": "new@example.com", "rol": "ADMIN"}),
        ("PUT", f"/api/v1/usuarios/{other.id}", {"nombre": "Edited", "apellido": "Fixture", "email": "edited@example.com"}),
        ("DELETE", f"/api/v1/usuarios/{other.id}", None),
        ("PATCH", f"/api/v1/usuarios/{other.id}/reactivar", None),
    ]
    schema = client.get("/openapi.json").json()
    protected = {(method.upper(), path) for path, methods in schema["paths"].items()
                 if path.startswith("/api/v1/usuarios") for method in methods}
    # Inventario exhaustivo: una ruta nueva exige ampliar la matriz.
    assert protected == {
        ("GET", "/api/v1/usuarios"), ("POST", "/api/v1/usuarios"),
        ("POST", "/api/v1/usuarios/{id}/credencial-inicial"),
        ("GET", "/api/v1/usuarios/{id}"), ("PUT", "/api/v1/usuarios/{id}"),
        ("DELETE", "/api/v1/usuarios/{id}"), ("PATCH", "/api/v1/usuarios/{id}/reactivar"),
    }
    for method, path, body in routes:
        response = client.request(method, path, headers=headers(pending), json=body)
        assert response.status_code == 403
        assert response.json() == {"error": {"codigo": "CAMBIO_PASSWORD_REQUERIDO",
            "mensaje": "Debe cambiar su contraseña antes de continuar."}}
        for forbidden in (str(other.email), str(other.id), PASSWORD, pending.access_token):
            assert forbidden not in response.text + caplog.text
    assert snapshot(factory) == before


def test_application_service_does_not_trust_principal_or_role(restricted):
    service, factory, user, other, _, pending, _ = restricted
    _, session_id = service.tokens.verify(pending.access_token)
    principal = Principal(user.id, session_id)  # Sin dependencias FastAPI.
    before = snapshot(factory)
    cases = [
        ("listar", (ListarUsuariosDatos(),)),
        ("obtener", (user.id,)), ("obtener", (other.id,)),
        ("crear", (CrearUsuarioDatos(nombre="New", apellido="Fixture", email="new@example.com", rol=Rol.ADMIN),)),
        ("modificar", (other.id, ModificarUsuarioDatos(nombre="Edit", apellido="Fixture", email="edited@example.com"))),
        ("baja", (other.id,)), ("reactivar", (other.id,)),
    ]
    for action, args in cases:
        with pytest.raises(CambioPasswordRequerido):
            service.manage(principal, action, *args)
    with pytest.raises(CambioPasswordRequerido):
        service.authenticate(pending.access_token)
    assert service.authenticate_session(pending.access_token) == principal
    assert snapshot(factory) == before


def test_me_is_minimal_including_old_normal_session(restricted):
    service, _, user, _, normal, pending, client = restricted
    for result in (normal, pending):
        principal = service.authenticate_session(result.access_token)
        assert asdict(service.me(principal)) == {"id": user.id, "debe_cambiar_password": True}
        response = client.get("/api/v1/auth/me", headers=headers(result))
        assert response.status_code == 200
        assert response.json() == {"id": str(user.id), "debe_cambiar_password": True}
        assert response.headers["Cache-Control"] == "no-store"


def test_old_normal_session_cannot_bypass_new_credential_state(restricted):
    service, _, _, _, normal, _, client = restricted
    with pytest.raises(CambioPasswordRequerido):
        service.authenticate(normal.access_token)
    response = client.get("/api/v1/usuarios", headers=headers(normal))
    assert response.status_code == 403
    assert response.json()["error"]["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"


def test_restricted_session_never_promotes_when_flag_cleared(restricted):
    service, factory, user, _, normal, pending, client = restricted
    with factory() as uow:
        uow.put_credential(replace(uow.credential(user.id), debe_cambiar_password=False))
    for path in ("/api/v1/auth/me", "/api/v1/usuarios", f"/api/v1/usuarios/{user.id}"):
        response = client.get(path, headers=headers(pending))
        assert response.status_code == 401
        assert response.json()["error"]["codigo"] == "AUTENTICACION_REQUERIDA"
    with pytest.raises(AutenticacionRequerida):
        service.authenticate_session(pending.access_token)
    _, sid = service.tokens.verify(pending.access_token)
    with pytest.raises(AutenticacionRequerida):
        service.me(Principal(user.id, sid))
    # Un estado definitivo historico con sesion normal conserva permisos reales.
    principal = service.authenticate(normal.access_token)
    assert service.me(principal).debe_cambiar_password is False
    response = client.get("/api/v1/auth/me", headers=headers(normal))
    assert response.status_code == 200
    assert response.json()["rol"] == user.rol.value
    assert response.json()["debe_cambiar_password"] is False
    assert client.get("/api/v1/usuarios", headers=headers(normal)).status_code == (200 if user.rol is Rol.ADMIN else 403)


def test_restricted_logout_is_idempotent_and_revokes(restricted):
    service, _, _, _, _, pending, client = restricted
    assert client.post("/api/v1/auth/logout", headers=headers(pending)).status_code == 204
    assert client.post("/api/v1/auth/logout", headers=headers(pending)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers(pending)).status_code == 401
    with pytest.raises(AutenticacionRequerida):
        service.authenticate_session(pending.access_token)


def test_password_endpoint_completes_pending_flow_and_requires_new_login(restricted):
    service, factory, user, _, _, pending, client = restricted
    with factory() as uow:
        initial = uow.credential(user.id)
    response = client.put("/api/v1/auth/password", headers=headers(pending), json={
        "password_actual": PASSWORD + "wrong", "password_nueva": PASSWORD + "-new"})
    assert response.status_code == 401
    assert response.json()["error"]["codigo"] == "CREDENCIALES_INVALIDAS"
    assert client.get("/api/v1/auth/me", headers=headers(pending)).status_code == 200
    # Una nueva password completa el flujo y revoca la sesion anterior.
    response = client.put("/api/v1/auth/password", headers=headers(pending), json={
        "password_actual": PASSWORD, "password_nueva": PASSWORD + "-definitive"})
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers(pending)).status_code == 401
    with factory() as uow:
        saved = uow.credential(user.id)
        assert saved.debe_cambiar_password is False
        assert saved.password_inicial_hash == initial.password_inicial_hash
    result = service.login(str(user.email), PASSWORD + "-definitive", "127.0.0.4")
    assert result.debe_cambiar_password is False


@pytest.mark.parametrize("mutation", ["inactive", "missing_credential", "revoked", "expired", "binding"])
def test_invalid_session_remains_401_before_pending_error(restricted, mutation):
    service, factory, user, _, _, pending, client = restricted
    _, sid = service.tokens.verify(pending.access_token)
    with factory() as uow:
        if mutation == "inactive":
            profile = uow.usuarios.obtener_por_id(user.id)
            profile.dar_de_baja()
            uow.usuarios.actualizar(profile)
        elif mutation == "missing_credential":
            if hasattr(uow, "db"):
                from app.infrastructure.persistence.models.auth import CredencialModel
                uow.db.delete(uow.db.get(CredencialModel, user.id))
            else:
                del uow.store.credentials[user.id]
        else:
            session = uow.session(sid)
            if mutation == "revoked": session = replace(session, revocada_at=service.clock())
            if mutation == "expired":
                session = replace(session, creada_at=service.clock()-timedelta(seconds=1000),
                                  expira_at=service.clock()-timedelta(seconds=1))
            if mutation == "binding":
                # Otra identidad existente evita que la FK sea la causa del rechazo.
                other = uow.usuarios.obtener_por_email(Email("other@example.com"))
                session = replace(session, usuario_id=other.id)
            uow.put_session(session)
    for path in ("/api/v1/auth/me", "/api/v1/usuarios"):
        response = client.get(path, headers=headers(pending))
        assert response.status_code == 401
        assert response.json()["error"]["codigo"] == "AUTENTICACION_REQUERIDA"


def test_public_routes_and_login_rejection_are_unchanged(restricted):
    _, factory, user, _, _, pending, client = restricted
    assert client.get("/docs", headers=headers(pending)).status_code == 200
    assert client.get("/openapi.json", headers=headers(pending)).status_code == 200
    responses = []
    for email in (str(user.email), "missing@example.com"):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD + "wrong"})
        assert response.status_code == 401
        responses.append(response.json())
    assert responses[0] == responses[1]
    with factory() as uow:
        profile = uow.usuarios.obtener_por_id(user.id)
        profile.dar_de_baja()
        uow.usuarios.actualizar(profile)
    response = client.post("/api/v1/auth/login", json={"email": str(user.email), "password": PASSWORD})
    assert response.status_code == 401 and response.json() == responses[0]


def test_state_change_after_dependency_is_rechecked_by_application(restricted):
    service, factory, user, _, normal, _, _ = restricted
    with factory() as uow:
        uow.put_credential(replace(uow.credential(user.id), debe_cambiar_password=False))
    principal = service.authenticate(normal.access_token)
    with factory() as uow:
        uow.put_credential(replace(uow.credential(user.id), debe_cambiar_password=True))
    with pytest.raises(CambioPasswordRequerido):
        service.manage(principal, "obtener", user.id)


def test_login_reads_pending_state_again_before_persisting(restricted, monkeypatch):
    service, factory, user, _, _, _, _ = restricted
    with factory() as uow:
        uow.put_credential(replace(uow.credential(user.id), debe_cambiar_password=False))
    original = service.hasher.verify

    def verify(encoded, raw):
        valid = original(encoded, raw)
        with factory() as uow:
            uow.put_credential(replace(uow.credential(user.id), debe_cambiar_password=True))
        return valid

    monkeypatch.setattr(service.hasher, "verify", verify)
    result = service.login(str(user.email), PASSWORD, "127.0.0.7")
    assert result.debe_cambiar_password is True
    _, sid = service.tokens.verify(result.access_token)
    with factory() as uow:
        assert uow.session(sid).restringida is True
