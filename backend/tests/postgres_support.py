"""Ayudas compartidas; toda operación destructiva valida primero el destino real."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from app.infrastructure.configuration.database import DatabaseConfig


def alembic_config(config: DatabaseConfig) -> Config:
    config.require_test_database()
    result = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    result.attributes["database_config"] = config
    return result


def require_test_connection(connection, config: DatabaseConfig) -> None:
    config.require_test_database()
    row = connection.execute(text("SELECT current_database(), current_user")).one()
    if tuple(row) != ("usuarios_test", "usuarios_test_admin"):
        raise RuntimeError("Se rechaza modificar una base que no es el destino aislado de pruebas.")


def clean_users(engine, config: DatabaseConfig) -> None:
    with engine.begin() as connection:
        require_test_connection(connection, config)
        connection.execute(text("TRUNCATE TABLE public.auth_intentos, public.auth_sesiones, public.usuario_credenciales, public.usuarios"))
