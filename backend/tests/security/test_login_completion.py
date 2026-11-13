"""No confirmar sesiones si falla la liberacion de la reserva propia."""
import pytest

from auth_support import PASSWORD, bootstrap_login
from app.bootstrap import create_app
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository
from fastapi.testclient import TestClient


@pytest.mark.parametrize('after_release', [False, True], ids=['before-release', 'after-release'])
def test_release_failure_prevents_session_and_preserves_existing(backend_security, monkeypatch, after_release):
    service, factory = backend_security
    _, old_token = bootstrap_login(service)
    old_principal = service.authenticate(old_token)
    with factory() as uow:
        before_credential = uow.credential(old_principal.usuario_id)
        before_session = uow.session(old_principal.sesion_id)
    original_success = service.limiter.success
    original_factory = service.uow_factory
    writes = []

    def tracked_factory():
        uow = original_factory()
        original_put = uow.put_session
        def put(session):
            writes.append(session.id)
            original_put(session)
        uow.put_session = put
        return uow

    def fail(*args, **kwargs):
        if after_release:
            original_success(*args, **kwargs)
        raise RuntimeError('injected release failure')

    with monkeypatch.context() as patch:
        patch.setattr(service, 'uow_factory', tracked_factory)
        patch.setattr(service.limiter, 'success', fail)
        with TestClient(create_app(repository=InMemoryUserRepository(), auth_service=service)) as client:
            response = client.post('/api/v1/auth/login', json={'email': 'operator@example.com', 'password': PASSWORD})
        assert response.status_code == 500
        assert 'access_token' not in response.text and PASSWORD not in response.text
        assert 'injected release failure' not in response.text
    assert writes == []
    with factory() as uow:
        assert uow.credential(old_principal.usuario_id) == before_credential
        assert uow.session(old_principal.sesion_id) == before_session
    assert service.authenticate(old_token) == old_principal
    assert service.login('operator@example.com', PASSWORD, '127.0.0.9').access_token


def test_release_precedes_final_transaction_and_signing_rollback(backend_security, monkeypatch):
    service, factory = backend_security
    _, token = bootstrap_login(service)
    principal = service.authenticate(token)
    original_success = service.limiter.success
    state = {'released': False}
    attempted = []
    def success(*args, **kwargs):
        original_success(*args, **kwargs)
        state['released'] = True
    def fail_signing(session):
        assert state['released']
        attempted.append(session.id)
        raise RuntimeError('injected signing failure')
    monkeypatch.setattr(service.limiter, 'success', success)
    monkeypatch.setattr(service.tokens, 'issue', fail_signing)
    with pytest.raises(RuntimeError, match='injected signing failure'):
        service.login('operator@example.com', PASSWORD, '127.0.0.8')
    with factory() as uow:
        assert uow.session(attempted[0]) is None
    assert service.authenticate(token) == principal


@pytest.mark.postgres
def test_login_commit_failure_does_not_leave_session(postgres_repository, postgres_resources, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from auth_support import auth_config, build_auth
    from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
    from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia
    _, _, sessions = postgres_resources
    factory = lambda: PostgresSecurityUnitOfWork(sessions)
    service = build_auth(factory, auth_config())
    _, old_token = bootstrap_login(service)
    attempted = []
    original_put = PostgresSecurityUnitOfWork.put_session
    original_commit = Session.commit
    def put(self, session):
        original_put(self, session)
        attempted.append(session.id)
    def commit(self):
        if attempted:
            raise SQLAlchemyError('injected login commit failure')
        return original_commit(self)
    with monkeypatch.context() as patch:
        patch.setattr(PostgresSecurityUnitOfWork, 'put_session', put)
        patch.setattr(Session, 'commit', commit)
        with pytest.raises(ErrorPersistencia):
            service.login('operator@example.com', PASSWORD, '127.0.0.8')
    assert len(attempted) == 1
    with factory() as uow:
        assert uow.session(attempted[0]) is None
    assert service.authenticate(old_token)
