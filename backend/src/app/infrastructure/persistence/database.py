"""Engine compartido; sesiones y transacciones independientes por operación."""

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.configuration.database import DatabaseConfig


def build_engine(config: DatabaseConfig) -> Engine:
    return create_engine(
        config.url(), pool_pre_ping=True, pool_size=5, max_overflow=3,
        pool_timeout=10, hide_parameters=True, echo=False,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
