"""Migracion 0003 sobre datos historicos ficticios, solo usuarios_test."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from postgres_support import alembic_config, require_test_connection

pytestmark = pytest.mark.postgres


def snapshot(engine, config, queries):
    with engine.connect() as connection:
        require_test_connection(connection, config)
        return [connection.execute(text(query)).all() for query in queries]


def test_0003_preserves_historical_data_and_reverses_only_new_columns(
    postgres_repository, postgres_resources,
):
    config, engine, _ = postgres_resources
    migration = alembic_config(config)
    now = datetime.now(UTC)
    queries = [
        "SELECT * FROM public.usuarios ORDER BY id",
        "SELECT usuario_id,password_hash,creada_at,actualizada_at FROM public.usuario_credenciales ORDER BY usuario_id",
        "SELECT id,usuario_id,creada_at,expira_at,revocada_at FROM public.auth_sesiones ORDER BY id",
        "SELECT * FROM public.auth_intentos ORDER BY ambito,clave,inicio",
    ]
    with engine.connect() as connection:
        require_test_connection(connection, config)
    try:
        command.downgrade(migration, "0002")
        with engine.begin() as connection:
            require_test_connection(connection, config)
            # Matriz: ambos roles, activos/inactivos, con/sin credencial.
            for role in ("ADMIN", "USUARIO"):
                for active in (True, False):
                    for has_credential in (True, False):
                        user_id = uuid4()
                        connection.execute(text("""INSERT INTO public.usuarios
                            (id,nombre,apellido,email,activo,rol,fecha_creacion)
                            VALUES (:id,'Historical','Fixture',:email,:active,:role,:now)"""),
                            dict(id=user_id, email=f"{user_id.hex}@example.com", active=active, role=role, now=now))
                        if has_credential:
                            connection.execute(text("""INSERT INTO public.usuario_credenciales
                                (usuario_id,password_hash,creada_at,actualizada_at)
                                VALUES (:id,:encoded,:now,:now)"""),
                                dict(id=user_id, encoded="historical-test-verifier", now=now))
                            for revoked in (None, now):
                                connection.execute(text("""INSERT INTO public.auth_sesiones
                                    (id,usuario_id,creada_at,expira_at,revocada_at)
                                    VALUES (:id,:uid,:now,:expires,:revoked)"""),
                                    dict(id=uuid4(), uid=user_id, now=now,
                                         expires=now+timedelta(seconds=900), revoked=revoked))
        before = snapshot(engine, config, queries)
        tables_before = set(inspect(engine).get_table_names(schema="public"))
        command.upgrade(migration, "0003")
        assert snapshot(engine, config, queries) == before
        assert set(inspect(engine).get_table_names(schema="public")) == tables_before
        with engine.connect() as connection:
            require_test_connection(connection, config)
            assert connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == "0003"
            assert connection.execute(text("""SELECT count(*) FROM public.usuario_credenciales
                WHERE debe_cambiar_password OR password_inicial_hash IS NOT NULL""")).scalar_one() == 0
            assert connection.execute(text("SELECT count(*) FROM public.auth_sesiones WHERE restringida")).scalar_one() == 0
        columns = {c["name"]: c for c in inspect(engine).get_columns("usuario_credenciales", schema="public")}
        assert columns["debe_cambiar_password"]["nullable"] is False
        assert columns["debe_cambiar_password"]["default"] is None
        assert columns["password_inicial_hash"]["nullable"] is True
        session_columns = {c["name"]: c for c in inspect(engine).get_columns("auth_sesiones", schema="public")}
        assert session_columns["restringida"]["nullable"] is False
        assert session_columns["restringida"]["default"] is None
        checks = {c["name"] for c in inspect(engine).get_check_constraints("usuario_credenciales", schema="public")}
        assert "ck_credenciales_password_inicial" in checks
        command.check(migration)
        command.downgrade(migration, "0002")
        assert snapshot(engine, config, queries) == before
        assert "debe_cambiar_password" not in {c["name"] for c in inspect(engine).get_columns("usuario_credenciales", schema="public")}
        assert "restringida" not in {c["name"] for c in inspect(engine).get_columns("auth_sesiones", schema="public")}
        command.upgrade(migration, "0003")
        assert snapshot(engine, config, queries) == before
        command.check(migration)
    finally:
        command.upgrade(migration, "head")


@pytest.mark.parametrize("statement", [
    "UPDATE public.usuario_credenciales SET debe_cambiar_password=true,password_inicial_hash=NULL",
    "UPDATE public.usuario_credenciales SET debe_cambiar_password=NULL",
    "UPDATE public.auth_sesiones SET restringida=NULL",
])
def test_database_rejects_invalid_password_state(postgres_repository, postgres_resources, statement):
    from auth_support import auth_config, bootstrap_login, build_auth
    from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
    config, engine, sessions = postgres_resources
    service = build_auth(lambda: PostgresSecurityUnitOfWork(sessions), auth_config())
    bootstrap_login(service)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            require_test_connection(connection, config)
            connection.execute(text(statement))
