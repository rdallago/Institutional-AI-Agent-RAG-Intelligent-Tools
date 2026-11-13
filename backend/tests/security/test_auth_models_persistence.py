"""Contrato de almacenamiento; no activa los flujos del incremento siguiente."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest

from auth_support import PASSWORD, bootstrap_login
from app.application.auth.exceptions import AprovisionamientoRechazado
from app.domain.auth.models import Credencial, Sesion
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.security.crypto import Argon2Hasher


def records(factory, *, pending=True):
    now = datetime.now(UTC)
    user = Usuario.crear(nombre="Fixture", apellido="Security", email=Email(f"{uuid4().hex}@example.com"))
    # Hashes reales de datos ficticios; nunca usar credenciales de desarrollo.
    encoded = Argon2Hasher(memory_cost=512, time_cost=1).hash(PASSWORD)
    credential = Credencial(user.id, encoded, now, now,
        debe_cambiar_password=pending, password_inicial_hash=encoded if pending else None)
    session = Sesion(uuid4(), user.id, now, now + timedelta(seconds=900), restringida=pending)
    with factory() as uow:
        uow.usuarios.agregar(user)
    return user, credential, session


@pytest.mark.parametrize("pending", [False, True])
def test_roundtrip_independent_uows_and_update_preserve_fields(backend_security, pending):
    _, factory = backend_security
    user, credential, session = records(factory, pending=pending)
    with factory() as uow:
        uow.put_credential(credential)
        uow.put_session(session)
    with factory() as uow:
        assert uow.credential(user.id) == credential
        assert uow.session(session.id) == session
        updated = replace(credential, password_hash="replacement-test-hash",
                          actualizada_at=credential.actualizada_at + timedelta(seconds=1))
        uow.put_credential(updated)
        uow.revoke(user.id, session.creada_at + timedelta(seconds=1))
    with factory() as uow:
        assert uow.credential(user.id) == updated
        saved = uow.session(session.id)
        assert saved.restringida is pending
        assert saved.revocada_at is not None


def test_strict_insert_rejects_duplicate_without_overwrite(backend_security):
    _, factory = backend_security
    user, credential, _ = records(factory)
    with factory() as uow:
        uow.insert_initial_credential(credential)
    with factory() as uow:
        with pytest.raises(AprovisionamientoRechazado) as rejected:
            uow.insert_initial_credential(replace(credential, password_hash="other-test-hash"))
        assert credential.password_hash not in str(rejected.value)
        assert uow.credential(user.id) == credential
        # El conflicto no invalida toda la UoW si el llamador lo maneja.
        uow.put_credential(replace(credential, actualizada_at=credential.actualizada_at + timedelta(seconds=1)))
    with factory() as uow:
        assert uow.credential(user.id).password_hash == credential.password_hash


def test_strict_insert_has_one_concurrent_winner(backend_security):
    _, factory = backend_security
    user, credential, _ = records(factory)
    barrier = Barrier(2)

    def insert(number):
        candidate = replace(credential, password_hash=f"candidate-test-{number}")
        barrier.wait(timeout=10)
        try:
            with factory() as uow:
                uow.insert_initial_credential(candidate)
            return candidate
        except AprovisionamientoRechazado:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [candidate for candidate in pool.map(insert, range(2)) if candidate]
    assert len(winners) == 1
    with factory() as uow:
        assert uow.credential(user.id) == winners[0]


def test_rollback_restores_credential_session_and_profile(backend_security):
    _, factory = backend_security
    user, credential, session = records(factory)
    with factory() as uow:
        uow.insert_initial_credential(credential)
        uow.put_session(session)
    with pytest.raises(RuntimeError):
        with factory() as uow:
            uow.put_credential(replace(credential, debe_cambiar_password=False))
            uow.put_session(replace(session, restringida=False))
            profile = uow.usuarios.obtener_por_id(user.id)
            profile.dar_de_baja()
            uow.usuarios.actualizar(profile)
            raise RuntimeError("injected rollback")
    with factory() as uow:
        assert uow.credential(user.id) == credential
        assert uow.session(session.id) == session
        assert uow.usuarios.obtener_por_id(user.id).activo


def test_rollback_removes_strict_insert(backend_security):
    _, factory = backend_security
    user, credential, _ = records(factory)
    with pytest.raises(RuntimeError):
        with factory() as uow:
            uow.insert_initial_credential(credential)
            raise RuntimeError("injected rollback")
    with factory() as uow:
        assert uow.credential(user.id) is None


def test_existing_factories_and_rehash_keep_normal_state(backend_security):
    service, factory = backend_security
    user_id, token = bootstrap_login(service)
    with factory() as uow:
        original = uow.credential(user_id)
        assert original.debe_cambiar_password is False
        assert original.password_inicial_hash is None
        # Antecedente conocido sin obligacion: conservarlo en rehash y cambio.
        weaker = Argon2Hasher(memory_cost=512, time_cost=1).hash(PASSWORD)
        stored = replace(original, password_hash=weaker, password_inicial_hash=weaker)
        uow.put_credential(stored)
    result = service.login("operator@example.com", PASSWORD, "127.0.0.9")
    principal = service.authenticate(result.access_token)
    with factory() as uow:
        saved = uow.credential(user_id)
        assert saved.password_hash != weaker
        assert saved.password_inicial_hash == weaker
        assert saved.debe_cambiar_password is False
        assert uow.session(principal.sesion_id).restringida is False
    assert set(vars_response(service.me(principal))) == {
        "id", "nombre", "apellido", "email", "activo", "rol", "fecha_creacion", "debe_cambiar_password"}
    service.change_password(principal, PASSWORD, PASSWORD + "-updated")
    with factory() as uow:
        assert uow.credential(user_id).password_inicial_hash == weaker
        assert uow.credential(user_id).debe_cambiar_password is False


def vars_response(result):
    from dataclasses import asdict
    return asdict(result)


def test_http_contract_does_not_expose_credential_fields(security, security_client):
    store, service, _, user_id, token = security
    credential = store.credentials[user_id]
    store.credentials[user_id] = replace(credential, password_inicial_hash=credential.password_hash)
    response = security_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert set(response.json()) == {"id", "nombre", "apellido", "email", "activo", "rol", "fecha_creacion", "debe_cambiar_password"}
    assert credential.password_hash not in response.text
    assert PASSWORD not in response.text
    result = security_client.post("/api/v1/auth/login", json={
        "email": "operator@example.com", "password": PASSWORD})
    assert result.status_code == 200
    assert set(result.json()) == {"access_token", "token_type", "expires_in", "debe_cambiar_password"}


def test_rehash_preserves_pending_snapshot_and_restricts_session(security):
    store, service, _, user_id, _ = security
    weak = Argon2Hasher(memory_cost=512, time_cost=1).hash(PASSWORD)
    store.credentials[user_id] = replace(store.credentials[user_id], password_hash=weak,
        debe_cambiar_password=True, password_inicial_hash=weak)
    result = service.login("operator@example.com", PASSWORD, "127.0.0.8")
    saved = store.credentials[user_id]
    assert saved.password_hash != weak
    assert saved.debe_cambiar_password is True
    assert saved.password_inicial_hash == weak
    principal = service.authenticate_session(result.access_token)
    assert store.sessions[principal.sesion_id].restringida is True


def test_new_hash_is_hidden_and_flags_are_explicit():
    from app.infrastructure.security.memory import MemorySecurityStore
    _, credential, session = records(MemorySecurityStore().uow)
    assert credential.password_hash not in repr(credential)
    assert "password_hash=" not in repr(credential)
    assert "password_inicial_hash=" not in repr(credential)
    with pytest.raises(ValueError):
        replace(credential, password_inicial_hash=None)
    with pytest.raises(ValueError):
        replace(credential, debe_cambiar_password=1)
    with pytest.raises(ValueError):
        replace(session, restringida=1)
    with pytest.raises(TypeError):
        Credencial(credential.usuario_id, "hidden", credential.creada_at, credential.actualizada_at)
    with pytest.raises(TypeError):
        Sesion(session.id, session.usuario_id, session.creada_at, session.expira_at)
