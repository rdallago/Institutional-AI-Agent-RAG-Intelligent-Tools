from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest

from auth_support import PASSWORD, bootstrap_login
from app.application.auth.exceptions import AprovisionamientoRechazado, LimiteIntentos, AutenticacionRequerida
from app.application.usuarios.dto import CrearUsuarioDatos
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.application.usuarios.ports.user_repository import EmailDuplicadoRepositorio
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.domain.usuarios.rol import Rol
from app.domain.auth.models import Credencial

pytestmark = pytest.mark.usefixtures("initial_provisioning_test_gate")


def test_bootstrap_preserves_existing_admin_profiles_without_claiming(backend_security):
    service, factory = backend_security
    with factory() as uow:
        old = CrearUsuario(uow.usuarios).ejecutar(CrearUsuarioDatos(nombre="Existing", apellido="Admin", email="old@example.com", rol=Rol.ADMIN))
    with pytest.raises(AprovisionamientoRechazado): service.bootstrap("Other","Person",old.email,PASSWORD)
    new_id = service.bootstrap("New","Operator","new@example.com",PASSWORD)
    with factory() as uow:
        assert uow.credential(old.id) is None
        assert uow.usuarios.obtener_por_id(old.id).rol is Rol.ADMIN
        assert uow.credential(new_id) is not None
    with pytest.raises(AprovisionamientoRechazado): service.assign_initial(old.id,PASSWORD)
    with pytest.raises(AprovisionamientoRechazado): service.bootstrap("Second","Operator","second@example.com",PASSWORD)


def test_initial_assignment_by_uuid_is_one_time_and_closes_bootstrap_for_admin(backend_security):
    service, factory = backend_security
    with factory() as uow:
        admin = CrearUsuario(uow.usuarios).ejecutar(CrearUsuarioDatos(nombre="Existing", apellido="Admin", email="existing@example.com", rol=Rol.ADMIN))
    service.assign_initial(admin.id, PASSWORD)
    with pytest.raises(AprovisionamientoRechazado): service.assign_initial(admin.id,PASSWORD+"overwrite")
    with pytest.raises(AprovisionamientoRechazado): service.bootstrap("New","Admin","new@example.com",PASSWORD)


def test_bootstrap_rolls_back_profile_when_credential_write_fails(backend_security, monkeypatch):
    service, factory = backend_security
    cls = type(factory())
    with monkeypatch.context() as patch:
        def fail(*args): raise RuntimeError("injected failure")
        patch.setattr(cls,"insert_initial_credential",fail)
        with pytest.raises(RuntimeError): service.bootstrap("A","B","failure@example.com",PASSWORD)
    with factory() as uow:
        assert uow.usuarios.obtener_por_email(Email("failure@example.com")) is None


def test_password_and_baja_roll_back_if_revocation_fails(backend_security, monkeypatch):
    service, factory = backend_security
    admin_id, token = bootstrap_login(service)
    principal = service.authenticate(token)
    with factory() as uow:
        target = CrearUsuario(uow.usuarios).ejecutar(CrearUsuarioDatos(nombre="User", apellido="Test",email="target@example.com"))
        original = uow.credential(admin_id)
    cls = type(factory())
    with monkeypatch.context() as patch:
        def fail(*args): raise RuntimeError("injected failure")
        patch.setattr(cls,"revoke",fail)
        with pytest.raises(RuntimeError): service.change_password(principal,PASSWORD,PASSWORD+"new")
        with pytest.raises(RuntimeError): service.manage(principal,"baja",target.id)
    with factory() as uow:
        assert uow.credential(admin_id).password_hash == original.password_hash
        assert uow.usuarios.obtener_por_id(target.id).activo
        assert uow.session(principal.sesion_id).revocada_at is None


def test_baja_revocation_and_reactivation_never_restore_session(backend_security):
    service,factory=backend_security
    _,token=bootstrap_login(service)
    admin=service.authenticate(token)
    with factory() as uow:
        target=CrearUsuario(uow.usuarios).ejecutar(CrearUsuarioDatos(nombre="User",apellido="Test",email="target@example.com"))
    from auth_support import seed_legacy_credential
    seed_legacy_credential(service, target.id)
    old=service.login(target.email,PASSWORD,"127.0.0.3").access_token
    service.manage(admin,"baja",target.id)
    service.manage(admin,"reactivar",target.id)
    with pytest.raises(AutenticacionRequerida): service.authenticate(old)
    assert service.authenticate(service.login(target.email,PASSWORD,"127.0.0.3").access_token)


def test_duplicate_email_savepoint_allows_following_write(backend_security):
    _,factory=backend_security
    original=Usuario.crear(nombre="A",apellido="B",email=Email("same@example.com"))
    with factory() as uow:
        uow.usuarios.agregar(original)
        with pytest.raises(EmailDuplicadoRepositorio):
            uow.usuarios.agregar(Usuario.crear(nombre="C",apellido="D",email=original.email))
        uow.usuarios.agregar(Usuario.crear(nombre="E",apellido="F",email=Email("after@example.com")))
    with factory() as uow:
        assert uow.usuarios.obtener_por_email(Email("after@example.com")) is not None


def test_concurrent_bootstrap_has_one_winner(backend_security):
    service,_=backend_security
    barrier=Barrier(2)
    def run(number):
        barrier.wait(timeout=10)
        try:
            service.bootstrap("Operator","Test",f"admin{number}@example.com",PASSWORD)
            return True
        except AprovisionamientoRechazado:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(run,range(2))) == 1


def test_concurrent_attempt_reservations_are_bounded_and_expire(backend_security):
    service,factory=backend_security
    now=datetime(2026,1,1,tzinfo=UTC)
    barrier=Barrier(12)
    def run(_):
        barrier.wait(timeout=10)
        try:
            service.limiter.check("private@example.com","127.0.0.1",now)
            return True
        except LimiteIntentos as error:
            assert error.retry_after > 0
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(run,range(12))) == 5
    assert service.limiter.cleanup(now+timedelta(minutes=16)) == 2
    service.limiter.check("private@example.com","127.0.0.1",now+timedelta(minutes=16))


def test_successful_login_releases_pair_reservation(backend_security):
    service,_=backend_security
    bootstrap_login(service)
    for _ in range(7):
        assert service.login("operator@example.com",PASSWORD,"127.0.0.2").access_token


def test_password_change_racing_with_login_cannot_issue_old_credential_session(backend_security, monkeypatch):
    from app.application.auth.exceptions import CredencialesInvalidas
    service,_=backend_security
    _,token=bootstrap_login(service)
    principal=service.authenticate(token)
    original=service.hasher.verify
    changed=False
    def verify(encoded,password):
        nonlocal changed
        result=original(encoded,password)
        if not changed:
            changed=True
            service.change_password(principal,PASSWORD,PASSWORD+"changed")
        return result
    monkeypatch.setattr(service.hasher,"verify",verify)
    with pytest.raises(CredencialesInvalidas): service.login("operator@example.com",PASSWORD,"127.0.0.3")
    with pytest.raises(AutenticacionRequerida): service.authenticate(token)


def test_session_is_rolled_back_when_token_signing_fails(backend_security, monkeypatch):
    service,factory=backend_security
    _,old_token=bootstrap_login(service)
    attempted=[]
    def fail(session):
        attempted.append(session.id)
        raise RuntimeError("signing unavailable")
    monkeypatch.setattr(service.tokens,"issue",fail)
    with pytest.raises(RuntimeError): service.login("operator@example.com",PASSWORD,"127.0.0.8")
    with factory() as uow:
        assert uow.session(attempted[0]) is None
    assert service.authenticate(old_token)
