"""Cambio seguro y limites compartidos; nunca utiliza datos de desarrollo."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from auth_support import PASSWORD
from app.application.auth.exceptions import (
    AutenticacionRequerida, CredencialesInvalidas, LimiteIntentos,
    PasswordInvalida, PasswordReutilizada,
)
from app.bootstrap import create_app
from app.domain.auth.models import Credencial
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository

NEW_PASSWORD = "a-different-definitive-password"
IP = "127.0.0.8"


@pytest.fixture(params=[False, True], ids=["historical", "pending"])
def password_case(request, backend_security):
    service, factory = backend_security
    clock = [datetime(2026, 10, 30, 12, 0, 10, tzinfo=UTC)]
    service.clock = service.tokens.clock = lambda: clock[0]
    user = Usuario.crear(nombre="Password", apellido="Fixture", email=Email("password@example.com"))
    encoded = service.hasher.hash(PASSWORD)
    with factory() as uow:
        uow.usuarios.agregar(user)
        uow.put_credential(Credencial(user.id, encoded, clock[0], clock[0],
            debe_cambiar_password=request.param, password_inicial_hash=encoded if request.param else None))
    first = service.login(str(user.email), PASSWORD, IP).access_token
    second = service.login(str(user.email), PASSWORD, IP).access_token
    principal = service.authenticate_session(first)
    with TestClient(create_app(repository=InMemoryUserRepository(), auth_service=service)) as client:
        yield service, factory, user, principal, first, second, clock, client


def auth(token):
    return {"Authorization": "Bearer " + token}


def saved(case):
    service, factory, user, principal, *_ = case
    with factory() as uow:
        return uow.credential(user.id), uow.session(principal.sesion_id)


def test_http_change_revokes_all_sessions_and_requires_normal_new_login(password_case):
    service, factory, user, principal, first, second, _, client = password_case
    before, _ = saved(password_case)
    response = client.put("/api/v1/auth/password", headers=auth(first), json={
        "password_actual": PASSWORD, "password_nueva": NEW_PASSWORD})
    assert response.status_code == 204 and response.content == b""
    credential, session = saved(password_case)
    assert credential.debe_cambiar_password is False
    assert credential.password_inicial_hash == before.password_inicial_hash
    assert credential.creada_at == before.creada_at
    assert credential.password_hash.startswith("$argon2id$")
    assert service.hasher.verify(credential.password_hash, NEW_PASSWORD)
    assert not service.hasher.verify(credential.password_hash, PASSWORD)
    assert session.revocada_at is not None
    # Ni siquiera el cambio de flag promueve una sesion anterior.
    for token in (first, second):
        assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401
        with pytest.raises(AutenticacionRequerida): service.authenticate_session(token)
    with pytest.raises(CredencialesInvalidas): service.login(str(user.email), PASSWORD, IP)
    result = service.login(str(user.email), NEW_PASSWORD, IP)
    assert result.debe_cambiar_password is False
    current = service.authenticate(result.access_token)
    with factory() as uow:
        assert uow.session(current.sesion_id).restringida is False
    response = client.get("/api/v1/auth/me", headers=auth(result.access_token))
    assert response.status_code == 200 and response.json()["debe_cambiar_password"] is False


def test_wrong_current_preserves_account_and_session(password_case):
    service, _, _, principal, token, _, _, client = password_case
    before = saved(password_case)
    response = client.put("/api/v1/auth/password", headers=auth(token), json={
        "password_actual": PASSWORD + "wrong", "password_nueva": NEW_PASSWORD})
    assert response.status_code == 401
    assert response.json()["error"]["codigo"] == "CREDENCIALES_INVALIDAS"
    assert saved(password_case) == before
    assert service.authenticate_session(token) == principal


@pytest.mark.parametrize("invalid", ["short", "x" * 129, "123456789012345", "\ud800" * 15])
def test_policy_and_correct_current_release_pair_reservation(password_case, invalid):
    service, _, user, principal, _, _, _, _ = password_case
    before = saved(password_case)
    with pytest.raises(PasswordInvalida):
        service.change_password(principal, PASSWORD, invalid, ip=IP)
    assert saved(password_case) == before
    # La password correcta libera solo su propio cupo, aunque la nueva sea invalida.
    for _ in range(5): service.limiter.check(str(user.email), IP, service.clock())
    with pytest.raises(LimiteIntentos): service.limiter.check(str(user.email), IP, service.clock())


def test_rejects_current_password_and_keeps_session(password_case):
    service, _, _, principal, token, _, _, client = password_case
    before = saved(password_case)
    response = client.put("/api/v1/auth/password", headers=auth(token), json={
        "password_actual": PASSWORD, "password_nueva": PASSWORD})
    assert response.status_code == 422
    assert response.json()["error"]["codigo"] == "PASSWORD_REUTILIZADA"
    assert saved(password_case) == before
    assert service.authenticate_session(token) == principal


def test_initial_is_rejected_on_later_voluntary_change(password_case):
    service, factory, user, principal, _, _, _, _ = password_case
    # Una credencial historica no dispone de antecedente; asignar solo en fixture
    # para verificar la misma regla tambien con una credencial ya normal.
    with factory() as uow:
        current = uow.credential(user.id)
        uow.put_credential(replace(current, password_inicial_hash=service.hasher.hash(PASSWORD)))
    service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    result = service.login(str(user.email), NEW_PASSWORD, IP)
    principal = service.authenticate(result.access_token)
    before = saved((service, factory, user, principal))
    with pytest.raises(PasswordReutilizada):
        service.change_password(principal, NEW_PASSWORD, PASSWORD, ip=IP)
    assert saved((service, factory, user, principal)) == before


def test_historical_unknown_initial_does_not_create_history(password_case):
    service, factory, user, principal, *_ = password_case
    original, _ = saved(password_case)
    service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    with factory() as uow:
        assert uow.credential(user.id).password_inicial_hash == original.password_inicial_hash


@pytest.mark.parametrize("failure", ["write", "revoke", "release"])
def test_failures_before_commit_preserve_credential_and_sessions(password_case, monkeypatch, failure):
    service, factory, _, principal, token, _, _, _ = password_case
    before = saved(password_case)
    target = service.limiter if failure == "release" else type(factory())
    method = {"write": "put_credential", "revoke": "revoke", "release": "success"}[failure]
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs): raise RuntimeError("injected failure")
        patch.setattr(target, method, fail)
        with pytest.raises(RuntimeError):
            service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    assert saved(password_case) == before
    assert service.authenticate_session(token) == principal


def test_concurrent_changes_have_one_winner(password_case, monkeypatch):
    service, factory, user, principal, _, _, _, _ = password_case
    barrier = Barrier(2)
    original = service.hasher.hash

    def hashing(raw):
        result = original(raw)
        barrier.wait(timeout=15)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(service.hasher, "hash", hashing)
        def change(number):
            chosen = NEW_PASSWORD + str(number)
            try:
                service.change_password(principal, PASSWORD, chosen, ip=IP)
                return chosen
            except AutenticacionRequerida:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = [value for value in pool.map(change, range(2)) if value]
    assert len(winners) == 1
    with factory() as uow:
        assert service.hasher.verify(uow.credential(user.id).password_hash, winners[0])
        assert uow.credential(user.id).debe_cambiar_password is False


def test_revocation_during_hash_prevents_commit(password_case, monkeypatch):
    service, factory, user, principal, token, *_ = password_case
    before, _ = saved(password_case)
    original = service.hasher.hash

    def hashing(raw):
        service.logout(token)
        return original(raw)

    monkeypatch.setattr(service.hasher, "hash", hashing)
    with pytest.raises(AutenticacionRequerida):
        service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    with factory() as uow:
        assert uow.credential(user.id) == before


def test_http_wrong_current_limit_retry_and_recovery(password_case):
    service, _, user, principal, token, _, clock, client = password_case
    before = saved(password_case)
    for _ in range(5):
        response = client.put("/api/v1/auth/password", headers=auth(token), json={
            "password_actual": PASSWORD + "wrong", "password_nueva": NEW_PASSWORD})
        assert response.status_code == 401
    response = client.put("/api/v1/auth/password", headers=auth(token), json={
        "password_actual": PASSWORD, "password_nueva": NEW_PASSWORD})
    assert response.status_code == 429
    assert response.json()["error"]["codigo"] == "LIMITE_INTENTOS"
    assert int(response.headers["Retry-After"]) == 890
    assert saved(password_case) == before
    clock[0] += timedelta(seconds=890)
    # La sesion de 900 s todavia es valida; no se espera tiempo real.
    service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    assert service.login(str(user.email), NEW_PASSWORD, IP).debe_cambiar_password is False


def test_login_and_password_share_pair_budget_without_erasing_failures(password_case):
    service, _, user, principal, *_ = password_case
    for _ in range(2):
        with pytest.raises(CredencialesInvalidas): service.login(str(user.email), PASSWORD + "wrong", IP)
        with pytest.raises(CredencialesInvalidas): service.change_password(principal, PASSWORD + "wrong", NEW_PASSWORD, ip=IP)
    # Exito de login libera solo SU reserva; los cuatro fallos siguen contados.
    service.login(str(user.email), PASSWORD, IP)
    # Error de nueva con actual correcta tampoco deja consumo de pareja.
    with pytest.raises(PasswordReutilizada): service.change_password(principal, PASSWORD, PASSWORD, ip=IP)
    with pytest.raises(CredencialesInvalidas): service.change_password(principal, PASSWORD + "wrong", NEW_PASSWORD, ip=IP)
    with pytest.raises(LimiteIntentos): service.login(str(user.email), PASSWORD, IP)
    with pytest.raises(LimiteIntentos): service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)


def test_no_partial_consumption_and_release_is_idempotent(password_case):
    service, _, user, _, _, _, _, _ = password_case
    limiter = service.limiter
    now = service.clock()
    # Cinco fallos agotan pareja. Rechazos adicionales no consumen IP.
    for _ in range(5): limiter.check(str(user.email), IP, now)
    for _ in range(40):
        with pytest.raises(LimiteIntentos): limiter.check(str(user.email), IP, now)
    reservation = limiter.check("another@example.com", IP, now)
    # 2 logins fixture + 5 fallos + 1 reserva = 8 de IP; quedan exactamente 22.
    for i in range(22): limiter.check(f"fixture{i}@example.com", IP, now)
    with pytest.raises(LimiteIntentos): limiter.check("ip-full@example.com", IP, now)
    # La reserva rechazada por IP tampoco deja consumida la pareja en esa IP.
    clock = password_case[6]
    clock[0] += timedelta(seconds=60)
    for _ in range(5): limiter.check("ip-full@example.com", IP, clock[0])
    # Liberar dos veces no borra la reserva de otro intento en la misma pareja.
    second = limiter.check("another@example.com", IP, clock[0])
    limiter.success("another@example.com", IP, now, reservation=reservation)
    limiter.success("another@example.com", IP, now, reservation=reservation)
    for _ in range(4): limiter.check("another@example.com", IP, clock[0])
    with pytest.raises(LimiteIntentos): limiter.check("another@example.com", IP, clock[0])


def test_errors_and_representations_do_not_leak_secrets(password_case, caplog):
    _, _, _, _, token, _, _, client = password_case
    credential, _ = saved(password_case)
    response = client.put("/api/v1/auth/password", headers=auth(token), json={
        "password_actual": PASSWORD, "password_nueva": PASSWORD})
    assert response.status_code == 422
    for secret in (PASSWORD, token, credential.password_hash, credential.password_inicial_hash):
        if secret: assert secret not in response.text + caplog.text + repr(credential)
    assert "429" in client.get("/openapi.json").json()["paths"]["/api/v1/auth/password"]["put"]["responses"]


@pytest.mark.parametrize("new", [" " + "a" * 15 + " ", "\U0001f600" * 15, "x" * 128])
def test_valid_spaces_unicode_and_boundaries_are_preserved(password_case, new):
    service, factory, user, principal, *_ = password_case
    service.change_password(principal, PASSWORD, new, ip=IP)
    with factory() as uow:
        encoded = uow.credential(user.id).password_hash
        assert service.hasher.verify(encoded, new)
        if new != new.strip(): assert not service.hasher.verify(encoded, new.strip())


def test_pair_isolation_and_legitimate_repeated_operations(password_case):
    service, _, user, principal, *_ = password_case
    # Cinco fallos desde otra IP no bloquean la pareja legitima.
    for _ in range(5):
        with pytest.raises(CredencialesInvalidas):
            service.change_password(principal, PASSWORD + "wrong", NEW_PASSWORD, ip="127.0.0.9")
    # Validar nueva repetidamente con actual correcta no acumula fallos de pareja.
    for _ in range(7):
        with pytest.raises(PasswordReutilizada): service.change_password(principal, PASSWORD, PASSWORD, ip=IP)
    service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    assert service.login(str(user.email), NEW_PASSWORD, IP).debe_cambiar_password is False


@pytest.mark.postgres
def test_postgres_commit_failure_rolls_back_hash_and_revocations(
    postgres_repository, postgres_resources, monkeypatch,
):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from auth_support import auth_config, bootstrap_login, build_auth
    from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
    from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia
    _, _, sessions = postgres_resources
    factory = lambda: PostgresSecurityUnitOfWork(sessions)
    service = build_auth(factory, auth_config())
    uid, token = bootstrap_login(service)
    principal = service.authenticate(token)
    with factory() as uow:
        before = uow.credential(uid), uow.session(principal.sesion_id)
    state = {"writing": False}
    original_write = PostgresSecurityUnitOfWork.put_credential
    original_commit = Session.commit

    def writing(self, credential):
        original_write(self, credential)
        state["writing"] = True

    def commit(self):
        if state["writing"]: raise SQLAlchemyError("injected commit failure")
        return original_commit(self)

    with monkeypatch.context() as patch:
        patch.setattr(PostgresSecurityUnitOfWork, "put_credential", writing)
        patch.setattr(Session, "commit", commit)
        with pytest.raises(ErrorPersistencia):
            service.change_password(principal, PASSWORD, NEW_PASSWORD, ip=IP)
    with factory() as uow:
        assert (uow.credential(uid), uow.session(principal.sesion_id)) == before
    assert service.authenticate(token) == principal
