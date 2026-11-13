import pytest
from alembic import command
from sqlalchemy import inspect, text

from postgres_support import alembic_config, require_test_connection


pytestmark = pytest.mark.postgres


def test_upgrade_downgrade_upgrade_and_metadata_match(postgres_resources):
    config, engine, _ = postgres_resources
    migration_config = alembic_config(config)
    with engine.connect() as connection:
        require_test_connection(connection, config)
    try:
        command.downgrade(migration_config, "base")
        assert "usuarios" not in inspect(engine).get_table_names(schema="public")
        command.upgrade(migration_config, "head")
        assert "usuarios" in inspect(engine).get_table_names(schema="public")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003"
        command.check(migration_config)
        names = {item["name"] for item in inspect(engine).get_indexes("usuarios", schema="public")}
        assert {"ix_usuarios_fecha_id", "ix_usuarios_activo_fecha_id"} <= names
    finally:
        command.upgrade(migration_config, "head")
