"""Configuración PostgreSQL sin exponer credenciales."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import URL


PROJECT_ROOT = Path(__file__).resolve().parents[5]


class ConfiguracionBaseInvalida(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
            self.host, self.database, self.username, self.password,
        )) or type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ConfiguracionBaseInvalida("Configuración PostgreSQL incompleta o inválida.")

    def url(self) -> URL:
        return URL.create(
            "postgresql+psycopg", username=self.username, password=self.password,
            host=self.host, port=self.port, database=self.database,
        )

    def require_test_database(self) -> None:
        if (
            self.database != "usuarios_test"
            or self.username != "usuarios_test_admin"
            or self.host not in {"127.0.0.1", "localhost"}
            or self.port != 5435
        ):
            raise ConfiguracionBaseInvalida(
                "Pruebas permitidas solo en usuarios_test, usuario de pruebas y puerto local 5435."
            )


def load_database_config(*, testing: bool = False, env_file: Path | None = None) -> DatabaseConfig:
    """Pruebas nunca usan variables POSTGRES_* ni el archivo de desarrollo."""
    prefix = "TEST_POSTGRES_" if testing else "POSTGRES_"
    path = env_file if env_file is not None else PROJECT_ROOT / (".env.test" if testing else ".env")
    # Evitar interpolación implícita de secretos entre variables del archivo.
    values = dict(dotenv_values(path, interpolate=False)) if path.exists() else {}
    values.update({key: value for key, value in os.environ.items() if key.startswith(prefix)})
    try:
        config = DatabaseConfig(
            host=values.get(prefix + "HOST") or "127.0.0.1",
            port=int(values[prefix + "PORT"]),
            database=values[prefix + "DB"],
            username=values[prefix + "USER"],
            password=values[prefix + "PASSWORD"],
        )
    except (KeyError, TypeError, ValueError):
        raise ConfiguracionBaseInvalida("Revisar las variables PostgreSQL obligatorias.") from None
    if testing:
        config.require_test_database()
    return config
