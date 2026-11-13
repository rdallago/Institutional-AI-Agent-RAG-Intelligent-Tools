"""Solo una base nueva vacía, previamente creada y autorizada por el operador."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import re

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from app.infrastructure.configuration.database import DatabaseConfig


def disposable_config(values=None):
    values = os.environ if values is None else values
    name = values.get('JINA_TEST_DATABASE', '')
    if not re.fullmatch(r'rag_jina_10c_[0-9a-f]{32}', name):
        raise ValueError('Se requiere una base desechable con UUID; bases existentes habituales prohibidas.')
    if values.get('JINA_TEST_ALLOW_SCHEMA') != name:
        raise ValueError('Falta autorización explícita de esquema para esa base.')
    host = values.get('JINA_TEST_HOST', '127.0.0.1')
    if host != '127.0.0.1':
        raise ValueError('Solo servidor loopback.')
    return DatabaseConfig(host=host, port=int(values.get('JINA_TEST_PORT', '5434')),
        database=name, username=values.get('JINA_TEST_USER', ''), password=values.get('JINA_TEST_PASSWORD', ''))


def validate_empty_target(conn, config):
    actual = conn.execute(text('SELECT current_database()')).scalar_one()
    if actual != config.database:
        raise ValueError('Destino real distinto del autorizado.')
    if conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector' AND extnamespace='public'::regnamespace")).scalar_one_or_none() != '0.8.2':
        raise ValueError('pgvector 0.8.2 debe estar previamente instalado y autorizado.')
    tables = conn.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')")).scalar_one()
    if tables:
        raise ValueError('Base no vacía: no ejecutar DDL ni borrar objetos.')


@contextmanager
def disposable_engine():
    config = disposable_config()  # Antes de construir motor o contactar PostgreSQL.
    engine = create_engine(config.url(), hide_parameters=True, connect_args={'connect_timeout': 3,
        'options': '-c statement_timeout=10000 -c lock_timeout=1000'})
    try:
        with engine.begin() as conn:
            validate_empty_target(conn, config)
            # Serializar el ensayo en la base dedicada; no crear bases ni extensiones.
            conn.execute(text('SELECT pg_advisory_xact_lock(100610)'))
            validate_empty_target(conn, config)
            path = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
            modules = ('0001_crear_usuarios', '0002_auth', '0003_password_inicial',
                       '0004_rag', '0005_agent_memory', '0006_cloud_embeddings')
            with Operations.context(MigrationContext.configure(conn)):
                for name in modules:
                    spec = importlib.util.spec_from_file_location('disposable_' + name, path / (name + '.py'))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.upgrade()
        yield config, engine
    finally:
        engine.dispose()
        # No borrar la base automáticamente: conservar evidencia del ensayo.
