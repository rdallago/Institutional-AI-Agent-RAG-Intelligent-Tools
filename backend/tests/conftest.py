import pytest


@pytest.fixture
def initial_provisioning_test_gate(monkeypatch):
    """Excepcion solo en pruebas aisladas; ninguna implementacion habilita produccion."""
    from app.application.auth import provisioning
    monkeypatch.setattr(provisioning, "require_initial_provisioning_enabled", lambda: None)


def pytest_addoption(parser):
    parser.addoption("--run-postgres", action="store_true", help="Ejecutar integración aislada PostgreSQL")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-postgres"):
        skipped = pytest.mark.skip(reason="Usar --run-postgres para habilitar PostgreSQL aislado")
        for item in items:
            if item.get_closest_marker("postgres"):
                item.add_marker(skipped)


@pytest.fixture(scope="session")
def postgres_resources():
    from alembic import command
    from app.infrastructure.configuration.database import load_database_config
    from app.infrastructure.persistence.database import build_engine, build_session_factory
    from postgres_support import alembic_config, require_test_connection

    config = load_database_config(testing=True)
    engine = build_engine(config)
    try:
        with engine.connect() as connection:
            require_test_connection(connection, config)
        command.upgrade(alembic_config(config), "head")
        yield config, engine, build_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture
def postgres_repository(postgres_resources):
    from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
    from postgres_support import clean_users

    config, engine, sessions = postgres_resources
    clean_users(engine, config)
    try:
        yield SQLAlchemyUserRepository(sessions)
    finally:
        clean_users(engine, config)
