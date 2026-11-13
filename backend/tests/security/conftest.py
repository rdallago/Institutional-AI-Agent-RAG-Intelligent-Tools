import pytest
from fastapi.testclient import TestClient

from auth_support import memory_auth, bootstrap_login
from app.bootstrap import create_app
from auth_support import auth_config, build_auth


@pytest.fixture
def security():
    store, service, config = memory_auth()
    admin_id, token = bootstrap_login(service)
    return store, service, config, admin_id, token


@pytest.fixture
def security_client(security):
    store, service, _, _, _ = security
    with TestClient(create_app(repository=store.users, auth_service=service)) as client:
        yield client


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.postgres)])
def backend_security(request):
    if request.param == "memory":
        store, service, config = memory_auth()
        return service, store.uow
    request.getfixturevalue("postgres_repository")
    _, _, sessions = request.getfixturevalue("postgres_resources")
    from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
    factory = lambda: PostgresSecurityUnitOfWork(sessions)
    return build_auth(factory, auth_config()), factory
