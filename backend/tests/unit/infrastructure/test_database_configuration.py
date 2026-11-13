from dataclasses import replace
import os

import pytest

from app.infrastructure.configuration.database import (
    ConfiguracionBaseInvalida, DatabaseConfig, load_database_config,
)


def test_url_encodes_special_characters_without_exposing_password():
    config = DatabaseConfig("127.0.0.1", 5435, "usuarios_test", "usuarios_test_admin", "test@:/%value")
    assert config.url().password == "test@:/%value"
    assert config.password not in repr(config)
    assert config.password not in str(config.url())


@pytest.mark.parametrize("changes", [
    {"database": "usuarios_dev"}, {"port": 5434}, {"username": "usuarios_dev_admin"},
    {"host": "remote.example"},
])
def test_test_guard_rejects_development_and_unexpected_targets(changes):
    config = DatabaseConfig("127.0.0.1", 5435, "usuarios_test", "usuarios_test_admin", "test-only")
    with pytest.raises(ConfiguracionBaseInvalida):
        replace(config, **changes).require_test_database()


def test_test_configuration_does_not_fall_back_to_development(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("TEST_POSTGRES_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("POSTGRES_PASSWORD", "development-value")
    with pytest.raises(ConfiguracionBaseInvalida):
        load_database_config(testing=True, env_file=tmp_path / "absent")


def test_environment_overrides_file_without_global_mutation(tmp_path, monkeypatch):
    path = tmp_path / "config"
    path.write_text(
        "POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=5434\nPOSTGRES_DB=usuarios_dev\n"
        "POSTGRES_USER=example\nPOSTGRES_PASSWORD='sample@$value'\n", encoding="utf-8",
    )
    for key in list(os.environ):
        if key.startswith("POSTGRES_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("POSTGRES_PORT", "5440")
    config = load_database_config(env_file=path)
    assert config.port == 5440
    assert config.password == "sample@$value"
    assert "POSTGRES_PASSWORD" not in os.environ


def test_programmatic_migrations_reject_development_without_connecting():
    from alembic import command
    from alembic.config import Config
    from app.infrastructure.configuration.database import PROJECT_ROOT

    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.attributes["database_config"] = DatabaseConfig(
        "127.0.0.1", 5434, "usuarios_dev", "usuarios_dev_admin", "unit-test-only",
    )
    with pytest.raises(ConfiguracionBaseInvalida):
        command.upgrade(config, "head")
