"""Migraciones explícitas; desarrollo requiere una segunda autorización operativa."""

from alembic import context
from sqlalchemy import MetaData
from sqlalchemy.schema import BLANK_SCHEMA

from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.models.usuario import UsuarioModel  # noqa: F401
from app.infrastructure.persistence.models.auth import CredencialModel, SesionModel, IntentoModel  # noqa: F401


arguments = context.get_x_argument(as_dictionary=True)

# PostgreSQL refleja el esquema predeterminado como None, incluso en FK.
# Normalizar solo la copia de comparación; los modelos y DDL siguen en public.
comparison_metadata = MetaData()
for table in Base.metadata.sorted_tables:
    table.to_metadata(comparison_metadata, schema=None,
        referred_schema_fn=lambda table, schema, constraint, referred: BLANK_SCHEMA if referred == "public" else referred)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in (None, "public")
    if type_ == "table":
        return name in {"usuarios", "usuario_credenciales", "auth_sesiones", "auth_intentos"}
    return True


config = context.config.attributes.get("database_config")
if config is None:
    if arguments.get("target") == "test":
        config = load_database_config(testing=True)
    elif arguments.get("allow-development") == "true":
        config = load_database_config()
        if config.database != "usuarios_dev":
            raise RuntimeError("Destino de desarrollo inesperado.")
    else:
        raise RuntimeError("Indicar -x target=test o autorización operativa -x allow-development=true.")
else:
    # La inyección programática se reserva a las pruebas aisladas.
    config.require_test_database()

if context.is_offline_mode():
    context.configure(
        url=config.url(), target_metadata=comparison_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
        include_schemas=True, compare_type=True, include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(config)
    try:
        with engine.connect() as connection:
            actual_database = connection.exec_driver_sql("SELECT current_database()").scalar_one()
            if actual_database != config.database:
                raise RuntimeError("La conexión no corresponde al destino autorizado.")
            connection.rollback()
            context.configure(
                connection=connection, target_metadata=comparison_metadata,
                include_schemas=True, compare_type=True, include_name=include_name,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
