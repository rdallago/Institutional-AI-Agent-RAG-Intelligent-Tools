"""Emision preparada solo bajo sustitucion aislada de la barrera en pruebas."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from auth_support import PASSWORD, bootstrap_login, seed_legacy_credential
from app.application.auth import provisioning
from app.application.auth.exceptions import (
    AprovisionamientoNoHabilitado, AprovisionamientoRechazado, CambioPasswordRequerido,
    CredencialExistente,
)
from app.application.usuarios.dto import CrearUsuarioDatos, ListarUsuariosDatos, EstadoUsuarios
from app.bootstrap import create_app
from app.domain.auth.models import Sesion
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository

INITIAL = "manual-initial-password-for-fixtures"
DEFINITIVE = "new-definitive-password-for-fixtures"
PROFILE = {"nombre": "New", "apellido": "Fixture", "email": "new@example.com"}


@pytest.fixture
def provisioning_case(backend_security):
    service, factory = backend_security
    admin_id, token = bootstrap_login(service)
    principal = service.authenticate(token)
    target = Usuario.crear(nombre="Existing", apellido="Fixture", email=Email("target@example.com"))
    with factory() as uow:
        uow.usuarios.agregar(target)
    with TestClient(create_app(repository=InMemoryUserRepository(), auth_service=service)) as client:
        yield service, factory, principal, token, target, client


def headers(token):
    return {"Authorization": "Bearer " + token}


def profile_snapshot(factory):
    with factory() as uow:
        return [(u.id, u.nombre, u.apellido, str(u.email), u.rol, u.activo, u.fecha_creacion)
                for u in uow.usuarios.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS))]


class TestClosedProvisioning:
    def test_http_barrier_cannot_be_enabled_by_environment(self, provisioning_case, monkeypatch):
        service, factory, principal, token, target, client = provisioning_case
        monkeypatch.setenv("AUTH_INITIAL_PROVISIONING_ENABLED", "true")
        monkeypatch.setenv("ENABLE_INITIAL_CREDENTIALS", "true")
        before = profile_snapshot(factory)
        for path, body in (("/api/v1/usuarios", {**PROFILE, "password_inicial": INITIAL}),
            (f"/api/v1/usuarios/{target.id}/credencial-inicial", {"password_inicial": INITIAL}),
            (f"/api/v1/usuarios/{uuid4()}/credencial-inicial", {"password_inicial": INITIAL})):
            response = client.post(path, json=body, headers=headers(token))
            assert response.status_code == 403
            assert response.json()["error"]["codigo"] == "APROVISIONAMIENTO_NO_HABILITADO"
        with pytest.raises(AprovisionamientoNoHabilitado):
            service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), INITIAL)
        with pytest.raises(AprovisionamientoNoHabilitado):
            service.assign_initial_admin(principal, target.id, INITIAL)
        with pytest.raises(AprovisionamientoNoHabilitado):
            service.manage(principal, "crear", CrearUsuarioDatos(**PROFILE))
        assert profile_snapshot(factory) == before
        with factory() as uow: assert uow.credential(target.id) is None

    def test_local_paths_are_closed_before_requesting_password(self, provisioning_case, monkeypatch, capsys):
        service, factory, _, _, target, _ = provisioning_case
        from app.presentation.cli.security import main
        def forbidden(*args): raise AssertionError("No debe pedir ni hashear secretos")
        monkeypatch.setattr("getpass.getpass", forbidden)
        monkeypatch.setattr(service.hasher, "hash", forbidden)
        for action in (
            lambda: service.bootstrap("New", "Admin", "admin-new@example.com", INITIAL),
            lambda: service.assign_initial(target.id, INITIAL),
        ):
            with pytest.raises(AprovisionamientoNoHabilitado): action()
        assert main(["bootstrap-admin", "--nombre", "New", "--apellido", "Admin",
                     "--email", "admin-new@example.com"], service=service) == 1
        assert main(["asignar-credencial-inicial", "--usuario-id", str(target.id)], service=service) == 1
        assert INITIAL not in capsys.readouterr().err
        with factory() as uow: assert uow.credential(target.id) is None

    def test_old_create_request_is_incompatible_without_partial_profile(self, provisioning_case):
        _, factory, _, token, _, client = provisioning_case
        before = profile_snapshot(factory)
        assert client.post("/api/v1/usuarios", json=PROFILE, headers=headers(token)).status_code == 422
        assert profile_snapshot(factory) == before


@pytest.mark.usefixtures("initial_provisioning_test_gate")
class TestPreparedProvisioning:
    @pytest.mark.parametrize("role", [Rol.ADMIN, Rol.USUARIO])
    def test_create_and_complete_first_login(self, provisioning_case, role, caplog):
        service, factory, _, token, _, client = provisioning_case
        response = client.post("/api/v1/usuarios", headers=headers(token),
            json={**PROFILE, "rol": role.value, "password_inicial": INITIAL})
        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"id", "nombre", "apellido", "email", "activo", "rol", "fecha_creacion"}
        uid = UUID(body["id"])
        assert response.headers["Location"].endswith(f"/api/v1/usuarios/{uid}")
        with factory() as uow:
            credential = uow.credential(uid)
            assert credential.debe_cambiar_password is True
            assert credential.password_hash == credential.password_inicial_hash
            assert credential.password_hash.startswith("$argon2id$")
            assert service.hasher.verify(credential.password_hash, INITIAL)
            assert uow.usuarios.obtener_por_id(uid).rol is role
        for secret in (INITIAL, credential.password_hash):
            assert secret not in response.text + caplog.text + repr(credential)
        first = service.login(PROFILE["email"], INITIAL, "127.0.0.2")
        assert first.debe_cambiar_password is True
        pending = service.authenticate_session(first.access_token)
        assert client.get("/api/v1/usuarios", headers=headers(first.access_token)).status_code == 403
        assert client.put("/api/v1/auth/password", headers=headers(first.access_token), json={
            "password_actual": INITIAL, "password_nueva": DEFINITIVE}).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers(first.access_token)).status_code == 401
        normal = service.login(PROFILE["email"], DEFINITIVE, "127.0.0.2")
        assert normal.debe_cambiar_password is False
        assert service.me(service.authenticate(normal.access_token)).rol is role

    @pytest.mark.parametrize("role", [Rol.ADMIN, Rol.USUARIO])
    def test_assign_to_existing_and_revoke_anomalous_sessions(self, provisioning_case, role):
        service, factory, _, token, target, client = provisioning_case
        with factory() as uow:
            uow.usuarios.actualizar(Usuario.reconstruir(id=target.id, nombre=target.nombre,
                apellido=target.apellido, email=target.email, activo=True, rol=role,
                fecha_creacion=target.fecha_creacion))
        now = service.clock()
        anomalous = Sesion(uuid4(), target.id, now, now + timedelta(seconds=900), restringida=False)
        before = profile_snapshot(factory)
        with factory() as uow: uow.put_session(anomalous)
        path = f"/api/v1/usuarios/{target.id}/credencial-inicial"
        response = client.post(path, headers=headers(token), json={"password_inicial": INITIAL})
        assert response.status_code == 204 and response.content == b""
        assert profile_snapshot(factory) == before
        with factory() as uow:
            saved = uow.credential(target.id)
            assert saved.debe_cambiar_password is True
            assert service.hasher.verify(saved.password_hash, INITIAL)
            assert uow.session(anomalous.id).revocada_at is not None
        assert service.login(str(target.email), INITIAL, "127.0.0.3").debe_cambiar_password is True
        again = client.post(path, headers=headers(token), json={"password_inicial": DEFINITIVE})
        assert again.status_code == 409 and again.json()["error"]["codigo"] == "CREDENCIAL_EXISTENTE"
        with factory() as uow: assert uow.credential(target.id) == saved

    @pytest.mark.parametrize("scenario,code", [("inactive", "USUARIO_INACTIVO_NO_APROVISIONABLE"),
        ("existing", "CREDENCIAL_EXISTENTE"), ("absent", "USUARIO_NO_ENCONTRADO")])
    def test_target_preconditions(self, provisioning_case, scenario, code):
        service, factory, _, token, target, client = provisioning_case
        uid = target.id
        if scenario == "inactive":
            with factory() as uow:
                profile = uow.usuarios.obtener_por_id(uid)
                profile.dar_de_baja()
                uow.usuarios.actualizar(profile)
        if scenario == "existing": seed_legacy_credential(service, uid)
        if scenario == "absent": uid = uuid4()
        before = profile_snapshot(factory)
        response = client.post(f"/api/v1/usuarios/{uid}/credencial-inicial", headers=headers(token),
            json={"password_inicial": INITIAL})
        assert response.status_code == (404 if scenario == "absent" else 409)
        assert response.json()["error"]["codigo"] == code
        assert profile_snapshot(factory) == before

    @pytest.mark.parametrize("actor", ["anonymous", "user", "pending_admin", "inactive"])
    def test_authorization_before_target_disclosure(self, provisioning_case, actor):
        service, factory, principal, token, target, client = provisioning_case
        with factory() as uow:
            profile = uow.usuarios.obtener_por_id(principal.usuario_id)
            if actor == "user":
                uow.usuarios.actualizar(Usuario.reconstruir(id=profile.id, nombre=profile.nombre,
                    apellido=profile.apellido, email=profile.email, activo=True, rol=Rol.USUARIO,
                    fecha_creacion=profile.fecha_creacion))
            if actor == "inactive":
                profile.dar_de_baja()
                uow.usuarios.actualizar(profile)
            if actor == "pending_admin":
                current = uow.credential(profile.id)
                uow.put_credential(replace(current, debe_cambiar_password=True,
                    password_inicial_hash=current.password_hash))
        expected = 401 if actor in ("anonymous", "inactive") else 403
        before = profile_snapshot(factory)
        for path, payload in (("/api/v1/usuarios", {**PROFILE, "password_inicial": INITIAL}),
            (f"/api/v1/usuarios/{target.id}/credencial-inicial", {"password_inicial": INITIAL}),
            (f"/api/v1/usuarios/{uuid4()}/credencial-inicial", {"password_inicial": INITIAL})):
            response = client.post(path, json=payload, headers={} if actor == "anonymous" else headers(token))
            assert response.status_code == expected
            assert str(target.email) not in response.text
            if actor == "pending_admin": assert response.json()["error"]["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"
        assert profile_snapshot(factory) == before
        with factory() as uow: assert uow.credential(target.id) is None

    @pytest.mark.parametrize("change", [{"password_inicial": "123456789012345"}, {"password_inicial": "short"},
        {"password_inicial": "x" * 129}, {"password_hash": "do-not-echo-hash"},
        {"debe_cambiar_password": False}, {"confirmacion": INITIAL}, {"rol": "root"}, {"nombre": " "}])
    def test_invalid_creation_does_not_write_or_echo(self, provisioning_case, change, caplog):
        _, factory, _, token, _, client = provisioning_case
        before = profile_snapshot(factory)
        response = client.post("/api/v1/usuarios", headers=headers(token), json={**PROFILE,
            "password_inicial": INITIAL, **change})
        assert response.status_code == 422
        assert INITIAL not in response.text + caplog.text
        assert "do-not-echo-hash" not in response.text + caplog.text
        assert profile_snapshot(factory) == before

    @pytest.mark.parametrize("failure", ["hash", "insert", "revoke"])
    def test_rollback_creation_and_assignment(self, provisioning_case, monkeypatch, failure):
        service, factory, principal, _, target, _ = provisioning_case
        before = profile_snapshot(factory)
        target_object = service.hasher if failure == "hash" else type(factory())
        method = {"hash": "hash", "insert": "insert_initial_credential", "revoke": "revoke"}[failure]
        with monkeypatch.context() as patch:
            def fail(*args, **kwargs): raise RuntimeError("injected failure")
            patch.setattr(target_object, method, fail)
            if failure != "revoke":
                with pytest.raises(RuntimeError): service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), INITIAL)
            with pytest.raises(RuntimeError): service.assign_initial_admin(principal, target.id, INITIAL)
        assert profile_snapshot(factory) == before
        with factory() as uow: assert uow.credential(target.id) is None

    def test_concurrent_assignment_has_one_winner_without_reset(self, provisioning_case):
        service, factory, principal, _, target, _ = provisioning_case
        barrier = Barrier(2)
        def run(number):
            chosen = INITIAL + str(number)
            barrier.wait(timeout=15)
            try:
                service.assign_initial_admin(principal, target.id, chosen)
                return chosen
            except (CredencialExistente, AprovisionamientoRechazado):
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = [value for value in pool.map(run, range(2)) if value]
        assert len(winners) == 1
        with factory() as uow:
            credential = uow.credential(target.id)
            assert service.hasher.verify(credential.password_hash, winners[0])
            assert credential.password_hash == credential.password_inicial_hash

    def test_creation_email_conflicts_preserve_original(self, provisioning_case):
        service, factory, principal, token, _, client = provisioning_case
        created = service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), INITIAL)
        with factory() as uow: original = uow.credential(created.id)
        for inactive in (False, True):
            if inactive:
                with factory() as uow:
                    user = uow.usuarios.obtener_por_id(created.id)
                    user.dar_de_baja()
                    uow.usuarios.actualizar(user)
            response = client.post("/api/v1/usuarios", headers=headers(token),
                json={**PROFILE, "nombre": "Do not overwrite", "password_inicial": DEFINITIVE})
            assert response.status_code == 409
            assert response.json()["error"]["codigo"] == ("USUARIO_INACTIVO_REACTIVABLE" if inactive else "USUARIO_ACTIVO_EXISTENTE")
            with factory() as uow:
                assert uow.credential(created.id) == original
                assert uow.usuarios.obtener_por_id(created.id).nombre == PROFILE["nombre"]

    def test_concurrent_creation_keeps_one_profile_and_credential(self, provisioning_case):
        from app.application.usuarios.exceptions import UsuarioActivoExistente
        service, factory, principal, _, _, _ = provisioning_case
        before = profile_snapshot(factory)
        barrier = Barrier(2)
        def run(number):
            chosen = INITIAL + str(number)
            barrier.wait(timeout=15)
            try:
                created = service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), chosen)
                return created.id, chosen
            except UsuarioActivoExistente:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = [value for value in pool.map(run, range(2)) if value]
        assert len(winners) == 1
        assert len(profile_snapshot(factory)) == len(before) + 1
        with factory() as uow:
            credential = uow.credential(winners[0][0])
            assert service.hasher.verify(credential.password_hash, winners[0][1])

    @pytest.mark.postgres
    def test_commit_failure_rolls_back_new_profile_and_credential(self, postgres_repository, postgres_resources, monkeypatch):
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import Session
        from auth_support import build_auth, auth_config
        from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
        from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia
        _, _, sessions = postgres_resources
        factory = lambda: PostgresSecurityUnitOfWork(sessions)
        service = build_auth(factory, auth_config())
        _, token = bootstrap_login(service)
        principal = service.authenticate(token)
        before = profile_snapshot(factory)
        state = {"inserted": False}
        original_insert = PostgresSecurityUnitOfWork.insert_initial_credential
        original_commit = Session.commit
        def insert(self, credential):
            original_insert(self, credential)
            state["inserted"] = True
        def commit(self):
            if state["inserted"]: raise SQLAlchemyError("injected commit failure")
            return original_commit(self)
        with monkeypatch.context() as patch:
            patch.setattr(PostgresSecurityUnitOfWork, "insert_initial_credential", insert)
            patch.setattr(Session, "commit", commit)
            with pytest.raises(ErrorPersistencia):
                service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), INITIAL)
        assert profile_snapshot(factory) == before
        with factory() as uow:
            assert uow.usuarios.obtener_por_email(Email(PROFILE["email"])) is None

    def test_actor_revalidated_after_hash(self, provisioning_case, monkeypatch):
        service, factory, principal, _, _, _ = provisioning_case
        before = profile_snapshot(factory)
        original = service.hasher.hash
        def hashing(raw):
            with factory() as uow:
                current = uow.credential(principal.usuario_id)
                uow.put_credential(replace(current, debe_cambiar_password=True,
                    password_inicial_hash=current.password_hash))
            return original(raw)
        monkeypatch.setattr(service.hasher, "hash", hashing)
        with pytest.raises(CambioPasswordRequerido):
            service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), INITIAL)
        assert profile_snapshot(factory) == before

    def test_barrier_rechecked_before_writes(self, provisioning_case, monkeypatch):
        service, factory, principal, _, _, _ = provisioning_case
        before = profile_snapshot(factory)
        original = service.hasher.hash
        def disabled(): raise AprovisionamientoNoHabilitado()
        def hashing(raw):
            monkeypatch.setattr(provisioning, "require_initial_provisioning_enabled", disabled)
            return original(raw)
        monkeypatch.setattr(service.hasher, "hash", hashing)
        with pytest.raises(AprovisionamientoNoHabilitado):
            service.create_with_initial(principal, CrearUsuarioDatos(**PROFILE), INITIAL)
        assert profile_snapshot(factory) == before

    def test_cli_initial_is_pending_and_keeps_bootstrap_closure(self, backend_security):
        service, factory = backend_security
        uid = service.bootstrap("First", "Admin", "first@example.com", INITIAL)
        with factory() as uow:
            credential = uow.credential(uid)
            assert credential.debe_cambiar_password is True
            assert credential.password_hash == credential.password_inicial_hash
        assert service.login("first@example.com", INITIAL, "127.0.0.2").debe_cambiar_password is True
        with pytest.raises(AprovisionamientoRechazado):
            service.bootstrap("Second", "Admin", "second@example.com", INITIAL)
