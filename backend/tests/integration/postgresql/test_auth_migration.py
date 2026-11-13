import pytest
from alembic import command
from sqlalchemy import inspect,text

from auth_support import PASSWORD, build_auth, auth_config, bootstrap_login
from postgres_support import alembic_config,require_test_connection
from app.domain.usuarios.usuario import Usuario
from app.domain.usuarios.email import Email
from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork

pytestmark=pytest.mark.postgres


def test_0002_preserves_existing_profiles_on_upgrade_and_downgrade(postgres_repository,postgres_resources):
    config,engine,_=postgres_resources
    entity=Usuario.crear(nombre="Existing",apellido="Profile",email=Email("existing@example.com"))
    postgres_repository.agregar(entity)
    migration=alembic_config(config)
    try:
        command.downgrade(migration,"0001")
        assert "usuario_credenciales" not in inspect(engine).get_table_names(schema="public")
        assert postgres_repository.obtener_por_id(entity.id).email==entity.email
        command.upgrade(migration,"head")
        with engine.connect() as connection:
            require_test_connection(connection,config)
            assert connection.execute(text("SELECT count(*) FROM public.usuario_credenciales")).scalar_one()==0
            assert connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()=="0003"
        command.check(migration)
    finally:
        command.upgrade(migration,"head")


def test_persisted_credentials_and_attempts_do_not_contain_plaintext(postgres_repository,postgres_resources):
    config,engine,sessions=postgres_resources
    service=build_auth(lambda:PostgresSecurityUnitOfWork(sessions),auth_config())
    bootstrap_login(service)
    with engine.connect() as connection:
        require_test_connection(connection,config)
        hashes=connection.execute(text("SELECT password_hash FROM public.usuario_credenciales")).scalars().all()
        assert all(value.startswith("$argon2id$") and PASSWORD not in value for value in hashes)
        rows=connection.execute(text("SELECT ambito,clave FROM public.auth_intentos")).all()
        assert all(len(row.clave)==32 for row in rows)
        assert "operator@example.com" not in str(rows)
