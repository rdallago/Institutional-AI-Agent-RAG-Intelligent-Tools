"""Controles previos sin SQL; el ensayo real requiere base nueva y autorización."""
from contextlib import contextmanager
from uuid import uuid4
import pytest

import jina_disposable_support as support


def settings():
    name = 'rag_jina_10c_' + uuid4().hex
    return {'JINA_TEST_DATABASE': name, 'JINA_TEST_ALLOW_SCHEMA': name,
            'JINA_TEST_USER': 'fixture', 'JINA_TEST_PASSWORD': 'not-a-real-password'}


@pytest.mark.parametrize('name', ['usuarios_dev', 'usuarios_test', 'postgres', 'template1',
                                 'rag_jina_10c', 'rag_jina_10c_existing', '../usuarios_dev'])
def test_existing_or_unscoped_database_names_rejected(name):
    data = settings();data['JINA_TEST_DATABASE'] = name;data['JINA_TEST_ALLOW_SCHEMA'] = name
    with pytest.raises(ValueError): support.disposable_config(data)


def test_explicit_authorization_and_loopback_required():
    data = settings();data['JINA_TEST_ALLOW_SCHEMA'] = 'wrong'
    with pytest.raises(ValueError): support.disposable_config(data)
    data = settings();data['JINA_TEST_HOST'] = 'external.example'
    with pytest.raises(ValueError): support.disposable_config(data)
    config = support.disposable_config(settings())
    assert config.database.startswith('rag_jina_10c_') and config.host == '127.0.0.1'
    assert 'not-a-real-password' not in repr(config)


def test_no_authorization_means_no_engine(monkeypatch):
    monkeypatch.delenv('JINA_TEST_DATABASE', raising=False)
    monkeypatch.delenv('JINA_TEST_ALLOW_SCHEMA', raising=False)
    monkeypatch.setattr(support, 'create_engine', lambda *_a, **_k: pytest.fail('No engine/SQL'))
    with pytest.raises(ValueError):
        with support.disposable_engine(): pass


@pytest.mark.parametrize('case', ['different_database', 'missing_pgvector', 'not_empty'])
def test_read_only_preconditions_reject_before_ddl(case):
    config = support.disposable_config(settings())
    queries = []
    class Reply:
        def __init__(self, value): self.value = value
        def scalar_one(self): return self.value
        def scalar_one_or_none(self): return self.value
    class Conn:
        def execute(self, statement):
            sql = str(statement);queries.append(sql)
            if 'current_database()' in sql:
                return Reply('usuarios_dev' if case == 'different_database' else config.database)
            if 'extversion' in sql: return Reply(None if case == 'missing_pgvector' else '0.8.2')
            return Reply(1)
    with pytest.raises(ValueError): support.validate_empty_target(Conn(), config)
    assert all(q.startswith('SELECT') for q in queries)


@pytest.mark.parametrize('llm,embedding', [('openrouter', 'ollama'), ('ollama', 'jina')])
def test_misconfigured_operational_rag_fails_before_any_runtime(monkeypatch, llm, embedding):
    from unittest.mock import Mock
    from auth_support import memory_auth
    from fastapi.testclient import TestClient
    import app.bootstrap as bootstrap
    from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida
    from app.infrastructure.configuration.embeddings import EmbeddingConfig
    store, auth, _ = memory_auth()
    engine = Mock()
    monkeypatch.setattr(bootstrap, 'crear_persistencia_postgresql', lambda *_: (engine, store.users))
    monkeypatch.setattr('app.infrastructure.configuration.llm_local.require_local_runtime', lambda *_: None)
    monkeypatch.setattr('app.infrastructure.configuration.embeddings.load_embedding_config',
                        lambda: EmbeddingConfig(provider=embedding))
    def forbidden(*_a, **_k): pytest.fail('No crear clientes/runtimes con configuración inválida')
    monkeypatch.setattr('app.infrastructure.llm.ollama.ollama_runtime', forbidden)
    monkeypatch.setattr('app.infrastructure.llm.openrouter.openrouter_runtime', forbidden)
    config = LLMConfig(enabled=True, environment='local-development', provider=llm, api_key='synthetic')
    with pytest.raises(LLMConfigInvalida):
        with TestClient(bootstrap.create_app(auth_service=auth, llm_config=config)): pass
    engine.dispose.assert_called_once()
